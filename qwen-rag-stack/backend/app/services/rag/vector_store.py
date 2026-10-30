from __future__ import annotations

import json
import os
import shutil
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from .config import RetrievedChunk, TextChunk

INDEX_FILES = ("vectors.faiss", "chunks.jsonl", "metadata.json", "manifest.json")


def _faiss() -> Any:
    try:
        import faiss
    except ImportError as error:
        raise RuntimeError("Install faiss-cpu to build or search the RAG index") from error
    return faiss


def _normalized(vectors: np.ndarray) -> np.ndarray:
    result = np.asarray(vectors, dtype=np.float32)
    if result.ndim != 2:
        raise ValueError("Expected a two-dimensional embedding matrix")
    norms = np.linalg.norm(result, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return result / norms


class FAISSVectorStore:
    def __init__(self, index: Any, chunks: list[TextChunk], manifest: dict[str, Any]) -> None:
        if index.ntotal != len(chunks):
            raise ValueError("FAISS vector count does not match chunks.jsonl")
        self.index = index
        self.chunks = chunks
        self.manifest = manifest

    @property
    def dimension(self) -> int:
        return int(self.index.d)

    @classmethod
    def from_embeddings(
        cls,
        chunks: Sequence[TextChunk],
        embeddings: np.ndarray,
        manifest: dict[str, Any],
    ) -> "FAISSVectorStore":
        vectors = _normalized(embeddings)
        if len(chunks) != vectors.shape[0]:
            raise ValueError("Chunk and embedding counts differ")
        if not chunks:
            raise ValueError("Cannot create an empty RAG index")
        index = _faiss().IndexFlatIP(int(vectors.shape[1]))
        index.add(vectors)
        complete_manifest = {
            **manifest,
            "embedding_dimension": int(vectors.shape[1]),
            "chunk_count": len(chunks),
        }
        return cls(index, list(chunks), complete_manifest)

    def save(self, path: str | Path, *, rebuild: bool = False) -> None:
        destination = Path(path).resolve()
        if destination.exists() and not rebuild:
            raise FileExistsError(
                f"RAG index already exists at {destination}; pass --rebuild to replace it"
            )
        if destination in {Path(destination.anchor), Path.home().resolve(), Path.cwd().resolve()}:
            raise ValueError("Refusing to use a broad directory as a RAG index target")

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.parent / f".{destination.name}.building-{uuid.uuid4().hex}"
        temporary.mkdir(parents=False, exist_ok=False)
        try:
            _faiss().write_index(self.index, str(temporary / "vectors.faiss"))
            with (temporary / "chunks.jsonl").open("w", encoding="utf-8", newline="\n") as stream:
                for chunk in self.chunks:
                    stream.write(chunk.model_dump_json() + "\n")
            metadata = {
                "schema_version": 1,
                "sources": [
                    chunk.metadata.model_dump(mode="json") for chunk in self.chunks
                ],
            }
            (temporary / "metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            manifest = {"schema_version": 1, **self.manifest}
            (temporary / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    @classmethod
    def load(cls, path: str | Path) -> "FAISSVectorStore":
        root = Path(path)
        missing = [name for name in INDEX_FILES if not (root / name).is_file()]
        if missing:
            raise FileNotFoundError(
                f"RAG index is missing required file(s): {', '.join(missing)}"
            )
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        chunks = [
            TextChunk.model_validate_json(line)
            for line in (root / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        index = _faiss().read_index(str(root / "vectors.faiss"))
        store = cls(index, chunks, manifest)
        expected_dimension = manifest.get("embedding_dimension")
        if expected_dimension is not None and int(expected_dimension) != store.dimension:
            raise ValueError("Manifest embedding dimension does not match vectors.faiss")
        return store

    def search(self, query_embedding: np.ndarray, top_k: int) -> list[RetrievedChunk]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query = _normalized(query_embedding)
        if query.shape != (1, self.dimension):
            raise ValueError(
                f"Query embedding must have shape (1, {self.dimension}), got {query.shape}"
            )
        scores, indices = self.index.search(query, min(top_k, len(self.chunks)))
        results: list[RetrievedChunk] = []
        for score, position in zip(scores[0], indices[0], strict=True):
            if position < 0:
                continue
            chunk = self.chunks[int(position)]
            results.append(
                RetrievedChunk(**chunk.model_dump(), score=float(score))
            )
        return results


def new_manifest(
    *,
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
    document_count: int,
    chunk_count: int,
    corpus_hash: str,
) -> dict[str, Any]:
    return {
        "embedding_model": embedding_model,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "created_at": datetime.now(UTC).isoformat(),
        "document_count": document_count,
        "chunk_count": chunk_count,
        "corpus_hash": corpus_hash,
    }

