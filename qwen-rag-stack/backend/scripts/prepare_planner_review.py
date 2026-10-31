"""Export kept/rejected synthetic training examples for independent human review.

This is a purposeful annotation artifact, not production telemetry. It has no
pre-filled expert judgments and must never be mixed back into training until
review decisions and their provenance are recorded.
"""
import argparse
import csv
import json
import random
from pathlib import Path

from training.data.prepare_planner_sft import read_rows


def export(source, prepared, output, *, sample=100, seed=42):
    if output.exists():
        raise FileExistsError("Review file exists")
    candidates = {"kept": [], "rejected": []}
    for row in read_rows(prepared / "audit.jsonl"):
        if row["split"] != "train":
            continue
        candidates["kept" if row["reason"] == "kept" else "rejected"].append(row)
    rng = random.Random(seed)
    chosen = [row for rows in candidates.values() for row in rng.sample(rows, min(sample, len(rows)))]
    wanted = {row["conversation_id"] for row in chosen}
    source_rows = {row["id"]: row for row in read_rows(source / "train.jsonl") if row["id"] in wanted}
    targets = {row["id"]: row for row in read_rows(prepared / "train.jsonl")}
    rng.shuffle(chosen)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "prefix", "reference", "selected_target", "slot", "filter_decision",
            "reasons", "on_target", "non_redundant", "one_question", "no_fabrication", "clinical_safety", "reviewer", "comments"])
        writer.writeheader()
        for item in chosen:
            end = item["prefix_end"]
            row_id = f"{item['conversation_id']}#planner-{end}"
            messages = source_rows[item["conversation_id"]]["messages"]
            target = targets.get(row_id)
            writer.writerow({"id": row_id,
                "prefix": json.dumps([m for m in messages[:end+1] if m["role"] != "system"], ensure_ascii=False),
                "reference": messages[end+1]["content"],
                "selected_target": target["messages"][-1]["content"] if target else "",
                "slot": item.get("target_slot", ""), "filter_decision": "kept" if target else "rejected", "reasons": item["reason"]})
    return {"rows": len(chosen), "expert_review_status": "pending", "seed": seed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/processed/vietnamese_dialogue_v1_strict"))
    parser.add_argument("--prepared", type=Path, default=Path("data/processed/vietnamese_planner_sft_v1"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.source, args.prepared, args.output)))


if __name__ == "__main__":
    main()
