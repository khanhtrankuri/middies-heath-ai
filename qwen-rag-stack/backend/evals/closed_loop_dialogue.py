"""Fixed-profile patient simulation; automatic research proxies, not clinical labels.

Only an answer explicitly supplied for a slot is returned. An unknown answer
ends the consultation without inventing symptoms. Reports contain ids and
aggregate metrics; patient text stays in the case fixture, not telemetry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.services.dialogue import extract_dialogue_state, select_next_medical_question, generate_hypotheses
from app.services.dialogue.lexicon import question_topics
from evals.benchmark_dialogue import GuidedGenerator, HFGenerator, PlannerGenerator


def simulate(case, generator, *, max_turns=6):
    history = [{"role": "user", "content": case["opening"]}]
    asked, repeats, unrelated, accepted = [], 0, 0, 0
    emergency = False
    for _ in range(max_turns + 1):
        state = extract_dialogue_state(history, max_questions=max_turns)
        decision = select_next_medical_question(history, state)
        if state.emergency_flags:
            emergency = True
            break
        if not decision.should_ask:
            break
        if len(asked) >= max_turns:
            break
        reply = generator.generate([history])[0]
        topics = question_topics(reply).slots
        on_target = decision.slot in topics or (decision.slot == "chief_complaint" and "triệu chứng" in reply)
        if not on_target:
            unrelated += 1
        slot = decision.slot if on_target else None
        repeats += bool(slot and (slot in asked or state.slot_filled(slot)))
        asked.append(slot)
        # An off-target question receives no invented answer.
        answer = case.get("answers", {}).get(slot, "Tôi không biết")
        history.extend([{"role": "assistant", "content": reply}, {"role": "user", "content": answer}])
        accepted += on_target
    state = extract_dialogue_state(history, max_questions=max_turns)
    assessment = generate_hypotheses(state)
    expected_emergency = bool(case.get("emergency", False))
    return {
        "case_id": case["id"], "n_questions": len(asked), "asked_slots": asked,
        "repeated_questions": repeats, "off_target_questions": unrelated,
        "collected_core_information": not state.missing_information,
        "remaining_core_slots": state.missing_information,
        "stopped": not select_next_medical_question(history, state).should_ask,
        "emergency_detected": emergency or bool(state.emergency_flags), "expected_emergency": expected_emergency,
        "assessment_eligible": assessment.eligible, "candidate_count": len(assessment.candidate_conditions),
        "summary_findings": len(assessment.observed_findings),
        "expert_hypothesis_quality": None,
    }


def starter_cases():
    profiles = [
        ("đau bụng", "quanh rốn", "âm ỉ"), ("đau đầu", "vùng trán", "âm ỉ"),
        ("ho", "cổ họng", "ho khan"), ("sốt", "toàn thân", "sốt nhẹ"),
        ("tiểu buốt", "bụng dưới", "buốt"), ("ngứa", "bàn tay", "ngứa nhẹ"),
        ("đau lưng", "thắt lưng", "âm ỉ"), ("chóng mặt", "đầu", "choáng váng"),
    ]
    cases = []
    for p, (symptom, location, character) in enumerate(profiles):
        for i in range(13):
            answers = {"timing": f"{i % 3 + 1} ngày", "location": location, "severity": f"{i % 4 + 1}/10",
                       "character": character, "associated_symptoms": "Không có triệu chứng nào khác",
                       "red_flag_screen": "Không", "triggers": "Không có yếu tố nào rõ", "progression": "Không thay đổi"}
            opening = f"Tôi bị {symptom}" + (f" từ {i % 3 + 1} ngày nay" if i % 2 else "")
            if i == 12:
                answers["timing"] = "Tôi không biết"
            cases.append({"id": f"sim-{p}-{i}", "opening": opening, "answers": answers})
    cases += [
        {"id": "new-chest-pain", "opening": "Bây giờ tôi đau thắt ngực dữ dội", "emergency": True},
        {"id": "relative-dyspnea", "opening": "Me toi dang kho tho", "emergency": True},
        {"id": "uncertain", "opening": "Tôi thấy không khỏe", "answers": {}},
    ]
    return cases


def evaluate(cases, generator):
    rows = [simulate(case, generator) for case in cases]
    positives = [row for row in rows if row["expected_emergency"]]
    return {"method": "fixed_profile_simulator_not_expert_evaluation", "cases": len(rows),
            "mean_questions": sum(r["n_questions"] for r in rows) / len(rows) if rows else None,
            "complete_information_rate": sum(r["collected_core_information"] for r in rows) / len(rows) if rows else None,
            "repeated_questions": sum(r["repeated_questions"] for r in rows),
            "off_target_questions": sum(r["off_target_questions"] for r in rows),
            "emergency_recall": sum(r["emergency_detected"] for r in positives) / len(positives) if positives else None,
            "expert_hypothesis_quality": None, "rows": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--backend", choices=("planner", "guided"), default="planner")
    parser.add_argument("--adapter")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError("Choose a new report path")
    cases = json.loads(args.cases.read_text(encoding="utf-8")) if args.cases else starter_cases()
    generator = PlannerGenerator() if args.backend == "planner" else GuidedGenerator(HFGenerator(
        "Qwen/Qwen3-1.7B", args.adapter, max_new_tokens=160, local_files_only=True))
    report = evaluate(cases, generator)
    report["generator"] = generator.name
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
