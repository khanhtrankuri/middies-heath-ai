"""Regression metrics for deterministic routing, not clinical sensitivity."""
import argparse
import json
from pathlib import Path

from app.triage import find_red_flags


def evaluate(path: Path) -> dict:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Safety cases must be non-empty with unique IDs")
    rows = [{"id": case["id"], "expected": case["emergency"],
             "actual": bool(find_red_flags(case["text"]))} for case in cases]
    tp = sum(row["expected"] and row["actual"] for row in rows)
    fn = sum(row["expected"] and not row["actual"] for row in rows)
    fp = sum(not row["expected"] and row["actual"] for row in rows)
    negatives = sum(not row["expected"] for row in rows)
    return {"case_count": len(rows), "emergency_recall": tp / (tp + fn) if tp + fn else None,
            "false_positive_rate": fp / negatives if negatives else None,
            "passed": fn == 0 and fp == 0, "failures": [r for r in rows if r["expected"] != r["actual"]],
            "note": "Development regression cases only. Not a clinical validation estimate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("safety_cases.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/safety.json"))
    args = parser.parse_args()
    result = evaluate(args.cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = json.dumps(result, ensure_ascii=False, indent=2)
    args.output.write_text(report, encoding="utf-8")
    print(report)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
