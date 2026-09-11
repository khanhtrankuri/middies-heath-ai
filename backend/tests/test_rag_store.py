from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path

from app.services.rag.config import DocumentMetadata, RAGConfig, TextChunk
from app.services.rag.embeddings import DeterministicHashEmbeddingProvider
from app.services.rag.service import RAGService, RAGUnavailableError, build_knowledge_index
from app.services.rag.vector_store import FAISSVectorStore, new_manifest


def _chunk(chunk_id: str, text: str, source_id: str) -> TextChunk:
    return TextChunk(
        chunk_id=chunk_id,
        text=text,
        metadata=DocumentMetadata(
            source_id=source_id,
            title=source_id,
            organization="Test authority",
            document_hash=chunk_id * 64,
        ),
    )


def _config(path: Path, *, enabled: bool = True) -> RAGConfig:
    return RAGConfig(
        enabled=enabled,
        index_path=path,
        embedding_model="deterministic-hash-test-v1",
        embedding_device="cpu",
        top_k=3,
        final_k=2,
        chunk_size=200,
        chunk_overlap=20,
        embedding_batch_size=2,
    )


def test_faiss_round_trip_and_retrieval_order(tmp_path: Path) -> None:
    provider = DeterministicHashEmbeddingProvider()
    chunks = [
        _chunk("a", "migraine headache nausea light sensitivity", "migraine"),
        _chunk("b", "influenza cough fever respiratory infection", "influenza"),
        _chunk("c", "ankle sprain rest and rehabilitation", "sprain"),
    ]
    embeddings = provider.embed_documents([item.text for item in chunks])
    manifest = new_manifest(
        embedding_model=provider.model_name,
        chunk_size=200,
        chunk_overlap=20,
        document_count=3,
        chunk_count=3,
        corpus_hash="f" * 64,
    )
    path = tmp_path / "index"
    FAISSVectorStore.from_embeddings(chunks, embeddings, manifest).save(path)

    service = RAGService(_config(path), embedding_provider=provider)
    service.load()
    results = asyncio.run(service.retrieve("migraine headache", top_k=2))

    assert service.ready is True
    assert results[0].metadata.source_id == "migraine"
    assert results[0].score >= results[1].score


def test_disabled_and_missing_index_are_safe(tmp_path: Path) -> None:
    disabled = RAGService(_config(tmp_path / "none", enabled=False))
    disabled.load()
    assert disabled.ready is False
    try:
        asyncio.run(disabled.retrieve("query"))
    except RAGUnavailableError:
        pass
    else:
        raise AssertionError("disabled RAG must not search")

    missing = RAGService(_config(tmp_path / "missing"))
    missing.load()
    assert missing.ready is False
    assert "missing required" in (missing.error or "")


def test_ingestion_deduplicates_exact_documents_and_chunks(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    content = "# Migraine\n\nMigraine headache may include nausea and sensitivity to light."
    (knowledge / "one.md").write_text(content, encoding="utf-8")
    (knowledge / "two.md").write_text(content, encoding="utf-8")
    output = tmp_path / "rag-index"
    provider = DeterministicHashEmbeddingProvider()

    stats = build_knowledge_index(
        knowledge,
        output,
        config=_config(output),
        embedding_provider=provider,
    )

    assert stats.loaded_records == 2
    assert stats.document_count == 1
    assert stats.duplicate_records == 1
    assert stats.chunk_count >= 1
    assert (output / "manifest.json").is_file()
    assert (output / "vectors.faiss").is_file()

