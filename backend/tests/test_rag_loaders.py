from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from app.services.rag.loaders import load_document, load_knowledge_directory


def test_loads_supported_text_json_and_html_with_null_metadata(tmp_path: Path) -> None:
    (tmp_path / "plain.txt").write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
    (tmp_path / "record.json").write_text(
        json.dumps(
            {
                "text": "Reviewed guidance",
                "metadata": {"source_id": "json-1", "organization": "Authority"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "page.html").write_text(
        "<html><head><title>HTML title</title><script>ignore()</script></head>"
        "<body><h1>Heading</h1><p>Useful text.</p></body></html>",
        encoding="utf-8",
    )

    documents = load_knowledge_directory(tmp_path)

    assert len(documents) == 3
    plain = next(item for item in documents if "First paragraph" in item.text)
    assert plain.metadata.organization is None
    assert plain.metadata.source_url is None
    assert len(plain.metadata.document_hash) == 64
    html = next(item for item in documents if "Useful text" in item.text)
    assert html.metadata.title == "HTML title"
    assert "ignore" not in html.text
    record = next(item for item in documents if item.metadata.source_id == "json-1")
    assert record.metadata.organization == "Authority"


def test_sidecar_metadata_is_retained(tmp_path: Path) -> None:
    source = tmp_path / "guidance.md"
    source.write_text("# Care\n\nReviewed content.", encoding="utf-8")
    source.with_suffix(".md.metadata.json").write_text(
        json.dumps(
            {
                "source_id": "care-1",
                "title": "Care guidance",
                "organization": "Health authority",
                "page": None,
            }
        ),
        encoding="utf-8",
    )

    document = load_document(source)[0]

    assert document.metadata.source_id == "care-1"
    assert document.metadata.title == "Care guidance"
    assert document.metadata.page is None


def test_directory_instructions_are_not_medical_evidence(tmp_path):
    (tmp_path / "README.md").write_text("Installation instructions", encoding="utf-8")
    (tmp_path / "guidance.txt").write_text("Actual guidance", encoding="utf-8")
    documents = load_knowledge_directory(tmp_path)
    assert [document.text for document in documents] == ["Actual guidance"]


def test_pdf_loader_preserves_one_based_page_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"fake text pdf")

    class Page:
        def __init__(self, text: str) -> None:
            self.text = text

        def extract_text(self) -> str:
            return self.text

    class Reader:
        def __init__(self, path: Path) -> None:
            del path
            self.pages = [Page("Page one"), Page(""), Page("Page three")]
            self.metadata = {"/Title": "PDF title"}

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=Reader))
    documents = load_document(pdf)

    assert [item.metadata.page for item in documents] == [1, 3]
    assert all(item.metadata.title == "PDF title" for item in documents)
    assert len({item.metadata.document_hash for item in documents}) == 1
