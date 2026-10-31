"""Related-condition hypotheses from user-reported features.

Output is a short, ranked list of *conditions worth discussing with a
clinician*, each with the user-reported evidence that supports it and the
information that is still missing. There are no percentages: ranking uses the
uncalibrated relevance weights in ``knowledge.py``. The module refuses to
suggest anything until the dialogue state is ready and enough user-reported
evidence matches.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .features import feature_label
from .knowledge import KB_VERSION, Condition, candidates_for
from .lexicon import SLOT_LABELS
from .state import DialogueState

MIN_SCORE = 2.0
MIN_MATCHED_FEATURES = 2
_URGENCY_ORDER = {"routine": 0, "soon": 1, "urgent": 2}
NEXT_ACTIONS = {
    "routine": (
        "Có thể theo dõi tại nhà nếu triệu chứng nhẹ; nên đi khám nếu triệu chứng kéo dài, "
        "tăng dần, tái diễn hoặc xuất hiện dấu hiệu nguy hiểm."
    ),
    "soon": "Nên sắp xếp đi khám trong 1–2 ngày tới để được bác sĩ đánh giá trực tiếp.",
    "urgent": "Nên đi khám trực tiếp ngay trong hôm nay; đến cấp cứu nếu triệu chứng nặng lên.",
}
NOT_A_DIAGNOSIS = (
    "Đây là các khả năng tham khảo dựa trên thông tin bạn cung cấp, không phải chẩn đoán; "
    "chỉ bác sĩ thăm khám trực tiếp mới xác định được nguyên nhân."
)


class CandidateCondition(BaseModel):
    name: str
    supporting_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    explanation: str
    care_level: Literal["routine", "soon", "urgent"]


class Assessment(BaseModel):
    eligible: bool
    candidate_conditions: list[CandidateCondition] = Field(default_factory=list)
    observed_findings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    uncertainty: str
    next_action: str
    method: str = f"rule_based_{KB_VERSION}"
    disclaimer: str = NOT_A_DIAGNOSIS


def _observed(state: DialogueState) -> list[str]:
    findings = [f"Triệu chứng: {', '.join(item.label for item in state.symptoms)}"] if state.symptoms else []
    for label, value in (
        ("Khởi phát", state.onset), ("Thời gian", state.duration), ("Vị trí", state.location),
        ("Mức độ", state.severity), ("Tính chất", state.character), ("Diễn biến", state.progression),
        ("Yếu tố liên quan", state.triggers),
    ):
        if value is not None:
            findings.append(f"{label}: {value.value}")
    if state.negated_symptoms:
        findings.append("Không có: " + ", ".join(item.label for item in state.negated_symptoms))
    return findings


def _candidate(condition: Condition, features: set[str]) -> CandidateCondition:
    matched = [token for token in condition.supports if token in features]
    known_symptoms = {token.split(":", 1)[1] for token in features if token.startswith(("sym:", "neg:"))}
    missing = [
        token for token, weight in sorted(condition.supports.items(), key=lambda item: -item[1])
        if weight >= 0.8 and token not in features
        and not (token.startswith(("sym:", "neg:")) and token.split(":", 1)[1] in known_symptoms)
    ][:3]
    supporting = [f"{feature_label(token)} (bạn cung cấp)" for token in matched]
    missing_labels = [feature_label(token) for token in missing]
    explanation = f"Được nêu vì phù hợp với: {', '.join(feature_label(token) for token in matched)}."
    if missing_labels:
        explanation += f" Chưa xác nhận: {', '.join(missing_labels)}."
    explanation += f" {condition.note}"
    return CandidateCondition(
        name=condition.name, supporting_evidence=supporting, missing_evidence=missing_labels,
        explanation=explanation, care_level=condition.urgency,
    )


def generate_hypotheses(state: DialogueState, *, max_candidates: int = 3) -> Assessment:
    missing = [SLOT_LABELS.get(slot, slot) for slot in state.missing_information + state.optional_missing]
    if state.conversation_status != "READY_FOR_ASSESSMENT":
        return Assessment(
            eligible=False, observed_findings=_observed(state), missing_information=missing,
            uncertainty="Chưa đủ thông tin để gợi ý tình trạng liên quan; hệ thống sẽ tiếp tục hỏi thêm.",
            next_action="Trả lời các câu hỏi bổ sung để có đánh giá phù hợp hơn.",
        )
    features = set(state.features)
    ranked = sorted(
        (
            (condition.score(features), condition)
            for condition in candidates_for(state.profile, features)
        ),
        key=lambda item: (-item[0], item[1].name),
    )
    selected = [
        condition for score, condition in ranked
        if score >= MIN_SCORE and sum(token in features for token in condition.supports) >= MIN_MATCHED_FEATURES
    ][:max_candidates]
    candidates = [_candidate(condition, features) for condition in selected]
    levels = [condition.urgency for condition in selected] + (["urgent"] if state.urgent_flags else [])
    level = max(levels, key=_URGENCY_ORDER.__getitem__) if levels else "routine"
    if candidates:
        uncertainty = (
            "Danh sách được xếp theo mức phù hợp giữa thông tin bạn cung cấp và bảng kiến thức tham khảo; "
            "không có xác suất và không loại trừ các nguyên nhân khác."
        )
    else:
        uncertainty = (
            "Thông tin hiện có chưa đủ đặc hiệu để gợi ý một tình trạng cụ thể; "
            "hệ thống không đoán bệnh khi thiếu căn cứ."
        )
    next_action = NEXT_ACTIONS[level]
    if state.urgent_flags:
        next_action = f"Có dấu hiệu cần khám sớm ({', '.join(state.urgent_flags)}). " + NEXT_ACTIONS["urgent"]
    return Assessment(
        eligible=True, candidate_conditions=candidates, observed_findings=_observed(state),
        missing_information=missing, uncertainty=uncertainty, next_action=next_action,
    )
