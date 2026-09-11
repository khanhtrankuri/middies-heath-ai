from __future__ import annotations

from app.services.rag.citations import (
    build_citations,
    cited_source_ids,
    ensure_at_least_one_citation,
)
from app.services.rag.config import DocumentMetadata, RetrievedChunk


def test_structured_citation_has_provenance_but_no_similarity_score() -> None:
    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        text="Reviewed medical information " * 30,
        score=0.9123,
        metadata=DocumentMetadata(
            source_id="source-1",
            title="Reviewed title",
            organization="Authority",
            source_url="https://example.test/source",
            publication_date="2026-01-01",
            section="Safety",
            page=3,
            document_hash="a" * 64,
        ),
    )

    citation = build_citations([chunk])[0]
    payload = citation.model_dump()

    assert citation.citation_id == "S1"
    assert citation.page == 3
    assert citation.section == "Safety"
    assert "score" not in payload
    assert len(citation.snippet) <= 280


def test_citation_marker_validation_and_safe_append() -> None:
    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        text="Source text",
        score=1.0,
        metadata=DocumentMetadata(document_hash="a" * 64),
    )
    citations = build_citations([chunk])

    answer = ensure_at_least_one_citation("Grounded answer", citations)

    assert cited_source_ids(answer) == {"S1"}
    assert ensure_at_least_one_citation("Already cited [S1].", citations).count("[S1]") == 1
