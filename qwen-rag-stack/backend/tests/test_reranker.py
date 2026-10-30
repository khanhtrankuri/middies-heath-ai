from types import SimpleNamespace

import numpy as np
import pytest

from app.services.rag.config import DocumentMetadata, RetrievedChunk
from app.services.rag.reranker import CrossEncoderReranker
from app.services.rag.retriever import Retriever, reciprocal_rank_fusion


def chunk(name, score):
    return RetrievedChunk(
        chunk_id=name,
        text=name,
        score=score,
        metadata=DocumentMetadata(document_hash=name),
    )


def test_cross_encoder_reorders_without_mutating_candidates():
    candidates = [chunk("irrelevant", 0.95), chunk("relevant", 0.65)]
    reranker = CrossEncoderReranker("test")
    reranker._model = SimpleNamespace(predict=lambda pairs, **kw: [-3, 4])
    result = reranker.rerank("query", candidates, 1)
    assert result[0].chunk_id == "relevant"
    assert result[0].score == 4
    assert candidates[1].score == 0.65


def test_cross_encoder_rejects_invalid_scores():
    reranker = CrossEncoderReranker("test")
    reranker._model = SimpleNamespace(predict=lambda pairs, **kw: [float("nan")])
    with pytest.raises(ValueError, match="invalid scores"):
        reranker.rerank("query", [chunk("a", 1)], 1)


def test_reranker_sees_patient_context_in_followup():
    captured = []

    class Ranker:
        def rerank(self, query, chunks, final_k):
            captured.append(query)
            return list(chunks)[:final_k]

    provider = SimpleNamespace(embed_queries=lambda queries: np.ones((len(queries), 2)))
    store = SimpleNamespace(search=lambda vector, k: [chunk("a", 1)])
    result = Retriever(provider, store, Ranker()).retrieve(
        ["2 days", "Main symptom: headache"], candidate_k=8, final_k=4,
    )
    assert len(result) == 1
    assert "headache" in captured[0]


def test_rrf_rewards_chunks_found_by_dense_and_sparse():
    dense = [chunk("dense-only", 0.99), chunk("both", 0.5)]
    sparse = [chunk("both", 20), chunk("sparse-only", 10)]
    fused = reciprocal_rank_fusion([dense, sparse], top_k=3)
    assert fused[0].chunk_id == "both"
