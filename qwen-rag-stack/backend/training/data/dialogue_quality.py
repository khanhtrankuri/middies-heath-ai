"""Cleaning and quality filters for multi-turn Meddies consultation dialogues.

Two cumulative levels, each rejection carrying an explicit reason code:

* ``standard`` (experiment E2) — structural validity, removal of private
  reasoning, and removal of conversations whose doctor turns contain unsafe
  content (medication doses, certain diagnoses, or a patient-reported
  emergency that the doctor never escalates).
* ``strict`` (experiment E3) — additionally removes role-inverted turns,
  leaked planning notes, English code-mixing, weak history taking and
  premature diagnosis in the first reply.

The heuristics are documented in DATASET.md. They are filters for training
data quality, not a clinical review of the synthetic content.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from app.services.dialogue.prompts import CERTAIN_DIAGNOSIS, DISEASE_NAMING, DOSE
from app.triage import find_red_flags

CLEANING_VERSION = "dialogue-clean-v1"
ROLES = {"system", "user", "assistant"}
REASONING_BLOCK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.IGNORECASE | re.DOTALL)
REASONING_PREFIX = re.compile(r"^.*?</(?:think|thinking|reasoning)>", re.IGNORECASE | re.DOTALL)
REASONING_TAG = re.compile(r"</?(?:think|thinking|reasoning)\b[^>]*>", re.IGNORECASE)
VIETNAMESE_CHAR = re.compile(r"[ăâđêôơưàáạảãầấậẩẫằắặẳẵèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]", re.IGNORECASE)

# Doctor-voice text inside a *user* turn (the patient side).
USER_ROLE_INVERSION = re.compile(
    r"\*\*|^\s*(?:[-•]|\d+\.)\s+\S"
    r"|tôi là (?:dr\.? ?)?meddies|(?:con|em|cháu|mình) là (?:dr\.? ?)?meddies|trợ lý ai"
    r"|cảm ơn (?:bác|em|anh|chị|bạn|cô|chú|ông|bà|mai|\w+) đã (?:chia sẻ|cung cấp|tin tưởng)"
    r"|dựa trên (?:những )?(?:gì|thông tin) (?:bác|em|anh|chị|bạn|cô|chú) (?:đã )?(?:chia sẻ|mô tả|cung cấp)"
    r"|(?:chị|anh|tôi|con|cháu) (?:khuyên|đề nghị) (?:em|bạn|bác|anh|chị|cô|chú)",
    re.IGNORECASE | re.MULTILINE,
)
# Patient-voice text inside an *assistant* turn.
ASSISTANT_ROLE_INVERSION = re.compile(
    r"^(?:dạ\s+)?thưa bác sĩ|(?:em|con|cháu|tôi|mình) (?:xin )?cảm ơn bác sĩ|bác sĩ ơi[,!]",
    re.IGNORECASE,
)
# Instructions or meta-commentary of the LLM that simulated the patient.
SIMULATION_ARTIFACT = re.compile(
    r"\bpersona\b|đóng vai (?:một |là )?(?:bệnh nhân|người bệnh)|tôi đã sẵn sàng (?:để )?(?:bắt đầu|trả lời)"
    r"|với vai trò (?:là )?(?:bệnh nhân|người bệnh)|\[(?:bệnh nhân|patient|doctor|bác sĩ)\]|as (?:the|a) patient",
    re.IGNORECASE,
)
PLANNING_NOTES = re.compile(
    r"\b(?:Giai đoạn|Phase(?: Check)?|Mục tiêu tiếp theo|Clinical Logic|FIFE|OPQRST|Red Flags?)\b\s*\**\s*:",
    re.IGNORECASE,
)
ENGLISH_FUNCTION_WORDS = re.compile(
    r"\b(?:the|and|with|which|should|however|because|regularly|patient|please|would|could)\b", re.IGNORECASE
)
URGENT_ADVICE = re.compile(
    r"115|cấp cứu|khám ngay|bệnh viện ngay|đến (?:cơ sở y tế|bệnh viện|phòng khám) (?:ngay|sớm nhất|gần nhất)"
    r"|ngay lập tức|khẩn cấp|càng sớm càng tốt|không nên chờ|ngay bây giờ",
    re.IGNORECASE,
)


def _red_flag_prefilter() -> re.Pattern[str]:
    """One folded regex over every triage phrase; a miss means no red flag."""
    from app.triage import COMBINED_RED_FLAGS, RED_FLAGS, _fold

    phrases = {_fold(phrase) for values in RED_FLAGS.values() for phrase in values}
    phrases |= {_fold(symptom) for _, _, symptoms in COMBINED_RED_FLAGS for symptom in symptoms}
    alternatives = sorted((re.escape(p) for p in phrases), key=len, reverse=True)
    alternatives += [context for _, context, _ in COMBINED_RED_FLAGS]
    return re.compile(r"(?<!\w)(?:" + "|".join(alternatives) + r")(?!\w)")


_RED_FLAG_CANDIDATE = _red_flag_prefilter()
_SENTENCE = re.compile(r"[^.!?\n]+[.!?\n]*")


def has_red_flag(text: str) -> bool:
    """Same decision as triage.find_red_flags, evaluated only on candidate sentences.

    Long patient turns make the full matcher slow; negation scope in the
    matcher never crosses sentence punctuation, so restricting it to the
    sentences that contain a candidate phrase (or a combined-flag context)
    keeps the result while cutting cost by an order of magnitude.
    """
    from app.triage import _fold

    sentences = [s for s in _SENTENCE.findall(text) if _RED_FLAG_CANDIDATE.search(_fold(s))]
    return bool(sentences) and bool(find_red_flags(" ".join(sentences)))


def strip_reasoning(content: str) -> str | None:
    """Remove private reasoning; None when an unmatched reasoning tag remains."""
    value = REASONING_BLOCK.sub("", content)
    value = REASONING_PREFIX.sub("", value)
    if REASONING_TAG.search(value):
        return None
    return unicodedata.normalize("NFC", value).strip()


def clean_structure(messages: Any) -> tuple[list[dict[str, str]] | None, list[str]]:
    """Normalize roles/content and validate turn structure."""
    if not isinstance(messages, list) or not messages:
        return None, ["malformed_messages"]
    cleaned: list[dict[str, str]] = []
    for item in messages:
        if not isinstance(item, Mapping) or item.get("role") not in ROLES or not isinstance(item.get("content"), str):
            return None, ["invalid_role_or_content"]
        content = strip_reasoning(item["content"])
        if content is None:
            return None, ["unclosed_reasoning"]
        if not content:
            return None, ["empty_message"]
        if item["role"] == "system":
            continue  # The training system prompt is injected separately.
        cleaned.append({"role": str(item["role"]), "content": content})
    while cleaned and cleaned[-1]["role"] == "user":
        cleaned.pop()  # A trailing patient turn has no supervised target.
    if any(a["role"] == b["role"] for a, b in zip(cleaned, cleaned[1:])):
        return None, ["consecutive_same_role"]
    users = sum(item["role"] == "user" for item in cleaned)
    assistants = sum(item["role"] == "assistant" for item in cleaned)
    if users < 2 or assistants < 2:
        return None, ["too_few_turns"]
    patient_text = " ".join(item["content"] for item in cleaned if item["role"] == "user")
    letters = sum(char.isalpha() for char in patient_text)
    if letters == 0 or len(VIETNAMESE_CHAR.findall(patient_text)) / letters < 0.05:
        return None, ["not_vietnamese"]
    return cleaned, []


def _first_reply_after_complaint(messages: list[dict[str, str]]) -> str | None:
    seen_user = False
    for item in messages:
        if item["role"] == "user":
            seen_user = True
        elif seen_user:
            return item["content"]
    return None


def safety_reasons(messages: list[dict[str, str]]) -> list[str]:
    reasons = []
    assistant = [item["content"] for item in messages if item["role"] == "assistant"]
    if any(DOSE.search(text) for text in assistant):
        reasons.append("medication_dose")
    if any(CERTAIN_DIAGNOSIS.search(text) for text in assistant):
        reasons.append("certain_diagnosis")
    for index, item in enumerate(messages):
        if item["role"] == "user" and has_red_flag(item["content"]):
            later = [m["content"] for m in messages[index + 1 :] if m["role"] == "assistant"]
            if not any(URGENT_ADVICE.search(text) for text in later):
                reasons.append("emergency_not_escalated")
            break
    return reasons


def strict_reasons(messages: list[dict[str, str]]) -> list[str]:
    reasons = []
    if any(item["role"] == "user" and USER_ROLE_INVERSION.search(item["content"]) for item in messages):
        reasons.append("role_inversion_user")
    if any(item["role"] == "assistant" and ASSISTANT_ROLE_INVERSION.search(item["content"]) for item in messages):
        reasons.append("role_inversion_assistant")
    if any(SIMULATION_ARTIFACT.search(item["content"]) for item in messages):
        reasons.append("simulation_artifact")
    assistant = [item["content"] for item in messages if item["role"] == "assistant"]
    if any(PLANNING_NOTES.search(text) for text in assistant):
        reasons.append("leaked_planning_notes")
    if any(len(ENGLISH_FUNCTION_WORDS.findall(text)) >= 2 for text in assistant):
        reasons.append("code_mixing")
    first = _first_reply_after_complaint(messages)
    if first is not None and "?" not in first:
        reasons.append("no_followup_question")
    if first is not None and DISEASE_NAMING.search(first) and "?" not in first:
        reasons.append("premature_diagnosis")
    # History taking: at least two of the first three replies after the
    # complaint should ask something.
    replies, seen_user = [], False
    for item in messages:
        if item["role"] == "user":
            seen_user = True
        elif seen_user:
            replies.append(item["content"])
    if sum("?" in text for text in replies[:3]) < 2:
        reasons.append("insufficient_history_taking")
    return reasons


def assess_conversation(messages: Any) -> dict[str, Any]:
    """Return cleaned messages plus standard/strict acceptance and reasons."""
    cleaned, structural = clean_structure(messages)
    if cleaned is None:
        return {"messages": None, "standard": False, "strict": False, "reasons": structural}
    standard_reasons = safety_reasons(cleaned)
    strict_only = strict_reasons(cleaned)
    return {
        "messages": cleaned,
        "standard": not standard_reasons,
        "strict": not standard_reasons and not strict_only,
        "reasons": standard_reasons + strict_only,
        "standard_reasons": standard_reasons,
        "strict_reasons": strict_only,
    }
