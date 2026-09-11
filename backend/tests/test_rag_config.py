from __future__ import annotations

from pathlib import Path

from app.services.rag.config import RAGConfig


def test_required_meddies_environment_names_take_precedence(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("MEDDIES_RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_ENABLED", "false")
    monkeypatch.setenv("MEDDIES_RAG_INDEX_PATH", str(tmp_path / "index"))
    monkeypatch.setenv("MEDDIES_EMBEDDING_MODEL", "test/model")
    monkeypatch.setenv("MEDDIES_EMBEDDING_DEVICE", "cuda")
    monkeypatch.setenv("MEDDIES_RAG_TOP_K", "6")
    monkeypatch.setenv("MEDDIES_RAG_FINAL_K", "3")

    config = RAGConfig.from_env()

    assert config.enabled is True
    assert config.index_path == (tmp_path / "index").resolve()
    assert config.embedding_model == "test/model"
    assert config.embedding_device == "cuda"
    assert config.top_k == 6
    assert config.final_k == 3
