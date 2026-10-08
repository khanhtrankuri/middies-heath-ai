from __future__ import annotations

import re
from collections.abc import Sequence

from .config import Citation, RetrievedChunk


def _snippet(text: str, limit: int = 280) -> str:
    value = " ".join(text.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rsplit(" ", 1)[0] + "…"


def build_citations(chunks: Sequence[RetrievedChunk]) -> list[Citation]:
    citations: list[Citation] = []
    for number, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata
        citations.append(
            Citation(
                citation_id=f"S{number}",
                source_id=metadata.source_id,
                title=metadata.title,
                organization=metadata.organization,
                source_url=metadata.source_url,
                publication_date=metadata.publication_date,
                section=metadata.section,
                page=metadata.page,
                snippet=_snippet(chunk.text),
            )
        )
    return citations


def format_grounding_context(chunks: Sequence[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for number, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata
        blocks.append(
            "\n".join(
                [
                    f"[Source S{number}]",
                    f"Title: {metadata.title or 'null'}",
                    f"Organization: {metadata.organization or 'null'}",
                    f"Source URL: {metadata.source_url or 'null'}",
                    f"Section: {metadata.section or 'null'}",
                    f"Page: {metadata.page if metadata.page is not None else 'null'}",
                    "Content:",
                    chunk.text,
                ]
            )
        )
    return "\n\n".join(blocks)


def cited_source_ids(answer: str) -> set[str]:
    return {match.upper() for match in re.findall(r"\[(S\d+)\]", answer, flags=re.I)}


def remove_unknown_citations(answer: str, citations: Sequence[Citation]) -> str:
    valid = {citation.citation_id.upper() for citation in citations}
    return re.sub(
        r"\[(S\d+)\]",
        lambda match: f"[{match[1].upper()}]" if match[1].upper() in valid else "",
        answer,
        flags=re.I,
    ).strip()


def ensure_at_least_one_citation(answer: str, citations: Sequence[Citation]) -> str:
    if not citations or cited_source_ids(answer):
        return answer.strip()
    return f"{answer.strip()}\n\nNguồn tham khảo: [{citations[0].citation_id}]"
