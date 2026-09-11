from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .config import Document, DocumentMetadata
from .normalizer import content_hash, normalize_text, normalized_hash

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".json", ".html", ".htm", ".pdf"}
METADATA_FIELDS = {
    "source_id",
    "title",
    "organization",
    "source_url",
    "publication_date",
    "jurisdiction",
    "language",
    "section",
    "page",
}


def _sidecar_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".metadata.json")


def _read_sidecar(path: Path) -> dict[str, Any]:
    sidecar = _sidecar_path(path)
    if not sidecar.exists():
        return {}
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Metadata sidecar must contain an object: {sidecar}")
    return {key: payload.get(key) for key in METADATA_FIELDS if key in payload}


def _metadata(values: dict[str, Any], document_hash: str, **overrides: Any) -> DocumentMetadata:
    merged = {key: values.get(key) for key in METADATA_FIELDS}
    for key, value in overrides.items():
        if value is not None:
            merged[key] = value
    merged["document_hash"] = document_hash
    return DocumentMetadata.model_validate(merged)


def _plain_document(path: Path) -> list[Document]:
    raw = path.read_bytes()
    text = normalize_text(raw.decode("utf-8-sig"))
    if not text:
        return []
    return [Document(text=text, metadata=_metadata(_read_sidecar(path), content_hash(raw)))]


def _html_document(path: Path) -> list[Document]:
    try:
        from bs4 import BeautifulSoup
    except ImportError as error:
        raise RuntimeError("Install beautifulsoup4 to ingest HTML documents") from error

    raw = path.read_bytes()
    soup = BeautifulSoup(raw, "html.parser")
    for node in soup(["script", "style", "noscript", "svg"]):
        node.decompose()
    title_node = soup.find("title")
    extracted_title = normalize_text(title_node.get_text(" ")) if title_node else None
    blocks: list[str] = []
    for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
        value = normalize_text(node.get_text(" ", strip=True))
        if not value:
            continue
        if node.name and node.name.startswith("h"):
            level = min(int(node.name[1]), 6)
            value = f"{'#' * level} {value}"
        blocks.append(value)
    text = normalize_text("\n\n".join(blocks))
    if not text:
        return []
    sidecar = _read_sidecar(path)
    return [
        Document(
            text=text,
            metadata=_metadata(
                sidecar,
                content_hash(raw),
                title=sidecar.get("title") or extracted_title,
            ),
        )
    ]


def _json_documents(path: Path) -> list[Document]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    sidecar = _read_sidecar(path)
    if isinstance(payload, dict) and isinstance(payload.get("documents"), list):
        records: Iterable[Any] = payload["documents"]
    elif isinstance(payload, list):
        records = payload
    else:
        records = [payload]

    documents: list[Document] = []
    for record in records:
        if isinstance(record, str):
            text = normalize_text(record)
            item_metadata: dict[str, Any] = {}
        elif isinstance(record, dict):
            raw_text = record.get("text", record.get("content"))
            if not isinstance(raw_text, str):
                continue
            text = normalize_text(raw_text)
            nested = record.get("metadata", {})
            item_metadata = nested if isinstance(nested, dict) else {}
            item_metadata = {
                **item_metadata,
                **{key: record[key] for key in METADATA_FIELDS if key in record},
            }
        else:
            continue
        if not text:
            continue
        provenance = {**sidecar, **item_metadata}
        canonical = json.dumps(
            {"text": text, "metadata": provenance},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        documents.append(
            Document(text=text, metadata=_metadata(provenance, normalized_hash(canonical)))
        )
    return documents


def _pdf_documents(path: Path) -> list[Document]:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise RuntimeError("Install pypdf to ingest text-based PDF documents") from error

    raw = path.read_bytes()
    file_hash = content_hash(raw)
    reader = PdfReader(path)
    sidecar = _read_sidecar(path)
    pdf_title = None
    if reader.metadata:
        pdf_title = getattr(reader.metadata, "title", None) or reader.metadata.get("/Title")
    documents: list[Document] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = normalize_text(page.extract_text() or "")
        if not text:
            continue
        documents.append(
            Document(
                text=text,
                metadata=_metadata(
                    sidecar,
                    file_hash,
                    title=sidecar.get("title") or pdf_title,
                    page=page_number,
                ),
            )
        )
    return documents


def load_document(path: str | Path) -> list[Document]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported knowledge document type: {source.suffix}")
    if source.name.endswith(".metadata.json"):
        return []
    if suffix in {".txt", ".md", ".markdown"}:
        return _plain_document(source)
    if suffix in {".html", ".htm"}:
        return _html_document(source)
    if suffix == ".json":
        return _json_documents(source)
    return _pdf_documents(source)


def load_knowledge_directory(path: str | Path) -> list[Document]:
    root = Path(path)
    if not root.exists():
        raise FileNotFoundError(f"Knowledge directory does not exist: {root}")
    documents: list[Document] = []
    for source in sorted(item for item in root.rglob("*") if item.is_file()):
        if source.suffix.lower() not in SUPPORTED_SUFFIXES or source.name.endswith(
            ".metadata.json"
        ):
            continue
        documents.extend(load_document(source))
    return documents

