from __future__ import annotations

import re
import unicodedata
from enum import StrEnum

from pydantic import BaseModel, Field
from app.triage import is_information_question, symptom_present


class ConsultationIntent(StrEnum):
    MEDICAL_INFORMATION = "medical_information"
    SYMPTOM_CONSULTATION = "symptom_consultation"


class PatientState(BaseModel):
    chief_complaint: str | None = None
    location: str | None = None
    duration: str | None = None
    severity: str | None = None
    associated_symptoms: list[str] = Field(default_factory=list)
    age: str | None = None
    medications: list[str] = Field(default_factory=list)
    relevant_history: list[str] = Field(default_factory=list)

    @property
    def sufficient_for_grounding(self) -> bool:
        return bool(self.chief_complaint and self.duration)

    def concise_summary(self) -> str:
        fields = [
            ("Triệu chứng chính", self.chief_complaint),
            ("Vị trí", self.location),
            ("Thời gian", self.duration),
            ("Mức độ", self.severity),
            ("Tuổi", self.age),
            (
                "Triệu chứng kèm",
                ", ".join(self.associated_symptoms) if self.associated_symptoms else None,
            ),
        ]
        return "; ".join(f"{label}: {value}" for label, value in fields if value)


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def classify_intent(messages: list[dict[str, str]]) -> ConsultationIntent:
    user_messages = [item["content"] for item in messages if item.get("role") == "user"]
    latest = _fold(user_messages[-1]) if user_messages else ""
    if user_messages and is_information_question(user_messages[-1]):
        return ConsultationIntent.MEDICAL_INFORMATION
    direct_patterns = (
        " la gi",
        "what is",
        "thong tin ve",
        "giai thich",
        "nguyen nhan cua",
        "trieu chung cua",
        "phong ngua",
        "co tac dung gi",
    )
    symptom_patterns = ("toi bi", "minh bi", "toi dang", "dau ", "sot", "ho ")
    if any(pattern in f" {latest}" for pattern in direct_patterns) and not any(
        pattern in latest for pattern in symptom_patterns[:3]
    ):
        return ConsultationIntent.MEDICAL_INFORMATION
    return ConsultationIntent.SYMPTOM_CONSULTATION


def patient_state_from_messages(messages: list[dict[str, str]]) -> PatientState:
    user_messages = [item["content"].strip() for item in messages if item.get("role") == "user"]
    if not user_messages:
        return PatientState()
    combined = " ".join(user_messages)
    # Age is not symptom duration ("bé 2 tháng tuổi"). Keep original indices.
    age_match = re.search(r"\b\d+\s*(?:(?:tháng|thang|năm|nam)\s*)?(?:tuổi|tuoi|years? old|months? old)\b", combined, re.I)
    duration_text = re.sub(
        r"\b\d+\s*(?:(?:tháng|thang|năm|nam)\s*)?(?:tuổi|tuoi|years? old|months? old)\b",
        lambda match: " " * len(match.group(0)), combined, flags=re.I,
    )
    duration_match = re.search(
        r"\b(?:khoảng\s+|được\s+|kéo dài\s+|dưới\s+|trên\s+)?\d+(?:\s*[-–]\s*\d+)?\s*(?:phút|giờ|ngày|tuần|tháng|năm|phut|gio|ngay|tuan|thang|nam|minutes?|hours?|days?|weeks?|months?|years?)\b"
        r"|\b(?:hôm nay|hôm qua|vài ngày|mấy ngày|hom nay|hom qua|vai ngay|today|yesterday)\b",
        duration_text,
        flags=re.IGNORECASE,
    )
    severity_match = re.search(r"\b(?:mức\s*)?\d{1,2}\s*/\s*10\b", combined, re.IGNORECASE)
    location_match = re.search(
        r"\b(?:bên trái|bên phải|nửa đầu|vùng trán|sau gáy|thượng vị|bụng dưới)\b",
        combined,
        re.IGNORECASE,
    )
    associated_terms = [
        term
        for term in (
            "buồn nôn",
            "nôn",
            "sợ ánh sáng",
            "chóng mặt",
            "sốt",
            "khó thở",
            "đau ngực",
        )
        if symptom_present(combined, term)
    ]
    return PatientState(
        chief_complaint=user_messages[0],
        location=location_match.group(0) if location_match else None,
        duration=duration_match.group(0) if duration_match else None,
        severity=severity_match.group(0) if severity_match else None,
        age=age_match.group(0) if age_match else None,
        associated_symptoms=associated_terms,
    )


def build_queries(query: str, patient_state: PatientState | None = None) -> list[str]:
    base = " ".join(query.split())
    queries = [base]
    if patient_state and patient_state.chief_complaint:
        summary = patient_state.concise_summary()
        queries.append(f"{summary}. Nguyên nhân thường gặp và hướng xử trí ban đầu")
        queries.append(f"{summary}. Dấu hiệu cảnh báo cần đi khám hoặc cấp cứu")
    return list(dict.fromkeys(item for item in queries if item))
