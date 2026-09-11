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
    top_k: int = 8
    final_k: int = 4
    chunk_size: int = 700
    chunk_overlap: int = 100
    max_context_tokens: int = 4096
    embedding_batch_size: int = 16

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
            top_k=int(_env("MEDDIES_RAG_TOP_K", "RAG_TOP_K", default="8")),
            final_k=int(_env("MEDDIES_RAG_FINAL_K", "RAG_FINAL_K", default="4")),
            chunk_size=int(_env("RAG_CHUNK_SIZE", default="700")),
            chunk_overlap=int(_env("RAG_CHUNK_OVERLAP", default="100")),
            max_context_tokens=int(_env("RAG_MAX_CONTEXT_TOKENS", default="4096")),
            embedding_batch_size=int(_env("RAG_EMBEDDING_BATCH_SIZE", default="16")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.embedding_device not in {"cpu", "cuda"}:
            raise ValueError("RAG_EMBEDDING_DEVICE must be 'cpu' or 'cuda'")
        if self.top_k < 1 or self.final_k < 1:
            raise ValueError("RAG_TOP_K and RAG_FINAL_K must be positive")
        if self.final_k > self.top_k:
            raise ValueError("RAG_FINAL_K cannot exceed RAG_TOP_K")
        if self.chunk_size < 100:
            raise ValueError("RAG_CHUNK_SIZE must be at least 100 characters")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE")
