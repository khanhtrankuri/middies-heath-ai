from __future__ import annotations

import asyncio
from pathlib import Path

from app.services.consultation import ConsultationOrchestrator
from app.services.rag.config import DocumentMetadata, RAGConfig, RetrievedChunk
from app.services.rag.service import RAGService


class SpyInference:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    async def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if "Chỉ hỏi 1–2 câu" in messages[0]["content"]:
            return "Triệu chứng bắt đầu từ khi nào và mức độ hiện tại là bao nhiêu trên thang 0–10?"
        return (
            "Thông tin bạn đã cung cấp: đau nửa đầu, buồn nôn và sợ ánh sáng.\n\n"
            "Khả năng có thể liên quan: migraine là một khả năng cần được nhân viên y tế đánh giá, "
            "không phải chẩn đoán. [S1]\n\n"
            "Khi nào cần trợ giúp y tế: đi khám nếu triệu chứng kéo dài hoặc tăng lên; cấp cứu nếu "
            "xuất hiện dấu hiệu nguy hiểm được nêu trong nguồn. [S1]\n\n"
            "Thông tin chỉ để tham khảo, không thay thế khám và chẩn đoán của bác sĩ."
        )


class SpyRAG(RAGService):
    def __init__(self, tmp_path: Path) -> None:
        super().__init__(
            RAGConfig(
                enabled=True,
                index_path=tmp_path,
                embedding_model="test",
                top_k=8,
                final_k=4,
            )
        )
        self.calls: list[list[str]] = []

    async def retrieve_many(self, queries, final_k=None):
        del final_k
        self.calls.append(list(queries))
        return [
            RetrievedChunk(
                chunk_id="migraine-1",
                text="Migraine is a recurring headache disorder with possible nausea and light sensitivity.",
                score=0.95,
                metadata=DocumentMetadata(
                    source_id="fixture-migraine-overview",
                    title="Migraine overview",
                    organization="Test authority",
                    source_url="https://example.test/migraine",
                    section="Overview",
                    document_hash="a" * 64,
                ),
            )
        ]


def test_direct_medical_question_calls_rag_and_passes_context_to_model(tmp_path: Path) -> None:
    inference = SpyInference()
    rag = SpyRAG(tmp_path)
    orchestrator = ConsultationOrchestrator(inference, rag, "spy")

    response = asyncio.run(
        orchestrator.respond([{"role": "user", "content": "Migraine là gì?"}])
    )

    assert response.action == "GROUNDED_ANSWER"
    assert response.grounding_status == "grounded"
    assert response.citations[0].citation_id == "S1"
    assert rag.calls
    assert "NGUỒN THAM KHẢO" in inference.calls[0][1]["content"]
    assert "[S1]" in response.reply


def test_symptom_flow_asks_then_finalizes_with_rag(tmp_path: Path) -> None:
    inference = SpyInference()
    rag = SpyRAG(tmp_path)
    orchestrator = ConsultationOrchestrator(inference, rag, "spy")
    first = [{"role": "user", "content": "Tôi đau nửa đầu bên trái, buồn nôn và sợ ánh sáng."}]

    ask = asyncio.run(orchestrator.respond(first))
    assert ask.action == "ASK_MORE"
    assert ask.citations == []
    assert not rag.calls
    assert len(inference.calls) == 1

    sufficient = [
        *first,
        {"role": "assistant", "content": ask.reply},
        {"role": "user", "content": "Đã kéo dài 2 ngày, mức 7/10, không yếu liệt."},
    ]
    final = asyncio.run(orchestrator.respond(sufficient))

    assert final.action == "FINALIZE"
    assert final.grounding_status == "grounded"
    assert final.patient_state["duration"] == "kéo dài 2 ngày"
    assert final.patient_state["location"] == "nửa đầu"
    assert final.citations
    assert rag.calls
    assert "Thông tin bạn đã cung cấp" in final.reply
    assert "Khả năng có thể liên quan" in final.reply
    assert "Khi nào cần trợ giúp y tế" in final.reply
    assert "Bạn chắc chắn bị migraine" not in final.reply
    assert final.disclaimer


def test_missing_rag_uses_degraded_mode_without_fake_citations(tmp_path: Path) -> None:
    inference = SpyInference()
    rag = RAGService(RAGConfig(enabled=False, index_path=tmp_path))
    rag.load()
    orchestrator = ConsultationOrchestrator(inference, rag, "spy")

    response = asyncio.run(
        orchestrator.respond([{"role": "user", "content": "Migraine là gì?"}])
    )

    assert response.grounding_status == "degraded"
    assert response.citations == []
    assert "không kèm trích dẫn" in response.reply
    assert "[S1]" not in response.reply


def test_uncited_generation_is_not_labeled_grounded(tmp_path: Path) -> None:
    class UncitedInference(SpyInference):
        async def generate(self, messages):
            return "An answer with an invented reference [S99]."

    response = asyncio.run(ConsultationOrchestrator(
        UncitedInference(), SpyRAG(tmp_path), "spy"
    ).respond([{"role": "user", "content": "Migraine là gì?"}]))

    assert response.grounding_status == "degraded"
    assert response.citations == []
    assert "[S99]" not in response.reply
    assert "[S1]" not in response.reply
