from __future__ import annotations

import os
import re
from pathlib import Path

from app.inference import InferenceManager
from app.models import ConsultationResponse
from app.triage import DISCLAIMER, find_red_flags

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


class ConsultationOrchestrator:
    def __init__(
        self,
        inference: InferenceManager,
        rag: RAGService,
        provider_name: str,
    ) -> None:
        self.inference = inference
        self.rag = rag
        self.provider_name = provider_name

    async def _degraded_answer(
        self, messages: list[dict[str, str]], action: str, patient_state: dict[str, object]
    ) -> ConsultationResponse:
        allow_ungrounded = os.getenv("MEDDIES_ALLOW_UNGROUNDED", "false").lower() in {"1", "true", "yes"}
        if allow_ungrounded or self.provider_name == "stub":
            reply = await self.inference.generate(
                inference_messages(DEGRADED_PROMPT, trim_conversation(messages))
            )
        else:
            reply = (
                "Tôi chưa có nguồn tham khảo phù hợp để trả lời câu hỏi này. "
                "Tôi không thể kết luận nguyên nhân hoặc đề xuất điều trị từ thông tin hiện có. "
                "Bạn nên trao đổi với nhân viên y tế để được đánh giá phù hợp."
            )
        notice = (
            "Nguồn y khoa tham khảo hiện chưa sẵn sàng; phần trả lời này có mức độ "
            "kiểm chứng thấp hơn và không kèm trích dẫn."
        )
        return ConsultationResponse(
            reply=f"{remove_unknown_citations(_remove_certain_diagnosis(reply), [])}\n\n{notice}",
            provider=self.provider_name,
            action=action,
            grounding_status="degraded",
            citations=[],
            patient_state=patient_state,
            disclaimer=DISCLAIMER,
        )

    async def respond(self, messages: list[dict[str, str]]) -> ConsultationResponse:
        state = patient_state_from_messages(messages)
        state_payload = state.model_dump(mode="json")
        # Never let negation or an educational question in another turn erase
        # a reported emergency. Assistant text is deliberately excluded.
        red_flags = list(dict.fromkeys(
            flag for item in messages if item.get("role") == "user"
            for flag in find_red_flags(item["content"])
        ))
        if red_flags:
            country = os.getenv(
                "MEDDIES_EMERGENCY_COUNTRY", os.getenv("EMERGENCY_COUNTRY", "VN")
            )
            phone = os.getenv(
                "MEDDIES_EMERGENCY_PHONE", os.getenv("EMERGENCY_PHONE", "115")
            )
            return ConsultationResponse(
                reply=(
                    "Mô tả có dấu hiệu có thể cần đánh giá khẩn cấp: "
                    f"{', '.join(red_flags)}. Nếu bạn ở {country}, hãy gọi {phone} hoặc đến "
                    "cơ sở cấp cứu gần nhất ngay; không chờ tư vấn trực tuyến."
                ),
                provider="safety-router",
                action="EMERGENCY",
                grounding_status="not_used",
                citations=[],
                patient_state=state_payload,
                disclaimer=DISCLAIMER,
            )

        intent = classify_intent(messages)
        if intent == ConsultationIntent.SYMPTOM_CONSULTATION and not state.sufficient_for_grounding:
            question_prompt = (
                "Bạn là MedAI. Chỉ hỏi 1–2 câu ngắn để thu thập dữ liệu triệu chứng còn thiếu "
                "(ưu tiên thời gian, mức độ, vị trí, triệu chứng kèm và dấu hiệu nguy hiểm). "
                "Không đưa chẩn đoán, dữ kiện y khoa hoặc trích dẫn. Không lặp lại câu đã được trả lời.\n\n"
                "Nếu thiếu thời gian khởi phát, BẮT BUỘC hỏi triệu chứng bắt đầu từ khi nào hoặc kéo dài bao lâu."
            )
            reply = await self.inference.generate(
                inference_messages(question_prompt, trim_conversation(messages), patient_summary=state.concise_summary())
            )
            if not state.duration and not re.search(
                r"bắt đầu|từ khi|bao lâu|kéo dài|thời gian|when|how long", reply, re.I
            ):
                reply = "Triệu chứng bắt đầu từ khi nào và kéo dài bao lâu?"
            return ConsultationResponse(
                reply=_remove_certain_diagnosis(reply),
                provider=self.provider_name,
                action="ASK_MORE",
                grounding_status="not_used",
                citations=[],
                patient_state=state_payload,
                disclaimer=DISCLAIMER,
            )

        latest_user = next(
            item["content"] for item in reversed(messages) if item.get("role") == "user"
        )
        queries = build_queries(
            latest_user,
            state if intent == ConsultationIntent.SYMPTOM_CONSULTATION else None,
        )
        action = (
            "GROUNDED_ANSWER"
            if intent == ConsultationIntent.MEDICAL_INFORMATION
            else "FINALIZE"
        )
        try:
            chunks = await self.rag.retrieve_many(queries)
            budgeted_messages = trim_conversation(messages)
            selected = select_chunks_within_budget(
                chunks,
                system_prompt=f"{_grounded_prompt()}\n\n{INPUT_POLICY}",
                messages=budgeted_messages,
                patient_summary=state.concise_summary(),
                max_context_tokens=self.rag.config.max_context_tokens,
            )
            if not selected:
                raise RAGUnavailableError("No retrieved chunk fits the context budget")
        except RAGUnavailableError:
            return await self._degraded_answer(messages, action, state_payload)

        citations = build_citations(selected)
        context = format_grounding_context(selected)
        grounded_messages = inference_messages(
            _grounded_prompt(), budgeted_messages,
            patient_summary=state.concise_summary(), context=context,
        )
        reply = await self.inference.generate(grounded_messages)
        reply = remove_unknown_citations(_remove_certain_diagnosis(reply), citations)
        used_ids = cited_source_ids(reply)
        citations = [citation for citation in citations if citation.citation_id in used_ids]
        if not citations:
            reply += "\n\nCâu trả lời chưa liên kết được với nguồn tham khảo; không thể xác nhận mức độ kiểm chứng."
        return ConsultationResponse(
            reply=reply,
            provider=self.provider_name,
            action=action,
            grounding_status="grounded" if citations else "degraded",
            citations=citations,
            patient_state=state_payload,
            disclaimer=DISCLAIMER,
        )
