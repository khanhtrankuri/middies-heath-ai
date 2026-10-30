from __future__ import annotations

import re
from collections.abc import Iterable

from .config import Document, TextChunk
from .normalizer import content_hash, normalize_text

HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+")


def _split_long_block(block: str, limit: int) -> list[str]:
    if len(block) <= limit:
        return [block]
    sentences = SENTENCE_BOUNDARY.split(block)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > limit:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
        while len(current) > limit:
            cut = current.rfind(" ", 0, limit + 1)
            cut = cut if cut >= limit // 2 else limit
            pieces.append(current[:cut].strip())
            current = current[cut:].strip()
    if current:
        pieces.append(current)
    return pieces


def _overlap_tail(text: str, overlap: int) -> str:
    if overlap <= 0 or not text:
        return ""
    tail = text[-overlap:]
    first_space = tail.find(" ")
    if first_space >= 0:
        tail = tail[first_space + 1 :]
    return tail.strip()


def chunk_document(
    document: Document,
    *,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> list[TextChunk]:
    if chunk_size < 100 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Invalid chunk size/overlap")

    blocks: list[str] = []
    for paragraph in re.split(r"\n\s*\n", document.text):
        pending: list[str] = []
        for line in paragraph.splitlines():
            if HEADING.match(line.strip()):
                if pending:
                    blocks.append("\n".join(pending).strip())
                    pending = []
                blocks.append(line.strip())
            elif line.strip():
                pending.append(line.strip())
        if pending:
            blocks.append("\n".join(pending).strip())
    chunks: list[TextChunk] = []
    current = ""
    current_section = document.metadata.section
    chunk_section = current_section

    def emit() -> None:
        nonlocal current, chunk_section
        text = normalize_text(current)
        if not text:
            return
        metadata = document.metadata.model_copy(update={"section": chunk_section})
        identity = "|".join(
            [
                metadata.document_hash,
                str(metadata.page or ""),
                metadata.section or "",
                str(len(chunks)),
                text,
            ]
        )
        chunks.append(TextChunk(chunk_id=content_hash(identity), text=text, metadata=metadata))

    for block in blocks:
        heading = HEADING.match(block.strip())
        if heading:
            if current:
                emit()
                current = ""
            current_section = heading.group(2).strip()
        for piece in _split_long_block(block.strip(), chunk_size):
            candidate = f"{current}\n\n{piece}".strip()
            if current and len(candidate) > chunk_size:
                previous = current
                emit()
                current = _overlap_tail(previous, chunk_overlap)
                chunk_section = current_section
                candidate = f"{current}\n\n{piece}".strip()
                if len(candidate) > chunk_size and current:
                    current = ""
                    candidate = piece
            if not current:
                chunk_section = current_section
            current = candidate
    emit()
    return chunks


def chunk_documents(
    documents: Iterable[Document],
    *,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for document in documents:
        chunks.extend(
            chunk_document(document, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        )
    return chunks


def deduplicate_chunks(chunks: Iterable[TextChunk]) -> tuple[list[TextChunk], int]:
    unique: list[TextChunk] = []
    seen: set[str] = set()
    duplicates = 0
    for chunk in chunks:
        exact_hash = content_hash(normalize_text(chunk.text))
        if exact_hash in seen:
            duplicates += 1
            continue
        seen.add(exact_hash)
        unique.append(chunk)
    return unique, duplicates
