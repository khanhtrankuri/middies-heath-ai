from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
import math
import os
import threading
from typing import Any

from .config import RetrievedChunk


class Reranker(ABC):
    @abstractmethod
    def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], final_k: int
    ) -> list[RetrievedChunk]: ...


class ScoreReranker(Reranker):
    """Deterministic test/compatibility ranker; production defaults to cross-encoder."""

    def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], final_k: int
    ) -> list[RetrievedChunk]:
        del query
        return sorted(chunks, key=lambda item: (-item.score, item.chunk_id))[:final_k]


class CrossEncoderReranker(Reranker):
    """Optional multilingual second pass. CPU keeps VRAM available for Qwen."""

    def __init__(self, model_name: str, device: str = "cpu", batch_size: int = 4) -> None:
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self._model: Any = None
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            if self._model is None:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(
                    self.model_name, device=self.device, max_length=512,
                    local_files_only=os.getenv("MEDDIES_LOCAL_FILES_ONLY", "false").lower() in {"1", "true", "yes"},
                )

    def rerank(
        self, query: str, chunks: Sequence[RetrievedChunk], final_k: int
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        self.load()
        with self._lock:
            scores = self._model.predict(
                [(query, chunk.text) for chunk in chunks],
                batch_size=self.batch_size,
                show_progress_bar=False,
            )
        if len(scores) != len(chunks) or any(not math.isfinite(float(s)) for s in scores):
            raise ValueError("Reranker returned invalid scores")
        ranked = [chunk.model_copy(update={"score": float(score)}) for chunk, score in zip(chunks, scores)]
        return sorted(ranked, key=lambda item: (-item.score, item.chunk_id))[:final_k]


def create_reranker(config) -> Reranker:
    if config.reranker == "score":
        return ScoreReranker()
    if config.reranker != "cross_encoder":
        raise ValueError("Unknown RAG reranker")
    reranker = CrossEncoderReranker(config.reranker_model, config.reranker_device)
    reranker.load()
    return reranker
