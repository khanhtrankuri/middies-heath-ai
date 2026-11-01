"""Blind human annotation of question quality and inter-annotator agreement.

export: write a CSV where each row shows one conversation prefix and one
        system response. System identity is replaced by a random code and rows
        are shuffled, so annotators cannot tell base from fine-tuned output.
        The key mapping codes to runs is written to a separate file that must
        not be shared with annotators.
agree:  read two or more completed CSVs (same rows) and report per-criterion
        Cohen's kappa for every annotator pair and raw percent agreement.

Rubric: QUESTION_RUBRIC.md. Scores are integers 1–3 per criterion.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import random
from pathlib import Path

from evals.dialogue_metrics import cohen_kappa

CRITERIA = ("relevance", "non_redundancy", "safety", "clarity", "context_sufficiency",
            "risk_handling", "no_fabrication", "no_premature_diagnosis")


def _load_rows(run_dir: Path) -> dict[str, dict]:
    rows = {}
    for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if "kind" not in row:
            rows[row["item_id"]] = row
    return rows


def export(runs: list[Path], test_items: list[dict], output: Path, *, sample: int, seed: int, one_per_conversation: bool = False) -> None:
    if output.exists() or output.with_name(output.stem + "_KEY_do_not_share.json").exists():
        raise FileExistsError("Annotation export exists; preserve prior review work")
    by_run = {run.name: _load_rows(run) for run in runs}
    common = sorted(set.intersection(*(set(rows) for rows in by_run.values())))
    rng = random.Random(seed)
    if one_per_conversation:
        by_conversation = {}
        items = {item["item_id"]: item for item in test_items}
        for item_id in common:
            if item_id in items:
                by_conversation.setdefault(items[item_id]["conversation_id"], []).append(item_id)
        common = [rng.choice(sorted(by_conversation[key])) for key in sorted(by_conversation)]
    chosen = rng.sample(common, min(sample, len(common)))
    prefixes = {item["item_id"]: item["prefix"] for item in test_items}
    codes = {name: f"S{index + 1}" for index, name in enumerate(rng.sample(sorted(by_run), len(by_run)))}
    records = []
    for item_id in chosen:
        context = "\n".join(f"[{'Bệnh nhân' if m['role'] == 'user' else 'Trợ lý'}] {m['content']}" for m in prefixes[item_id])
        for name, rows in by_run.items():
            records.append({"row_id": f"{item_id}|{codes[name]}", "context": context, "response": rows[item_id]["response"],
                            **{criterion: "" for criterion in CRITERIA}, "comment": ""})
    rng.shuffle(records)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    output.with_name(output.stem + "_KEY_do_not_share.json").write_text(
        json.dumps({code: name for name, code in codes.items()}, ensure_ascii=False, indent=2), encoding="utf-8")


def agreement(files: list[Path]) -> dict:
    sheets = []
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            sheets.append({row["row_id"]: row for row in csv.DictReader(handle)})
    common = sorted(set.intersection(*(set(sheet) for sheet in sheets)))
    report: dict = {"rows": len(common), "annotators": [path.name for path in files], "criteria": {}}
    for criterion in CRITERIA:
        pairs = {}
        for (i, left), (j, right) in itertools.combinations(enumerate(sheets), 2):
            usable = [r for r in common if left[r].get(criterion, "").strip() and right[r].get(criterion, "").strip()]
            a = [int(left[r][criterion]) for r in usable]
            b = [int(right[r][criterion]) for r in usable]
            pairs[f"{files[i].name}~{files[j].name}"] = {
                "n": len(usable), "cohen_kappa": cohen_kappa(a, b),
                "percent_agreement": sum(x == y for x, y in zip(a, b)) / len(usable) if usable else None,
            }
        report["criteria"][criterion] = pairs
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    exp = sub.add_parser("export")
    exp.add_argument("runs", nargs="+", type=Path)
    exp.add_argument("--test-file", type=Path, default=Path("data/processed/vietnamese_dialogue_v1_strict/test.jsonl"))
    exp.add_argument("--conversations", type=int, default=100)
    exp.add_argument("--max-turn", type=int, default=3)
    exp.add_argument("--seed", type=int, default=42)
    exp.add_argument("--sample", type=int, default=60)
    exp.add_argument("--one-per-conversation", action="store_true")
    exp.add_argument("--output", type=Path, default=Path("reports/annotation/question_quality.csv"))
    agr = sub.add_parser("agree")
    agr.add_argument("files", nargs="+", type=Path)
    agr.add_argument("--output", type=Path, default=Path("reports/annotation/agreement.json"))
    args = parser.parse_args(argv)
    if args.command == "export":
        from evals.benchmark_dialogue import build_items

        items = build_items(args.test_file, conversations=args.conversations, max_turn=args.max_turn, seed=args.seed)
        export(args.runs, items, args.output, sample=args.sample, seed=args.seed,
               one_per_conversation=args.one_per_conversation)
        print(f"Wrote {args.output} (key file written separately; do not share it with annotators)")
    else:
        if len(args.files) < 2:
            parser.error("agreement needs at least two annotated files")
        report = agreement(args.files)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
