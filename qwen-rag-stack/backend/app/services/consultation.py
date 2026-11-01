from __future__ import annotations

import os
import re
from pathlib import Path

from app.inference import InferenceManager
from app.models import ConsultationResponse
from app.triage import DISCLAIMER, emergency_reply, find_red_flags

from .dialogue import (
    DialogueState,
    check_scope,
    extract_dialogue_state,
    generate_hypotheses,
    select_next_medical_question,
)
from .dialogue.question_generator import generate_question
from .dialogue.prompts import CERTAIN_DIAGNOSIS, DOSE
from .prompt_boundary import INPUT_POLICY, inference_messages
from .rag.citations import build_citations, cited_source_ids, format_grounding_context, remove_unknown_citations
from .rag.context_budget import select_chunks_within_budget, trim_conversation
from .rag.query_builder import (
    ConsultationIntent,
    build_queries,
    classify_intent,
    patient_state_from_messages,
)
from .rag.service import RAGService, RAGUnavailableError

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "grounded_answer.txt"
DEGRADED_PROMPT = """Bạn là MedAI, trợ lý sàng lọc sức khỏe ban đầu. Hệ thống truy xuất nguồn
y khoa hiện không sẵn sàng. Không đưa dữ kiện y khoa chi tiết như thể đã được kiểm chứng, không
tạo trích dẫn, không khẳng định chẩn đoán. Hãy nêu rõ giới hạn, tập trung vào thu thập thông tin,
dấu hiệu nguy hiểm và khuyến nghị liên hệ nhân viên y tế khi phù hợp."""
LIMITATIONS = [
    "Nguyên mẫu nghiên cứu, chưa được chứng nhận sử dụng lâm sàng.",
    "Kết quả chỉ mang tính tham khảo, không phải chẩn đoán và không thay thế thăm khám của bác sĩ.",
    "Trạng thái hội thoại và danh sách khả năng liên quan được tạo bằng luật tham khảo chưa được chuyên gia y tế thẩm định.",
    "Hệ thống chỉ dựa trên thông tin bạn cung cấp; không có khám thực thể hoặc xét nghiệm.",
]


def _grounded_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _remove_certain_diagnosis(answer: str) -> str:
    patterns = (
        r"(?i)\bbạn chắc chắn (?:bị|mắc)\b",
        r"(?i)\bchẩn đoán của bạn là\b",
        r"(?i)\bkhẳng định bạn (?:bị|mắc)\b",
    )
    value = answer
    for pattern in patterns:
        value = re.sub(pattern, "không thể khẳng định bạn bị", value)
    return value.strip()


def _optional_budget() -> int:
    try:
        return max(0, int(os.getenv("MEDDIES_OPTIONAL_QUESTIONS", "0")))
    except ValueError:
        return 0


