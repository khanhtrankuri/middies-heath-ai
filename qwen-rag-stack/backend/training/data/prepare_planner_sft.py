"""Derive E5C SFT from frozen Meddies splits without re-splitting or a teacher.

Only train rows are used for optimization; validation is independently derived
from the existing validation split. Test content is used only for leakage
exclusion. The default accepts auto-filtered reference questions, not templates.
No output is described as clinician reviewed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from app.services.dialogue import extract_dialogue_state, select_next_medical_question
from app.services.dialogue.guardrails import check_scope
from app.services.dialogue.lexicon import split_questions
from app.services.dialogue.prompts import CERTAIN_DIAGNOSIS, DISEASE_NAMING, DOSE, PLANNER_PROMPT_VERSION, planner_messages
from app.services.dialogue.question_generator import validate_question
from training.data.prepare_dialogue import DEFAULT_REVISION, normalize_label

VERSION = "planner-sft-v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def first_user(row):
    return normalize_label(next((m["content"] for m in row["messages"] if m["role"] == "user"), ""))


def build_examples(row, *, allow_templates=False):
    """Yield (example or None, audit entry). State sees only a user-ended prefix."""
    history = []
    for index, message in enumerate(row["messages"]):
        if message["role"] not in {"user", "assistant"}:
            continue
        history.append({"role": message["role"], "content": message["content"]})
        if message["role"] != "user" or index + 1 >= len(row["messages"]):
            continue
        reference = row["messages"][index + 1]
        if reference["role"] != "assistant":
            continue
        audit = {"conversation_id": row["id"], "prefix_end": index, "split": row["metadata"]["split"]}
        state = extract_dialogue_state(history)
        decision = select_next_medical_question(history, state)
        if not decision.should_ask or not check_scope(message["content"]).in_scope:
            yield None, {**audit, "reason": "stop_emergency_or_scope"}
            break
        raw = reference["content"]
        questions = split_questions(raw)
        reasons = []
        if "<think" in raw.lower() or "</think" in raw.lower():
            reasons.append("reasoning")
        if DOSE.search(raw) or DISEASE_NAMING.search(raw) or CERTAIN_DIAGNOSIS.search(raw):
            reasons.append("unsafe_reference")
        # A synthetic doctor turn often bundles several questions. Extract
        # exactly one independently valid sentence for the selected slot;
        # none of the other sentences enter the SFT target.
        aligned = [q for q in questions if not validate_question(q, decision, state)]
        if len(aligned) != 1:
            reasons.append("reference_question_count")
        text = aligned[0] if len(aligned) == 1 else ""
        reasons += validate_question(text, decision, state)
        label = "auto_filtered_dataset_question"
        if reasons:
            if not allow_templates or validate_question(decision.text or "", decision, state):
                yield None, {**audit, "reason": ",".join(sorted(set(reasons))), "target_slot": decision.slot}
                continue
            text, label = decision.text, "planner_template_unreviewed"
        example = {
            "id": f"{row['id']}#planner-{index}", "conversation_id": row["id"], "source": "vietnamese", "usage": "sft",
            "messages": [*planner_messages(history, state, decision),
                         {"role": "assistant", "content": json.dumps({"question": text}, ensure_ascii=False)}],
            "metadata": {
                **{key: value for key, value in row["metadata"].items() if key not in {"target_disease", "system_prompt_version"}},
                "source_dataset": "Meddies/meddies-consultant", "conversation_id": row["id"],
                "target_slot": decision.slot, "label_source": label, "prefix_end": index,
                "preparation_version": VERSION, "system_prompt_version": PLANNER_PROMPT_VERSION,
                "clinical_review": "not_reviewed", "reference_rejections": sorted(set(reasons)),
                "reference_question_count": len(questions),
            },
        }
        yield example, {**audit, "target_slot": decision.slot, "label_source": label, "reason": "kept"}


def prepare(source: Path, output: Path, manifest_path: Path, *, allow_templates=False, max_conversations=None):
    if output.exists():
        raise FileExistsError("Choose a new output directory; existing experiments are immutable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["revision"] != DEFAULT_REVISION:
        raise ValueError("Unexpected dataset revision")
    source_hashes = {}
    ids, groups, first = {}, {}, {}
    level = "strict" if source.name.endswith("strict") else "standard"
    for split in ("train", "validation", "test"):
        path = source / f"{split}.jsonl"
        source_hashes[split] = digest(path)
        if manifest["file_sha256"].get(f"{source.name}/{split}.jsonl") != source_hashes[split]:
            raise ValueError(f"Frozen source hash mismatch: {split}")
        ids[split], groups[split], first[split] = set(), set(), set()
        for row in read_rows(path):
            meta = row["metadata"]
            if meta["split"] != split or meta["revision"] != manifest["revision"] or row["id"] in ids[split]:
                raise ValueError("Invalid split, revision or duplicate conversation id")
            ids[split].add(row["id"])
            groups[split].add(meta["group_id"])
            first[split].add(first_user(row))
        # Standard directories also share the STRICT held-out sets.
        split_level = level if split == "train" else "strict"
        if ids[split] != set(manifest["ids"][split_level][split]):
            raise ValueError("Split membership differs from the frozen manifest")
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if ids[a] & ids[b] or groups[a] & groups[b]:
            raise ValueError("Cross-split conversation/group leakage")
    output.mkdir(parents=True)
    stats = {"version": VERSION, "prompt_version": PLANNER_PROMPT_VERSION,
             "source_file_sha256": source_hashes, "source_manifest_sha256": digest(manifest_path),
             "dataset_revision": manifest["revision"], "allow_unreviewed_templates": allow_templates,
             "max_conversations_per_split": max_conversations, "splits": {},
             "clinical_review": "pending; automatic filtering is not medical validation"}
    with (output / "audit.jsonl").open("w", encoding="utf-8") as audit_file:
        for split in ("train", "validation"):
            counts = Counter()
            # Existing files contain overlapping opening patient messages.
            # Preserve their membership but exclude every affected derived row.
            blocked = set.union(*(first[other] for other in first if other != split))
            with (output / f"{split}.jsonl").open("w", encoding="utf-8", newline="\n") as out:
                for number, row in enumerate(read_rows(source / f"{split}.jsonl")):
                    if max_conversations and number >= max_conversations:
                        break
                    counts["conversations_seen"] += 1
                    if first_user(row) in blocked:
                        counts["cross_split_opening_excluded"] += 1
                        continue
                    for example, audit in build_examples(row, allow_templates=allow_templates):
                        audit_file.write(json.dumps(audit, ensure_ascii=False) + "\n")
                        if example:
                            counts[example["metadata"]["label_source"]] += 1
                            counts["kept"] += 1
                            out.write(json.dumps(example, ensure_ascii=False) + "\n")
                        else:
                            counts["rejected"] += 1
                            counts["rejected:" + audit["reason"]] += 1
            stats["splits"][split] = dict(counts)
    stats["output_sha256"] = {name: digest(output / name) for name in ("train.jsonl", "validation.jsonl", "audit.jsonl")}
    code_root = Path(__file__).resolve().parents[2]
    stats["code_sha256"] = {str(p.relative_to(code_root)).replace("\\", "/"): digest(p) for p in sorted(
        list((code_root / "app/services/dialogue").glob("*.py")) + [Path(__file__).resolve()])}
    (output / "manifest.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/processed/vietnamese_dialogue_v1_strict"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/vietnamese_planner_sft_v1"))
    parser.add_argument("--manifest", type=Path, default=Path("data/processed/meddies_dialogue_v1_manifest.json"))
    parser.add_argument("--allow-unreviewed-templates", action="store_true")
    parser.add_argument("--max-conversations", type=int)
    args = parser.parse_args(argv)
    print(json.dumps(prepare(args.source, args.output, args.manifest, allow_templates=args.allow_unreviewed_templates,
                             max_conversations=args.max_conversations), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
