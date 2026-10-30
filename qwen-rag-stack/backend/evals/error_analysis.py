"""Group benchmark failures into error categories with short examples.

  python -m evals.error_analysis reports/benchmark/E1_base reports/benchmark/E3_pilot_lora \
      --output reports/benchmark/error_analysis.md

Categories (question items; turns 1–3 of held-out test conversations):
  no_question            reply asks nothing although the reference doctor asked
  names_conditions_early lists/names candidate conditions at turn 1–2
  over_question_limit    more than two questions in one turn
  off_target             asks questions, but none about a missing core/optional slot
  unsafe                 specific medication dose or certain diagnosis
Behaviour cases: any failed check, grouped by case kind.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

CATEGORIES = ("no_question", "names_conditions_early", "over_question_limit", "off_target", "unsafe")


def categorize(row: dict) -> list[str]:
    labels = []
    if not row["asks_question"]:
        labels.append("no_question")
    if row["premature_diagnosis"]:
        labels.append("names_conditions_early")
    if row["over_question_limit"]:
        labels.append("over_question_limit")
    if row["asks_question"] and row["asked_slots"] and not row["targets_missing"]:
        labels.append("off_target")
    if row["unsafe"]:
        labels.append("unsafe")
    return labels


def _snippet(text: str, limit: int = 220) -> str:
    flat = " ".join(text.replace("|", "/").split())
    return flat[:limit] + ("…" if len(flat) > limit else "")


def analyse(run_dir: Path, examples: int) -> tuple[dict, list[str]]:
    rows = [json.loads(line) for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    questions = [row for row in rows if "kind" not in row]
    behavior = [row for row in rows if "kind" in row]
    counts: Counter[str] = Counter()
    samples: dict[str, list[dict]] = {category: [] for category in CATEGORIES}
    for row in sorted(questions, key=lambda item: item["item_id"]):
        for label in categorize(row):
            counts[label] += 1
            if len(samples[label]) < examples:
                samples[label].append(row)
    failed_behavior = [row for row in behavior if not row["passed"]]
    lines = [f"## {run_dir.name}", "", f"Mục hỏi bệnh: {len(questions)}; ca hành vi: {len(behavior)}", "",
             "| Nhóm lỗi | Số mục | Tỷ lệ |", "|---|---|---|"]
    for category in CATEGORIES:
        lines.append(f"| {category} | {counts[category]} | {counts[category] / len(questions):.3f} |" if questions else f"| {category} | 0 | — |")
    for category in CATEGORIES:
        if samples[category]:
            lines += ["", f"**Ví dụ — {category}**", ""]
            lines += [f"- `{row['item_id']}` (lượt {row['turn_index']}): {_snippet(row['response'])}" for row in samples[category]]
    if failed_behavior:
        lines += ["", "**Ca hành vi không đạt**", ""]
        for row in failed_behavior:
            failed = [name for name, ok in row["checks"].items() if not ok]
            lines.append(f"- `{row['item_id']}` ({row['kind']}; trượt: {', '.join(failed)}): {_snippet(row['response'], 180)}")
    return {"run": run_dir.name, "items": len(questions), "counts": dict(counts),
            "failed_behavior": [row["item_id"] for row in failed_behavior]}, lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--examples", type=int, default=2)
    parser.add_argument("--output", type=Path, default=Path("reports/benchmark/error_analysis.md"))
    args = parser.parse_args(argv)
    summaries, lines = [], ["# Phân tích lỗi", "",
                            "Phân loại tự động bằng các bộ phát hiện của benchmark (độ chính xác đã đo: xem EXPERIMENT_RESULTS.md).", ""]
    for run in args.runs:
        summary, section = analyse(run, args.examples)
        summaries.append(summary)
        lines += section + [""]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    args.output.with_suffix(".json").write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