class ConsultationOrchestrator:
    """User message → safety → scope → state → next question or assessment."""

    def __init__(
        self,
        inference: InferenceManager,
        rag: RAGService,
        provider_name: str,
    ) -> None:
        self.inference = inference
        self.rag = rag
        self.provider_name = provider_name

    def _response(self, state: DialogueState, **values: object) -> ConsultationResponse:
        """Attach the structured dialogue fields shared by every action."""
        values.setdefault("provider", self.provider_name)
        values.setdefault("disclaimer", DISCLAIMER)
        values.setdefault("model_identity", getattr(self.inference, "identity", {"provider": self.provider_name}))
        return ConsultationResponse(
            dialogue_state=state.model_dump(mode="json"),
            missing_information=state.missing_information_labels,
            emergency_flags=list(state.emergency_flags),
            limitations=LIMITATIONS,
            **values,
        )

    async def _degraded_answer(
        self, messages: list[dict[str, str]], action: str, patient_state: dict[str, object],
        state: DialogueState, assessment: dict | None,
    ) -> ConsultationResponse:
        allow_ungrounded = os.getenv("MEDDIES_ALLOW_UNGROUNDED", "false").lower() in {"1", "true", "yes"}
        generated = allow_ungrounded or self.provider_name == "stub"
        if generated:
            reply = await self.inference.generate(
                inference_messages(DEGRADED_PROMPT, trim_conversation(messages))
            )
        else:
            reply = (
                "Tôi chưa có nguồn tham khảo phù hợp để trả lời câu hỏi này. "
                "Tôi không thể kết luận nguyên nhân hoặc đề xuất điều trị từ thông tin hiện có. "
                "Bạn nên trao đổi với nhân viên y tế để được đánh giá phù hợp."
            )
        if DOSE.search(reply) or CERTAIN_DIAGNOSIS.search(reply):
            reply = "Không thể kết luận hoặc đề xuất điều trị từ thông tin hiện có. Hãy trao đổi với nhân viên y tế."
        notice = (
            "Nguồn y khoa tham khảo hiện chưa sẵn sàng; phần trả lời này có mức độ "
            "kiểm chứng thấp hơn và không kèm trích dẫn."
        )
        return self._response(
            state,
            reply=f"{remove_unknown_citations(_remove_certain_diagnosis(reply), [])}\n\n{notice}",
            provider=self.provider_name if generated else "planner-template",
            action=action,
            grounding_status="degraded",
            citations=[],
            patient_state=patient_state,
            assessment=assessment,
        )

    async def _ask(
        self, messages: list[dict[str, str]], state: DialogueState, patient_state: dict[str, object]
    ) -> ConsultationResponse:
        decision = select_next_medical_question(messages, state, optional_budget=_optional_budget())
        result = await generate_question(
            self.inference, messages, state, decision,
            allow_degraded=os.getenv("MEDDIES_ALLOW_TEMPLATE_FALLBACK", "false").lower() in {"1", "true", "yes"},
        )
        rendered = decision.model_dump(mode="json")
        rendered["text"] = result.text
        return self._response(
            state,
            reply=result.text,
            provider="planner-template" if result.source == "template" else self.provider_name,
            action="ASK_MORE",
            grounding_status="not_used",
            citations=[],
            patient_state=patient_state,
            next_question=rendered,
            question_source=result.source,
            model_validation=result.validation,
        )

    async def respond(self, messages: list[dict[str, str]]) -> ConsultationResponse:
        legacy_state = patient_state_from_messages(messages)
        patient_state = legacy_state.model_dump(mode="json")
        state = extract_dialogue_state(messages)
        # Never let negation or an educational question in another turn erase
        # a reported emergency. Assistant text is deliberately excluded.
        red_flags = list(dict.fromkeys(
            [flag for item in messages if item.get("role") == "user" for flag in find_red_flags(item["content"])]
            + state.emergency_flags
        ))
        if red_flags:
            state.emergency_flags = red_flags
            state.conversation_status = "EMERGENCY"
            country = os.getenv(
                "MEDDIES_EMERGENCY_COUNTRY", os.getenv("EMERGENCY_COUNTRY", "VN")
            )
            phone = os.getenv(
                "MEDDIES_EMERGENCY_PHONE", os.getenv("EMERGENCY_PHONE", "115")
            )
            return self._response(
                state,
                reply=emergency_reply(red_flags, country, phone),
                provider="safety-router",
                action="EMERGENCY",
                grounding_status="not_used",
                citations=[],
                patient_state=patient_state,
            )

        latest_user = next(
            item["content"] for item in reversed(messages) if item.get("role") == "user"
        )
        scope = check_scope(latest_user)
        if not scope.in_scope:
            state.conversation_status = "OUT_OF_SCOPE"
            return self._response(
                state,
                reply=scope.reply or "",
                provider="domain-guardrail",
                action="OUT_OF_SCOPE",
                grounding_status="not_used",
                citations=[],
                patient_state=patient_state,
            )

        intent = classify_intent(messages)
        assessment = None
        if intent == ConsultationIntent.SYMPTOM_CONSULTATION:
            decision = select_next_medical_question(messages, state, optional_budget=_optional_budget())
            if decision.should_ask:
                return await self._ask(messages, state, patient_state)
            assessment = generate_hypotheses(state).model_dump(mode="json")
            if state.unable_to_continue or not assessment["eligible"]:
                assessment["uncertainty"] = "Chưa đủ thông tin để xác định nguyên nhân hoặc gợi ý bệnh cụ thể."
                assessment["next_action"] = "Có thể dừng trao đổi và liên hệ nhân viên y tế để được đánh giá trực tiếp."
                return self._response(
                    state, action="FINALIZE", provider="planner-template", grounding_status="not_used",
                    reply="Chưa đủ thông tin để xác định nguyên nhân. Bạn có thể dừng trao đổi và liên hệ nhân viên y tế để được đánh giá trực tiếp.",
                    patient_state=patient_state, assessment=assessment,
                )
        else:
            state.conversation_status = "INFORMATION_REQUEST"

        queries = build_queries(
            latest_user,
            legacy_state if intent == ConsultationIntent.SYMPTOM_CONSULTATION else None,
        )
        action = (
            "GROUNDED_ANSWER"
            if intent == ConsultationIntent.MEDICAL_INFORMATION
            else "FINALIZE"
        )
        patient_summary = state.concise_summary() if intent == ConsultationIntent.SYMPTOM_CONSULTATION else ""
        try:
            chunks = await self.rag.retrieve_many(queries)
            chunks = [chunk for chunk in chunks if
                      chunk.metadata.review_status in {"source_checked", "clinician_reviewed"}
                      and chunk.metadata.source_url and chunk.metadata.source_version
                      and chunk.metadata.reviewed_by and chunk.metadata.reviewed_at]
            budgeted_messages = trim_conversation(messages)
            selected = select_chunks_within_budget(
                chunks,
                system_prompt=f"{_grounded_prompt()}\n\n{INPUT_POLICY}",
                messages=budgeted_messages,
                patient_summary=patient_summary,
                max_context_tokens=self.rag.config.max_context_tokens,
            )
            if not selected:
                raise RAGUnavailableError("No retrieved chunk fits the context budget")
        except RAGUnavailableError:
            return await self._degraded_answer(messages, action, patient_state, state, assessment)

        citations = build_citations(selected)
        context = format_grounding_context(selected)
        grounded_messages = inference_messages(
            _grounded_prompt(), budgeted_messages,
            patient_summary=patient_summary, context=context,
        )
        reply = await self.inference.generate(grounded_messages)
        if DOSE.search(reply) or CERTAIN_DIAGNOSIS.search(reply):
            return self._response(state, action=action, provider="safety-validator", grounding_status="degraded",
                                  patient_state=patient_state, assessment=assessment,
                                  reply="Không thể cung cấp chẩn đoán xác định hoặc liều thuốc qua hội thoại. Hãy trao đổi với nhân viên y tế để được đánh giá phù hợp.", citations=[])
        reply = remove_unknown_citations(_remove_certain_diagnosis(reply), citations)
        used_ids = cited_source_ids(reply)
        citations = [citation for citation in citations if citation.citation_id in used_ids]
        if not citations:
            reply += "\n\nCâu trả lời chưa liên kết được với nguồn tham khảo; không thể xác nhận mức độ kiểm chứng."
        return self._response(
            state,
            reply=reply,
            action=action,
            grounding_status="grounded" if citations else "degraded",
            citations=citations,
            patient_state=patient_state,
            assessment=assessment,
        )
