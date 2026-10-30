"""Prepare leakage-controlled multi-turn consultation data from Meddies Vietnamese.

Pipeline: load a pinned dataset revision → clean structure and reasoning →
quality levels (standard/strict) → exact and near-duplicate removal →
group-aware train/validation/test split → JSONL in Qwen chat format with
provenance metadata, a split manifest, rejection log and statistics.

Outputs (``--output-dir``, default ``data/processed``):

* ``vietnamese_dialogue_v1/``        E2 training data (standard level)
* ``vietnamese_dialogue_v1_strict/`` E3 training data (strict level)
  Both directories share identical strict-level ``validation.jsonl`` and
  ``test.jsonl`` so validation loss and benchmarks are comparable.
* ``meddies_dialogue_v1_manifest.json`` split manifest (ids per split, seed, hashes)
* ``meddies_dialogue_v1_stats.json`` retained/rejected counts and leakage checks
* ``meddies_dialogue_v1_rejected.jsonl`` ids and reasons only (no content)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from app.services.dialogue.prompts import CONSULTATION_SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION
from training.data.dialogue_quality import CLEANING_VERSION, assess_conversation
from training.data.near_dedup import near_duplicate_clusters

LOGGER = logging.getLogger(__name__)
DATASET_ID = "Meddies/meddies-consultant"
DEFAULT_REVISION = "05428709a7572f6f0d4aa5045e6ba255fa85af51"
SPLITS = ("train", "validation", "test")
E2_DIR = "vietnamese_dialogue_v1"
E3_DIR = "vietnamese_dialogue_v1_strict"
PREFIX = "meddies_dialogue_v1"


def normalize_label(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def conversation_hash(messages: list[dict[str, str]]) -> str:
    canonical = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assign_splits(
    group_sizes: Mapping[str, int], ratios: tuple[float, float, float], seed: int
) -> dict[str, str]:
    """Deterministically assign whole groups to splits by seeded hash order.

    Groups are visited in sha256(seed:group) order and placed in the split
    whose cumulative boundary the running total has not yet passed, so split
    sizes track the requested ratios while every group stays in one split.
    """
    if len(ratios) != 3 or abs(sum(ratios) - 1) > 1e-6 or any(r <= 0 for r in ratios):
        raise ValueError("ratios must be three positive values summing to 1")
    total = sum(group_sizes.values())
    ordered = sorted(group_sizes, key=lambda group: hashlib.sha256(f"{seed}:{group}".encode()).hexdigest())
    boundaries = (ratios[0] * total, (ratios[0] + ratios[1]) * total)
    assignment: dict[str, str] = {}
    running = 0
    for group in ordered:
        if running < boundaries[0]:
            split = "train"
        elif running < boundaries[1]:
            split = "validation"
        else:
            split = "test"
        assignment[group] = split
        running += group_sizes[group]
    return assignment


def _iter_source(source_parquet: Path | None, revision: str, config: str) -> Iterable[Mapping[str, Any]]:
    if source_parquet is not None:
        import pyarrow.parquet as pq

        table = pq.read_table(source_parquet)
        yield from table.to_pylist()
        return
    from app.dataset_loader import load_meddies_dataset

    yield from load_meddies_dataset(config, streaming=False, revision=revision)


def prepare(
    rows: Iterable[Mapping[str, Any]],
    output_dir: Path,
    *,
    revision: str,
    config: str = "vietnamese",
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
    seed: int = 42,
    group_by: str = "disease",
    near_dup_threshold: float = 0.7,
    max_samples: int | None = None,
) -> dict[str, Any]:
    if group_by not in {"disease", "conversation"}:
        raise ValueError("group_by must be 'disease' or 'conversation'")
    stats: dict[str, Any] = {"total_seen": 0, "rejected_reasons": Counter(), "strict_only_reasons": Counter()}
    rejected: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    seen_hashes: dict[str, str] = {}
    for index, row in enumerate(rows):
        if max_samples is not None and index >= max_samples:
            break
        stats["total_seen"] += 1
        sample_id = str(row.get("id") or f"row-{index}")
        result = assess_conversation(row.get("messages"))
        if result["messages"] is None or not result["standard"]:
            reasons = result["reasons"] if result["messages"] is None else result["standard_reasons"]
            stats["rejected_reasons"].update(reasons)
            rejected.append({"sample_id": sample_id, "level": "standard", "reasons": reasons})
            continue
        digest = conversation_hash(result["messages"])
        if digest in seen_hashes:
            stats["rejected_reasons"]["exact_duplicate"] += 1
            rejected.append({"sample_id": sample_id, "level": "standard", "reasons": ["exact_duplicate"],
                             "duplicate_of": seen_hashes[digest]})
            continue
        seen_hashes[digest] = sample_id
        if not result["strict"]:
            stats["strict_only_reasons"].update(result["strict_reasons"])
        kept.append({
            "sample_id": sample_id,
            "messages": result["messages"],
            "strict": result["strict"],
            "strict_reasons": result["strict_reasons"],
            "target_disease": row.get("target_disease"),
            "disease_key": normalize_label(row.get("target_disease")),
        })

    # Near-duplicates on the patient side; keep the first (lowest index) of each cluster.
    patient_texts = [" ".join(m["content"] for m in item["messages"] if m["role"] == "user") for item in kept]
    roots, confirmed_pairs = near_duplicate_clusters(patient_texts, threshold=near_dup_threshold, seed=seed)
    unique: list[dict[str, Any]] = []
    for index, (item, root) in enumerate(zip(kept, roots)):
        if root != index:
            stats["rejected_reasons"]["near_duplicate"] += 1
            rejected.append({"sample_id": item["sample_id"], "level": "standard", "reasons": ["near_duplicate"],
                             "duplicate_of": kept[root]["sample_id"]})
            continue
        unique.append(item)
    stats["near_duplicate_pairs_confirmed"] = confirmed_pairs

    for item in unique:
        key = item["disease_key"] if group_by == "disease" and item["disease_key"] else f"conv:{item['sample_id']}"
        item["group_id"] = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    sizes = Counter(item["group_id"] for item in unique)
    assignment = assign_splits(sizes, ratios, seed)

    output_dir.mkdir(parents=True, exist_ok=True)
    for name in (E2_DIR, E3_DIR):
        (output_dir / name).mkdir(parents=True, exist_ok=True)
    files = {
        (E2_DIR, "train"): "standard", (E3_DIR, "train"): "strict",
        (E2_DIR, "validation"): "strict", (E3_DIR, "validation"): "strict",
        (E2_DIR, "test"): "strict", (E3_DIR, "test"): "strict",
    }
    handles = {key: (output_dir / key[0] / f"{key[1]}.jsonl").open("w", encoding="utf-8", newline="\n") for key in files}
    manifest_ids: dict[str, dict[str, list[str]]] = {level: defaultdict(list) for level in ("standard", "strict")}
    split_counts: dict[str, Counter] = {"standard": Counter(), "strict": Counter()}
    try:
        for item in sorted(unique, key=lambda value: value["sample_id"]):
            split = assignment[item["group_id"]]
            levels = ["standard"] + (["strict"] if item["strict"] else [])
            for level in levels:
                manifest_ids[level][split].append(item["sample_id"])
                split_counts[level][split] += 1
            for (directory, file_split), level in files.items():
                if file_split != split or level not in levels:
                    continue
                record = {
                    "id": item["sample_id"],
                    "conversation_id": item["sample_id"],
                    "source": config,
                    "usage": "sft",
                    "messages": [{"role": "system", "content": CONSULTATION_SYSTEM_PROMPT}, *item["messages"]],
                    "metadata": {
                        "dataset": DATASET_ID, "revision": revision, "source_config": config, "split": split,
                        "cleaning_version": CLEANING_VERSION, "quality_level": level,
                        "system_prompt_version": SYSTEM_PROMPT_VERSION, "group_id": item["group_id"],
                        "turns": len(item["messages"]),
                        # Analysis only. Never placed in model input.
                        "target_disease": item["target_disease"],
                    },
                }
                handles[(directory, file_split)].write(json.dumps(record, ensure_ascii=False) + "\n")
    finally:
        for handle in handles.values():
            handle.close()

    # Leakage checks on the released splits.
    by_split_groups = defaultdict(set)
    by_split_first_user: dict[str, set[str]] = defaultdict(set)
    for item in unique:
        split = assignment[item["group_id"]]
        by_split_groups[split].add(item["group_id"])
        first_user = next(m["content"] for m in item["messages"] if m["role"] == "user")
        by_split_first_user[split].add(normalize_label(first_user))
    leakage = {
        "group_overlap": {
            f"{a}-{b}": len(by_split_groups[a] & by_split_groups[b])
            for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))
        },
        "identical_first_user_turn_overlap": {
            f"{a}-{b}": len(by_split_first_user[a] & by_split_first_user[b])
            for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))
        },
        "near_duplicates_removed_before_split": True,
    }
    file_hashes = {
        f"{directory}/{split}.jsonl": hashlib.sha256((output_dir / directory / f"{split}.jsonl").read_bytes()).hexdigest()
        for directory, split in files
    }
    manifest = {
        "dataset": DATASET_ID, "revision": revision, "source_config": config, "seed": seed,
        "ratios": dict(zip(SPLITS, ratios)), "group_by": group_by, "near_dup_threshold": near_dup_threshold,
        "cleaning_version": CLEANING_VERSION, "system_prompt_version": SYSTEM_PROMPT_VERSION,
        "max_samples": max_samples, "license": "CC BY-NC 4.0 (non-commercial; verify before any commercial use)",
        "file_sha256": file_hashes,
        "ids": {level: {split: ids[split] for split in SPLITS} for level, ids in manifest_ids.items()},
    }
    summary = {
        "dataset": DATASET_ID, "revision": revision, "cleaning_version": CLEANING_VERSION,
        "total_seen": stats["total_seen"],
        "standard_retained": len(unique),
        "strict_retained": sum(item["strict"] for item in unique),
        "rejected_total": len(rejected),
        "rejected_reasons": dict(stats["rejected_reasons"].most_common()),
        "strict_exclusion_reasons_among_standard": dict(stats["strict_only_reasons"].most_common()),
        "near_duplicate_pairs_confirmed": stats["near_duplicate_pairs_confirmed"],
        "groups": len(sizes),
        "split_counts": {level: {split: counts[split] for split in SPLITS} for level, counts in split_counts.items()},
        "leakage_checks": leakage,
        "output_files": {
            f"{E2_DIR}/train.jsonl": "standard", f"{E3_DIR}/train.jsonl": "strict",
            "*/validation.jsonl": "strict (shared)", "*/test.jsonl": "strict (shared)",
        },
    }
    (output_dir / f"{PREFIX}_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (output_dir / f"{PREFIX}_stats.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / f"{PREFIX}_rejected.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for item in rejected:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--revision", default=DEFAULT_REVISION, help="Pinned Hugging Face dataset revision")
    parser.add_argument("--source-parquet", type=Path, help="Read a local parquet file instead of the Hub")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ratios", type=float, nargs=3, default=(0.8, 0.1, 0.1), metavar=("TRAIN", "VAL", "TEST"))
    parser.add_argument("--group-by", choices=("disease", "conversation"), default="disease")
    parser.add_argument("--near-dup-threshold", type=float, default=0.7)
    parser.add_argument("--max-samples", type=int)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    summary = prepare(
        _iter_source(args.source_parquet, args.revision, "vietnamese"), args.output_dir,
        revision=args.revision, ratios=tuple(args.ratios), seed=args.seed, group_by=args.group_by,
        near_dup_threshold=args.near_dup_threshold, max_samples=args.max_samples,
    )
    LOGGER.info("Prepared dialogue data: %s", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
