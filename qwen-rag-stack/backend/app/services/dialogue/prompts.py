"""Prompts shared by training data, the benchmark and the API question path.

Using one system prompt everywhere keeps the fine-tuned model's training
format identical to the format it sees at evaluation and inference time.
Changing the text requires bumping ``SYSTEM_PROMPT_VERSION`` and re-preparing
the training data.
"""
from __future__ import annotations

import re

from .lexicon import question_topics, split_questions

SYSTEM_PROMPT_VERSION = "consult-vi-v1"
CONSULTATION_SYSTEM_PROMPT = (
    "Bạn là Meddies, trợ lý AI hỗ trợ hỏi bệnh và sàng lọc sức khỏe ban đầu bằng tiếng Việt; "
    "bạn không phải bác sĩ. Hãy thu thập thông tin triệu chứng qua hội thoại: mỗi lượt chỉ hỏi "
    "1–2 câu ngắn về thông tin quan trọng nhất còn thiếu và không hỏi lại điều người bệnh đã nói. "
    "Không khẳng định chẩn đoán, không kê đơn và không đưa liều thuốc. Nếu có dấu hiệu nguy hiểm, "
    "khuyên gọi 115 hoặc đến cơ sở cấp cứu ngay. Khi đã đủ thông tin, tóm tắt những gì người bệnh "
    "cung cấp, nêu các khả năng cần cân nhắc kèm mức độ không chắc chắn và khuyên hướng thăm khám phù hợp."
)

CERTAIN_DIAGNOSIS = re.compile(
    r"(?:bạn|em|anh|chị|bác)\s+(?:chắc chắn|chắc là|đúng là)\s+(?:bị|mắc)|chẩn đoán (?:của bạn|là)"
    r"|tôi khẳng định|you definitely have|your diagnosis is",
    re.I,
)
DOSE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ml|viên|giọt|mg/kg|gói)\b|uống\s+\d+\s+(?:lần|viên)|mỗi\s+\d+\s+(?:giờ|tiếng)",
    re.I,
)
DISEASE_NAMING = re.compile(
    r"(?:có thể|khả năng|nghi ngờ|có lẽ|dấu hiệu của|triệu chứng của|nghĩ đến)\s+(?:là\s+|bạn\s+(?:bị|mắc)\s+|bị\s+|mắc\s+)?"
    r"(?:bệnh|viêm|hội chứng|nhiễm|loét|sỏi|suy|ung thư|rối loạn|thoát vị|trào ngược|cúm|sốt xuất huyết|migraine|đau nửa đầu)",
    re.I,
)


def question_instruction(slot_label: str, template: str) -> str:
    return (
        f"{CONSULTATION_SYSTEM_PROMPT}\n\n"
        f"Lượt này: Chỉ hỏi 1–2 câu ngắn, ưu tiên đúng một câu về: {slot_label}. "
        f"Câu hỏi gợi ý: \"{template}\" (có thể diễn đạt lại cho tự nhiên). "
        "Không nêu tên bệnh, không đưa chẩn đoán, không khuyên dùng thuốc."
    )


def validate_generated_question(reply: str, target_slot: str) -> list[str]:
    """Return the reasons a generated follow-up question is rejected (empty = accepted)."""
    problems = []
    questions = split_questions(reply)
    if not questions:
        problems.append("no_question")
    if len(questions) > 2:
        problems.append("too_many_questions")
    if len(reply) > 450:
        problems.append("too_long")
    if CERTAIN_DIAGNOSIS.search(reply) or DISEASE_NAMING.search(reply):
        problems.append("premature_diagnosis")
    if DOSE.search(reply):
        problems.append("medication_dose")
    if target_slot != "chief_complaint" and questions and target_slot not in question_topics(reply).slots:
        problems.append("off_target")
    return problems
