from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from .chunking import chunk_documents, deduplicate_chunks
from .config import RAGConfig, RetrievedChunk
from .embeddings import EmbeddingProvider, create_embedding_provider
from .loaders import load_knowledge_directory
from .normalizer import content_hash
from .reranker import Reranker
from .retriever import Retriever
from .vector_store import FAISSVectorStore, new_manifest

LOGGER = logging.getLogger(__name__)


class RAGUnavailableError(RuntimeError):
    pass


class RAGService:
    def __init__(
        self,
        config: RAGConfig,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: FAISSVectorStore | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.config = config
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.reranker = reranker
        self.retriever: Retriever | None = None
        self.ready = False
        self.error: str | None = None

    def load(self) -> None:
        if not self.config.enabled:
            self.error = "RAG is disabled by configuration"
            self.ready = False
            return
        try:
            store = self.vector_store or FAISSVectorStore.load(self.config.index_path)
            manifest_model = store.manifest.get("embedding_model")
            if manifest_model and manifest_model != self.config.embedding_model:
                raise ValueError(
                    "RAG embedding model does not match index manifest: "
                    f"{self.config.embedding_model!r} != {manifest_model!r}"
                )
            provider = self.embedding_provider or create_embedding_provider(
                self.config.embedding_model, self.config.embedding_device
            )
            if provider.dimension is None:
                provider.embed_queries(["RAG embedding readiness check"])
            if provider.dimension is not None and provider.dimension != store.dimension:
                raise ValueError("Embedding provider dimension does not match the FAISS index")
            self.vector_store = store
            self.embedding_provider = provider
            self.retriever = Retriever(provider, store, self.reranker)
            self.error = None
            self.ready = True
            LOGGER.info("RAG index loaded with %d chunks", len(store.chunks))
        except Exception as error:
            self.error = str(error)
            self.ready = False
            LOGGER.warning("RAG is not ready: %s", error)

    def _retrieve_sync(
        self, queries: Sequence[str], *, candidate_k: int, final_k: int
    ) -> list[RetrievedChunk]:
        if not self.config.enabled or not self.ready or self.retriever is None:
            raise RAGUnavailableError(self.error or "RAG is not ready")
        return self.retriever.retrieve(
            queries,
            candidate_k=candidate_k,
            final_k=final_k,
        )

    async def retrieve(self, query: str, *, top_k: int = 5) -> list[RetrievedChunk]:
        requested = max(1, min(top_k, self.config.top_k))
        try:
            results = await asyncio.to_thread(
                self._retrieve_sync,
                [query],
                candidate_k=max(self.config.top_k, requested),
                final_k=requested,
            )
        except RAGUnavailableError:
            raise
        except Exception as error:
            self.ready = False
            self.error = f"Retrieval failed: {error}"
            raise RAGUnavailableError("RAG retrieval failed") from error
        self._log_retrieval([query], len(results))
        return results

    async def retrieve_many(
        self, queries: Sequence[str], final_k: int | None = None
    ) -> list[RetrievedChunk]:
        count = final_k or self.config.final_k
        try:
            results = await asyncio.to_thread(
                self._retrieve_sync,
                queries,
                candidate_k=self.config.top_k,
                final_k=min(count, self.config.top_k),
            )
        except RAGUnavailableError:
            raise
        except Exception as error:
            self.ready = False
            self.error = f"Retrieval failed: {error}"
            raise RAGUnavailableError("RAG retrieval failed") from error
        self._log_retrieval(queries, len(results))
        return results

    @staticmethod
    def _log_retrieval(queries: Sequence[str], result_count: int) -> None:
        joined = "\n".join(queries)
        log_content = os.getenv(
            "MEDDIES_LOG_CONTENT", os.getenv("LOG_CONTENT", "false")
        ).strip().lower()
        if log_content in {"1", "true", "yes"}:
            LOGGER.info("RAG retrieval queries=%r result_count=%d", list(queries), result_count)
        else:
            LOGGER.info(
                "RAG retrieval query_hash=%s result_count=%d",
                content_hash(joined)[:12],
                result_count,
            )


def create_rag_service(config: RAGConfig | None = None) -> RAGService:
    return RAGService(config or RAGConfig.from_env())


@dataclass(frozen=True, slots=True)
class IndexBuildStats:
    loaded_records: int
    document_count: int
    duplicate_records: int
    chunk_count: int
    duplicate_chunks: int
    embedding_dimension: int
    output_path: Path


def build_knowledge_index(
    input_path: str | Path,
    output_path: str | Path,
    *,
    config: RAGConfig,
    embedding_provider: EmbeddingProvider | None = None,
    rebuild: bool = False,
) -> IndexBuildStats:
    documents = load_knowledge_directory(input_path)
    if not documents:
        raise ValueError("No supported, non-empty knowledge documents were found")

    unique_records = []
    seen_records: set[tuple[str, int | None, str]] = set()
    for document in documents:
        key = (
            document.metadata.document_hash,
            document.metadata.page,
            document.text,
        )
        if key not in seen_records:
            seen_records.add(key)
            unique_records.append(document)
    duplicate_records = len(documents) - len(unique_records)
    document_hashes = sorted({item.metadata.document_hash for item in unique_records})

    raw_chunks = chunk_documents(
        unique_records,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
    )
    chunks, duplicate_chunks = deduplicate_chunks(raw_chunks)
    if not chunks:
        raise ValueError("Knowledge documents produced no indexable chunks")

    provider = embedding_provider or create_embedding_provider(
        config.embedding_model, config.embedding_device
    )
    batches: list[np.ndarray] = []
    for start in range(0, len(chunks), config.embedding_batch_size):
        batch = chunks[start : start + config.embedding_batch_size]
        batches.append(provider.embed_documents([item.text for item in batch]))
    embeddings = np.concatenate(batches, axis=0)
    corpus_manifest_records = sorted(
        json.dumps(
            {
                "document_hash": item.metadata.document_hash,
                "metadata": item.metadata.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for item in unique_records
    )
    corpus_hash = content_hash("\n".join(corpus_manifest_records))
    manifest = new_manifest(
        embedding_model=provider.model_name,
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        document_count=len(document_hashes),
        chunk_count=len(chunks),
        corpus_hash=corpus_hash,
    )
    store = FAISSVectorStore.from_embeddings(chunks, embeddings, manifest)
    destination = Path(output_path).resolve()
    store.save(destination, rebuild=rebuild)
    return IndexBuildStats(
        loaded_records=len(documents),
        document_count=len(document_hashes),
        duplicate_records=duplicate_records,
        chunk_count=len(chunks),
        duplicate_chunks=duplicate_chunks,
        embedding_dimension=store.dimension,
        output_path=destination,
    )
