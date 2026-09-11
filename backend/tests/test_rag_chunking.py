from __future__ import annotations

from app.services.rag.chunking import chunk_document, deduplicate_chunks
from app.services.rag.config import Document, DocumentMetadata, TextChunk


def _document(text: str, *, page: int | None = 2) -> Document:
    return Document(
        text=text,
        metadata=DocumentMetadata(
            source_id="source-1",
            title="Reviewed source",
            organization="Authority",
            source_url="https://example.test/source",
            publication_date="2026-01-01",
            jurisdiction="TEST",
            language="en",
            page=page,
            document_hash="a" * 64,
        ),
    )


def test_chunking_retains_page_and_section_without_blind_boundaries() -> None:
    text = "# Overview\n\n" + "First clinical paragraph. " * 12 + "\n\n## Safety\n\n" + (
        "Seek assessment for warning signs. " * 12
    )
    chunks = chunk_document(_document(text), chunk_size=240, chunk_overlap=40)

    assert len(chunks) >= 3
    assert all(item.metadata.page == 2 for item in chunks)
    assert {item.metadata.section for item in chunks} >= {"Overview", "Safety"}
    assert all(len(item.text) <= 240 for item in chunks)


def test_exact_duplicate_chunks_are_removed() -> None:
    metadata = _document("content").metadata
    chunks = [
        TextChunk(chunk_id="1", text="same content", metadata=metadata),
        TextChunk(chunk_id="2", text="same   content", metadata=metadata),
        TextChunk(chunk_id="3", text="different", metadata=metadata),
    ]

    unique, duplicate_count = deduplicate_chunks(chunks)

    assert [item.chunk_id for item in unique] == ["1", "3"]
    assert duplicate_count == 1

