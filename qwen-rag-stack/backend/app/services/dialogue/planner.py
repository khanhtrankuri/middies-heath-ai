"""Intelligent next-question selection.

Decision order (each step only runs if the previous one did not decide):

1. Emergency: if the state already contains an emergency flag, stop asking.
2. Chief complaint: if no symptom has been reported, ask for it.
3. Red-flag priority: when risk cues are present (sudden onset, high severity,
   high fever, pregnancy, infant/elderly, urgent flags) and the profile's
   red-flag screen has not been done, ask it first.
4. Timing first: onset/duration is asked before anything else because it
   determines acuity (and both training data and clinical history-taking start
   with it).
5. Information gain: among the remaining missing core slots, pick the slot
   with the highest ``base_weight + IG_WEIGHT * normalized_IG``.

Information gain is computed over the *knowledge-base candidate set* for the
complaint profile (``knowledge.py``), not over model-generated probabilities.
Candidate weights are ``1 + support score`` — relevance weights, not
calibrated probabilities. For a slot ``s`` whose possible answers are the
feature tokens ``A_s`` mentioned by any candidate:

    IG(s) = H(C) - sum_a P(a) * H(C | a)

where each candidate spreads its mass over the tokens it supports in ``A_s``
(or uniformly over ``A_s`` and "other" if it supports none). Yes/no symptom
questions use a soft binary split (0.9 / 0.1). IG is normalized by H(C).

The planner asks exactly one question per turn and stops once all core slots
are known, after ``MAX_PLANNER_QUESTIONS`` questions, or when the user asks for
an assessment with enough information (see ``state.py``).
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, Field

from .features import feature_label, feature_slot
from .knowledge import Condition, candidates_for
from .lexicon import SLOT_LABELS, fold_aligned
from .profiles import PROFILE_BY_NAME, question_template
from .state import DialogueState

Strategy = Literal[
    "emergency_stop", "chief_complaint", "red_flag_priority", "timing_first",
    "information_gain", "optional_followup", "complete",
]
BASE_WEIGHTS: dict[str, float] = {
    "timing": 1.5, "red_flag_screen": 0.9, "location": 0.8, "severity": 0.7,
    "associated_symptoms": 0.7, "character": 0.6, "triggers": 0.6, "progression": 0.4,
    "relevant_history": 0.4, "medications": 0.35, "allergies": 0.3, "age": 0.3,
}
IG_WEIGHT = 0.6
SOFT_YES, SOFT_NO = 0.9, 0.1


class NextQuestion(BaseModel):
    should_ask: bool
    slot: str | None = None
    slot_label: str | None = None
    text: str | None = None
    strategy: Strategy
    reason: str
    information_gain: float | None = None
    candidate_count: int = 0
    options: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)


def _entropy(weights: list[float]) -> float:
    total = sum(weights)
    if total <= 0:
        return 0.0
    return -sum((w / total) * math.log2(w / total) for w in weights if w > 0)


def _weights(candidates: list[Condition], features: set[str]) -> list[float]:
    return [1.0 + condition.score(features) for condition in candidates]


def categorical_information_gain(
    candidates: list[Condition], features: set[str], slot: str
) -> tuple[float, list[str]]:
    known = {token for token in features if feature_slot(token) == slot}
    answers = sorted({
        token for condition in candidates for token in condition.supports
        if feature_slot(token) == slot and token not in known and not token.startswith(("sym:", "neg:", "dur:"))
    })
    if not answers or len(candidates) < 2:
        return 0.0, answers
    priors = _weights(candidates, features)
    outcomes = answers + ["__other__"]
    # mass[c][a]: how candidate c distributes over answers.
    mass: list[dict[str, float]] = []
    for condition in candidates:
        own = [token for token in answers if token in condition.supports]
        if own:
            mass.append({token: 1 / len(own) for token in own})
        else:
            mass.append({token: 1 / len(outcomes) for token in outcomes})
    total_prior = sum(priors)
    h_before = _entropy(priors)
    expected = 0.0
    for outcome in outcomes:
        joint = [prior * row.get(outcome, 0.0) for prior, row in zip(priors, mass)]
        p_outcome = sum(joint) / total_prior
        if p_outcome > 0:
            expected += p_outcome * _entropy(joint)
    return max(0.0, h_before - expected), answers


def binary_information_gain(candidates: list[Condition], features: set[str], token: str) -> float:
    if len(candidates) < 2:
        return 0.0
    priors = _weights(candidates, features)
    total = sum(priors)
    yes = [prior * (SOFT_YES if token in condition.supports else SOFT_NO) for prior, condition in zip(priors, candidates)]
    no = [prior - y for prior, y in zip(priors, yes)]
    p_yes = sum(yes) / total
    return max(0.0, _entropy(priors) - p_yes * _entropy(yes) - (1 - p_yes) * _entropy(no))


def _symptom_options(candidates: list[Condition], features: set[str], prefix: str) -> list[tuple[str, float]]:
    known = {token.split(":", 1)[1] for token in features if token.startswith(("sym:", "neg:"))}
    tokens = sorted({
        token for condition in candidates for token in condition.supports
        if token.startswith(prefix) and token.split(":", 1)[1] not in known and token != "sym:sot_cao"
    })
    scored = [(token, binary_information_gain(candidates, features, token)) for token in tokens]
    return sorted(scored, key=lambda item: (-item[1], item[0]))


def slot_information_gain(
    slot: str, candidates: list[Condition], features: set[str]
) -> tuple[float, list[str]]:
    if slot == "associated_symptoms":
        scored = _symptom_options(candidates, features, "sym:")
        return (scored[0][1] if scored else 0.0), [token for token, _ in scored[:3]]
    if slot == "relevant_history":
        scored = [(token, binary_information_gain(candidates, features, token)) for token in sorted({
            token for condition in candidates for token in condition.supports if token.startswith("hist:")
        } - features)]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return (scored[0][1] if scored else 0.0), [token for token, _ in scored[:3]]
    if slot in {"location", "character", "triggers", "progression"}:
        return categorical_information_gain(candidates, features, slot)
    return 0.0, []


def _risk_cues(state: DialogueState) -> list[str]:
    cues = []
    features = set(state.features)
    if "onset:sudden" in features:
        cues.append("khởi phát đột ngột")
    if "sym:sot_cao" in features:
        cues.append("sốt cao")
    if state.severity and re.search(r"(?:[7-9]|10)\s*/\s*10|du doi|khong chiu|rat nang", fold_aligned(state.severity.value)):
        cues.append("mức độ nặng")
    if state.pregnancy:
        cues.append("đang mang thai")
    if state.age:
        folded = fold_aligned(state.age.value)
        years = re.search(r"(\d+)\s*(?:nam\s*)?tuoi", folded)
        if re.search(r"thang|ngay|tuan", folded) or (years and (int(years.group(1)) >= 65 or int(years.group(1)) < 2)):
            cues.append("nhóm tuổi nguy cơ")
    if state.urgent_flags:
        cues.append("có dấu hiệu cần khám sớm")
    return cues


def _personalize(text: str, state: DialogueState) -> str:
    if state.subject == "other":
        text = re.sub(r"^Bạn\b", "Người bệnh", text)
        text = re.sub(r"\bbạn\b", "người bệnh", text)
    return text


def _associated_question(options: list[str], state: DialogueState) -> str | None:
    labels = [feature_label(token) for token in options]
    if not labels:
        return None
    joined = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " hoặc " + labels[-1]
    return f"Bạn có kèm theo {joined} không?"


def _question_text(slot: str, state: DialogueState, options: list[str]) -> str:
    profile = PROFILE_BY_NAME[state.profile]
    text = None
    if slot == "associated_symptoms":
        text = _associated_question(options, state)
    elif slot == "relevant_history" and options:
        labels = [feature_label(token).replace("tiền sử ", "") for token in options]
        text = f"Bạn có tiền sử {', '.join(labels)} hoặc bệnh lý nền nào khác không?"
    return _personalize(text or question_template(profile, slot), state)


def select_next_medical_question(
    conversation_history: list[dict[str, str]],
    patient_state: DialogueState,
    *,
    optional_budget: int = 0,
) -> NextQuestion:
    """Choose the single most useful next question, or decide to stop asking.

    `conversation_history` is accepted for API symmetry and to count questions
    already asked; all slot values come from `patient_state`.
    """
    del conversation_history  # state already summarizes the history
    state = patient_state
    if state.emergency_flags:
        return NextQuestion(should_ask=False, strategy="emergency_stop",
                            reason="Có dấu hiệu nguy hiểm: ưu tiên khuyến nghị cấp cứu thay vì tiếp tục hỏi.")
    if state.chief_complaint is None:
        return NextQuestion(
            should_ask=True, slot="chief_complaint", slot_label="triệu chứng chính",
            text=_personalize("Bạn đang gặp triệu chứng gì và triệu chứng đó bắt đầu từ khi nào?", state),
            strategy="chief_complaint", reason="Chưa ghi nhận triệu chứng chính.",
        )
    features = set(state.features)
    candidates = candidates_for(state.profile, features)
    missing = list(state.missing_information)
    if state.conversation_status == "READY_FOR_ASSESSMENT" or not missing:
        asked_optional = sum(state.asked_slots.get(slot, 0) for slot in PROFILE_BY_NAME[state.profile].optional_slots)
        optional = [slot for slot in state.optional_missing if state.asked_slots.get(slot, 0) == 0]
        if optional and asked_optional < optional_budget:
            return _best(optional, state, candidates, features, strategy="optional_followup")
        return NextQuestion(should_ask=False, strategy="complete", candidate_count=len(candidates),
                            reason="Đã đủ thông tin cốt lõi hoặc đạt giới hạn số câu hỏi.")
    # Never re-ask a slot the user was already asked twice without a usable answer.
    missing = [slot for slot in missing if state.asked_slots.get(slot, 0) < 2] or missing
    cues = _risk_cues(state)
    if "red_flag_screen" in missing and cues:
        return NextQuestion(
            should_ask=True, slot="red_flag_screen", slot_label=SLOT_LABELS["red_flag_screen"],
            text=_question_text("red_flag_screen", state, []), strategy="red_flag_priority",
            reason="Có yếu tố nguy cơ (" + ", ".join(cues) + ") nên sàng lọc dấu hiệu nguy hiểm trước.",
            candidate_count=len(candidates),
        )
    if "timing" in missing:
        return NextQuestion(
            should_ask=True, slot="timing", slot_label=SLOT_LABELS["timing"],
            text=_question_text("timing", state, []), strategy="timing_first",
            reason="Thời gian khởi phát quyết định mức độ cấp tính nên được hỏi trước.",
            candidate_count=len(candidates),
        )
    return _best(missing, state, candidates, features, strategy="information_gain")


def _best(
    slots: list[str], state: DialogueState, candidates: list[Condition], features: set[str], *, strategy: Strategy
) -> NextQuestion:
    h_before = _entropy(_weights(candidates, features)) if candidates else 0.0
    scored: list[tuple[float, float, str, list[str]]] = []
    for slot in slots:
        gain, options = slot_information_gain(slot, candidates, features)
        normalized = gain / h_before if h_before > 0 else 0.0
        scored.append((BASE_WEIGHTS.get(slot, 0.3) + IG_WEIGHT * normalized, normalized, slot, options))
    scored.sort(key=lambda item: (-item[0], slots.index(item[2])))
    total, normalized, slot, options = scored[0]
    reason = f"Thông tin còn thiếu có điểm ưu tiên cao nhất ({total:.2f})"
    if normalized > 0:
        reason += f"; giảm bất định chuẩn hóa {normalized:.2f} trên {len(candidates)} tình trạng tham khảo."
    else:
        reason += "; xếp theo trọng số ưu tiên mặc định của mục thông tin."
    return NextQuestion(
        should_ask=True, slot=slot, slot_label=SLOT_LABELS.get(slot, slot),
        text=_question_text(slot, state, options), strategy=strategy,
        reason=reason,
        information_gain=round(normalized, 4), candidate_count=len(candidates),
        options=[feature_label(token) for token in options],
        scores={item[2]: round(item[0], 4) for item in scored},
    )
