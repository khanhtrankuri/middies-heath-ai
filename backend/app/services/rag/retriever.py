from __future__ import annotations

from collections.abc import Sequence

from .config import RetrievedChunk
from .embeddings import EmbeddingProvider
from .reranker import Reranker, ScoreReranker
from .vector_store import FAISSVectorStore


class Retriever:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: FAISSVectorStore,
        reranker: Reranker | None = None,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.reranker = reranker or ScoreReranker()

    def retrieve(
        self,
        queries: Sequence[str],
        *,
        candidate_k: int,
        final_k: int,
    ) -> list[RetrievedChunk]:
        normalized_queries = [query.strip() for query in queries if query.strip()]
        if not normalized_queries:
            return []
        query_vectors = self.embedding_provider.embed_queries(normalized_queries)
        merged: dict[str, RetrievedChunk] = {}
        for row, query in enumerate(normalized_queries):
            candidates = self.vector_store.search(query_vectors[row : row + 1], candidate_k)
            for candidate in candidates:
                existing = merged.get(candidate.chunk_id)
                if existing is None or candidate.score > existing.score:
                    merged[candidate.chunk_id] = candidate
        ordered = sorted(merged.values(), key=lambda item: (-item.score, item.chunk_id))
        return self.reranker.rerank(normalized_queries[0], ordered, final_k)

