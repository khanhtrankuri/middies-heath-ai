from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from .config import RetrievedChunk


class Reranker(ABC):
    @abstractmethod
    def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], final_k: int
    ) -> list[RetrievedChunk]: ...


class ScoreReranker(Reranker):
    """CPU-safe baseline; interface can later host a cross-encoder reranker."""

    def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], final_k: int
    ) -> list[RetrievedChunk]:
        del query
        return sorted(chunks, key=lambda item: (-item.score, item.chunk_id))[:final_k]

