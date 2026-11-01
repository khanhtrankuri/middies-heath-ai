"""Planner-controlled question rendering; no provider substitution or raw telemetry."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from .lexicon import fold_aligned, question_topics
from .prompts import CONDITION_NOUN, planner_messages, validate_generated_question


@dataclass
class QuestionResult:
    text: str
    source: str
    validation: dict


def validate_question(text: str, decision, state) -> list[str]:
    problems = validate_generated_question(text, decision.slot or "")
    topic = question_topics(text)
    topics = topic.slots
    if decision.slot not in {"associated_symptoms", "red_flag_screen", "relevant_history"}:
        reported = {s.key for s in state.symptoms + state.negated_symptoms}
        if topic.symptoms - reported:
            problems.append("unreported_symptom")
    # Overlapping symptom lexicons describe the same clinical screen.
    extras = topics - {decision.slot}
    if decision.slot in {"associated_symptoms", "red_flag_screen"}:
        extras -= {"associated_symptoms", "red_flag_screen"}
    if decision.slot == "severity":
        extras.discard("character")
    if extras:
        problems.append("multiple_slots")
    if decision.slot and state.slot_filled(decision.slot):
        problems.append("already_known")
    # No assertions before/after the question: this also prevents invented
    # patient findings. Permit decimals in a numerical question.
    if re.search(r"[.!;\n](?!\d)|[?？].*\S", text.strip().rstrip("?？")):
        problems.append("extra_content")
    if CONDITION_NOUN.search(text) and decision.slot != "relevant_history":
        problems.append("condition_naming")
    if re.search(r"(?:nen|hay|can) (?:uong|dung|su dung)|ke don|system|target_slot|<think>|```|<\|", fold_aligned(text)):
        problems.append("unsafe_or_internal_content")
    if decision.slot == "chief_complaint" and not re.search(r"trieu chung|kho chiu|van de (?:gi|suc khoe)", fold_aligned(text)):
        problems.append("off_target")
    return list(dict.fromkeys(problems))


def resolve_question(raw: str, decision, state) -> QuestionResult:
    problems = []
    text = ""
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {"question"} or not isinstance(payload["question"], str):
            raise ValueError("schema")
        text = payload["question"].strip()
    except (ValueError, TypeError):
        problems.append("invalid_json_schema")
    if not problems:
        problems.extend(validate_question(text, decision, state))
    return QuestionResult(
        text=decision.text or "" if problems else text,
        source="template" if problems else "model",
        validation={"accepted": not problems, "rejection_reasons": problems},
    )


async def generate_question(inference, history, state, decision, *, allow_degraded: bool = False) -> QuestionResult:
    if not decision.should_ask or not decision.text:
        raise ValueError("Cannot generate a question for a stop decision")
    try:
        raw = await inference.generate(planner_messages(history, state, decision))
    except (RuntimeError, TimeoutError, OSError):
        if not allow_degraded:
            raise
        return QuestionResult(decision.text, "template", {"accepted": False, "rejection_reasons": ["model_unavailable"]})
    return resolve_question(raw, decision, state)
