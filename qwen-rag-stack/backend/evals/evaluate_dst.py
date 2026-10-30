"""Evaluate the rule-based dialogue state tracker against a gold set.

Reports symptom extraction precision/recall/F1 (present and negated
separately), chief-complaint accuracy, subject accuracy and slot-level
"filled" accuracy. The bundled gold set is developer-annotated and not
clinician-verified; treat numbers as development diagnostics.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.dialogue import extract_dialogue_state
from evals.dialogue_metrics import precision_recall_f1

DEFAULT_GOLD = Path(__file__).with_name("dst_gold_dev.json")


def _prf(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4), "tp": tp, "fp": fp, "fn": fn}


def evaluate(gold: dict[str, Any]) -> dict[str, Any]:
    slots = gold["slots"]
    totals = {"present": [0, 0, 0], "negated": [0, 0, 0]}
    chief_correct = subject_correct = slot_correct = slot_total = 0
    failures = []
    for case in gold["cases"]:
        state = extract_dialogue_state(case["messages"])
        predicted = {
            "present": {item.key for item in state.symptoms},
            "negated": {item.key for item in state.negated_symptoms},
        }
        problems = {}
        for kind in ("present", "negated"):
            tp, fp, fn = precision_recall_f1(predicted[kind], set(case[kind]))
            for index, value in enumerate((tp, fp, fn)):
                totals[kind][index] += value
            if fp or fn:
                problems[kind] = {"predicted": sorted(predicted[kind]), "gold": sorted(case[kind])}
        chief_correct += state.chief_complaint_key == case["chief"]
        subject_correct += state.subject == case["subject"]
        if state.chief_complaint_key != case["chief"]:
            problems["chief"] = {"predicted": state.chief_complaint_key, "gold": case["chief"]}
        for slot in slots:
            expected = slot in case["filled"]
            actual = state.slot_filled(slot)
            slot_total += 1
            slot_correct += expected == actual
            if expected != actual:
                problems.setdefault("slots", []).append({"slot": slot, "predicted_filled": actual, "gold_filled": expected})
        if problems:
            failures.append({"id": case["id"], **problems})
    count = len(gold["cases"])
    return {
        "annotation": gold["annotation"],
        "cases": count,
        "symptom_extraction_present": _prf(*totals["present"]),
        "symptom_extraction_negated": _prf(*totals["negated"]),
        "chief_complaint_accuracy": round(chief_correct / count, 4),
        "subject_accuracy": round(subject_correct / count, 4),
        "state_slot_accuracy": round(slot_correct / slot_total, 4),
        "slot_decisions": slot_total,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output", type=Path, default=Path("reports/dst.json"))
    args = parser.parse_args(argv)
    report = evaluate(json.loads(args.gold.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "failures"}, ensure_ascii=False, indent=2))
    print(f"{len(report['failures'])} case(s) with at least one error; see {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
