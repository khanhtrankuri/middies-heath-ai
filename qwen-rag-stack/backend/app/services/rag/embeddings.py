from __future__ import annotations

import hashlib
import re
import os
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

import numpy as np


def _normalize(vectors: np.ndarray) -> np.ndarray:
    values = np.asarray(vectors, dtype=np.float32)
    if values.ndim != 2:
        raise ValueError("Embeddings must be a two-dimensional matrix")
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return values / norms


class EmbeddingProvider(ABC):
    model_name: str
    dimension: int | None

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> np.ndarray: ...

    @abstractmethod
    def embed_queries(self, texts: Sequence[str]) -> np.ndarray: ...


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Lazy sentence-transformers provider; production defaults to CPU."""

    def __init__(self, model_name: str = "BAAI/bge-m3", device: str = "cpu") -> None:
        if device not in {"cpu", "cuda"}:
            raise ValueError("Embedding device must be 'cpu' or 'cuda'")
        self.model_name = model_name
        self.device = device
        self.dimension: int | None = None
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise RuntimeError(
                    "Install sentence-transformers to use the production embedding provider"
                ) from error
            self._model = SentenceTransformer(
                self.model_name, device=self.device,
                local_files_only=os.getenv("MEDDIES_LOCAL_FILES_ONLY", "false").lower() in {"1", "true", "yes"},
            )
            get_dimension = getattr(self._model, "get_embedding_dimension", None)
            if get_dimension is None:
                get_dimension = self._model.get_sentence_embedding_dimension
            self.dimension = int(get_dimension())
        return self._model

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        if not texts:
            dimension = self.dimension or 0
            return np.empty((0, dimension), dtype=np.float32)
        values = self._load().encode(
            list(texts),
            batch_size=16,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        result = _normalize(values)
        self.dimension = int(result.shape[1])
        return result

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode(texts)

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode(texts)


class DeterministicHashEmbeddingProvider(EmbeddingProvider):
    """Download-free deterministic embedding for tests and local diagnostics only."""

    def __init__(self, dimension: int = 64) -> None:
        if dimension < 8:
            raise ValueError("Deterministic embedding dimension must be at least 8")
        self.model_name = "deterministic-hash-test-v1"
        self.dimension = dimension

    def _encode(self, texts: Sequence[str]) -> np.ndarray:
        matrix = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            tokens = re.findall(r"\w+", text.casefold(), flags=re.UNICODE)
            for token in tokens:
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "little") % self.dimension
                sign = 1.0 if digest[4] & 1 else -1.0
                matrix[row, index] += sign
            if not tokens:
                matrix[row, 0] = 1.0
        return _normalize(matrix)

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode(texts)

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._encode(texts)


def create_embedding_provider(model_name: str, device: str) -> EmbeddingProvider:
    return SentenceTransformerEmbeddingProvider(model_name=model_name, device=device)
