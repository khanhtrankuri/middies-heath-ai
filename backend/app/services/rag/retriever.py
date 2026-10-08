from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from .config import RetrievedChunk
from .embeddings import EmbeddingProvider
from .reranker import Reranker
from .sparse import BM25Retriever
from .vector_store import FAISSVectorStore


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[RetrievedChunk]], *, top_k: int, rank_constant: int = 60
) -> list[RetrievedChunk]:
    scores: dict[str, float] = defaultdict(float)
    chunks: dict[str, RetrievedChunk] = {}
    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            scores[chunk.chunk_id] += 1.0 / (rank_constant + rank)
            chunks[chunk.chunk_id] = chunk
    fused = [chunk.model_copy(update={"score": scores[chunk_id]}) for chunk_id, chunk in chunks.items()]
    return sorted(fused, key=lambda item: (-item.score, item.chunk_id))[:top_k]


class Retriever:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: FAISSVectorStore,
        reranker: Reranker,
        sparse_retriever: BM25Retriever | None = None,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.reranker = reranker
        chunks = getattr(vector_store, "chunks", [])
        self.sparse_retriever = sparse_retriever or BM25Retriever(chunks)

    def retrieve(
        self,
        queries: Sequence[str],
        *,
        candidate_k: int | None = None,
        final_k: int,
        dense_top_k: int | None = None,
        sparse_top_k: int | None = None,
        fusion_top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        normalized_queries = [query.strip() for query in queries if query.strip()]
        if not normalized_queries:
            return []
        dense_k = dense_top_k or candidate_k or 30
        sparse_k = sparse_top_k or candidate_k or 30
        fusion_k = fusion_top_k or candidate_k or 20
        query_vectors = self.embedding_provider.embed_queries(normalized_queries)
        rankings: list[list[RetrievedChunk]] = []
        for row, query in enumerate(normalized_queries):
            rankings.append(self.vector_store.search(query_vectors[row : row + 1], dense_k))
            sparse = self.sparse_retriever.search(query, sparse_k)
            if sparse:
                rankings.append(sparse)
        fused = reciprocal_rank_fusion(rankings, top_k=fusion_k)
        # Follow-up messages may only say "2 days"; include patient context in reranking.
        return self.reranker.rerank("\n".join(normalized_queries), fused, final_k)
