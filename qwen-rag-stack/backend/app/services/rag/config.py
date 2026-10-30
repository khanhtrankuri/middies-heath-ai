from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def _env(*names: str, default: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default


def _boolean(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


class DocumentMetadata(BaseModel):
    """Provenance retained from source metadata; missing values stay null."""

    model_config = ConfigDict(extra="ignore")

    source_id: str | None = None
    title: str | None = None
    organization: str | None = None
    source_url: str | None = None
    publication_date: str | None = None
    jurisdiction: str | None = None
    language: str | None = None
    section: str | None = None
    page: int | None = Field(default=None, ge=1)
    document_hash: str

    @field_validator(
        "source_id",
        "title",
        "organization",
        "source_url",
        "publication_date",
        "jurisdiction",
        "language",
        "section",
        mode="before",
    )
    @classmethod
    def blank_to_none(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class Document(BaseModel):
    text: str = Field(min_length=1)
    metadata: DocumentMetadata


class TextChunk(BaseModel):
    chunk_id: str
    text: str = Field(min_length=1)
    metadata: DocumentMetadata


class RetrievedChunk(TextChunk):
    score: float

    @property
    def title(self) -> str | None:
        return self.metadata.title

    @property
    def organization(self) -> str | None:
        return self.metadata.organization

    @property
    def source_url(self) -> str | None:
        return self.metadata.source_url

    @property
    def section(self) -> str | None:
        return self.metadata.section

    @property
    def page(self) -> int | None:
        return self.metadata.page


class Citation(BaseModel):
    citation_id: str
    source_id: str | None = None
    title: str | None = None
    organization: str | None = None
    source_url: str | None = None
    publication_date: str | None = None
    section: str | None = None
    page: int | None = None
    snippet: str


@dataclass(frozen=True, slots=True)
class RAGConfig:
    enabled: bool
    index_path: Path
    embedding_model: str = "BAAI/bge-m3"
    embedding_device: str = "cpu"
    # top_k remains a compatibility alias for callers predating hybrid retrieval.
    top_k: int = 30
    dense_top_k: int = 30
    sparse_top_k: int = 30
    fusion_top_k: int = 20
    final_k: int = 4
    chunk_size: int = 700
    chunk_overlap: int = 100
    max_context_tokens: int = 4096
    embedding_batch_size: int = 16
    reranker: str = "cross_encoder"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_device: str = "cpu"

    def __post_init__(self) -> None:
        if self.top_k != 30 and self.dense_top_k == 30:
            object.__setattr__(self, "dense_top_k", self.top_k)

    @classmethod
    def from_mapping(
        cls, values: dict[str, Any], *, index_path: str | Path
    ) -> "RAGConfig":
        """Create runtime RAG settings from the ``rag`` section of a YAML config."""
        dense_top_k = int(values.get("dense_top_k", 30))
        config = cls(
            enabled=bool(values.get("enabled", True)),
            index_path=Path(index_path).expanduser().resolve(),
            embedding_model=str(values.get("dense_model", "BAAI/bge-m3")),
            embedding_device=str(values.get("embedding_device", "cpu")),
            top_k=dense_top_k,
            dense_top_k=dense_top_k,
            sparse_top_k=int(values.get("sparse_top_k", 30)),
            fusion_top_k=int(values.get("fusion_top_k", 20)),
            final_k=int(values.get("final_k", 4)),
            reranker=str(values.get("reranker", "cross_encoder")),
            reranker_model=str(values.get("reranker_model", "BAAI/bge-reranker-v2-m3")),
            reranker_device=str(values.get("reranker_device", "cpu")),
        )
        config.validate()
        return config

    @classmethod
    def from_env(cls) -> "RAGConfig":
        raw_path = Path(
            _env(
                "MEDDIES_RAG_INDEX_PATH",
                "INDEX_PATH",
                "MEDDIES_INDEX_PATH",
                default="data/rag_index",
            )
        ).expanduser()
        index_path = raw_path if raw_path.is_absolute() else BACKEND_ROOT / raw_path
        dense_top_k = int(
            _env("MEDDIES_RAG_DENSE_TOP_K", "MEDDIES_RAG_TOP_K", "RAG_TOP_K", default="30")
        )
        config = cls(
            enabled=_boolean(_env("MEDDIES_RAG_ENABLED", "RAG_ENABLED", default="true")),
            index_path=index_path.resolve(),
            embedding_model=_env(
                "MEDDIES_EMBEDDING_MODEL",
                "RAG_EMBEDDING_MODEL",
                "MEDDIES_RAG_EMBEDDING_MODEL",
                default="BAAI/bge-m3",
            ),
            embedding_device=_env(
                "MEDDIES_EMBEDDING_DEVICE",
                "RAG_EMBEDDING_DEVICE",
                "MEDDIES_RAG_EMBEDDING_DEVICE",
                default="cpu",
            ).lower(),
            top_k=dense_top_k,
            dense_top_k=dense_top_k,
            sparse_top_k=int(_env("MEDDIES_RAG_SPARSE_TOP_K", default="30")),
            fusion_top_k=int(_env("MEDDIES_RAG_FUSION_TOP_K", default="20")),
            final_k=int(_env("MEDDIES_RAG_FINAL_K", "RAG_FINAL_K", default="4")),
            chunk_size=int(_env("RAG_CHUNK_SIZE", default="700")),
            chunk_overlap=int(_env("RAG_CHUNK_OVERLAP", default="100")),
            max_context_tokens=int(_env("MEDDIES_MAX_CONTEXT_TOKENS", "RAG_MAX_CONTEXT_TOKENS", default="4096")),
            embedding_batch_size=int(_env("RAG_EMBEDDING_BATCH_SIZE", default="16")),
            reranker=_env("MEDDIES_RAG_RERANKER", default="cross_encoder"),
            reranker_model=_env("MEDDIES_RERANKER_MODEL", default="BAAI/bge-reranker-v2-m3"),
            reranker_device=_env("MEDDIES_RERANKER_DEVICE", default="cpu"),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.reranker not in {"score", "cross_encoder"}:
            raise ValueError("MEDDIES_RAG_RERANKER must be score or cross_encoder")
        if self.reranker_device not in {"cpu", "cuda"}:
            raise ValueError("MEDDIES_RERANKER_DEVICE must be cpu or cuda")
        if self.embedding_batch_size < 1 or self.max_context_tokens < 512:
            raise ValueError("Embedding batch size must be positive and context at least 512")
        if self.embedding_device not in {"cpu", "cuda"}:
            raise ValueError("RAG_EMBEDDING_DEVICE must be 'cpu' or 'cuda'")
        if min(self.dense_top_k, self.sparse_top_k, self.fusion_top_k, self.final_k) < 1:
            raise ValueError("All RAG top-k values must be positive")
        if self.final_k > self.fusion_top_k:
            raise ValueError("RAG_FINAL_K cannot exceed RAG_FUSION_TOP_K")
        if self.chunk_size < 100:
            raise ValueError("RAG_CHUNK_SIZE must be at least 100 characters")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE")
