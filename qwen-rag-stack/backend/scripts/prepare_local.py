"""Download public local weights and build the small development reference index."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from huggingface_hub import snapshot_download

from app.services.rag.config import BACKEND_ROOT, RAGConfig
from app.services.rag.service import build_knowledge_index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=BACKEND_ROOT / "data/reference_starter")
    parser.add_argument("--rebuild", action="store_true", help="Explicitly replace an existing index")
    args = parser.parse_args()
    config = RAGConfig.from_env()
    if config.index_path.exists() and any(config.index_path.iterdir()) and not args.rebuild:
        parser.error("Index exists; use --rebuild to replace it or choose another index path")
    models = [os.getenv("MEDDIES_BASE_MODEL", "Qwen/Qwen3-1.7B"), config.embedding_model]
    if config.reranker == "cross_encoder":
        models.append(config.reranker_model)
    for model in models:
        print(f"Preparing weights: {model}", flush=True)
        if not Path(model).is_dir():
            snapshot_download(
                model, allow_patterns=["*.json", "*.safetensors", "*.txt", "*.model", "*.jinja"],
                ignore_patterns=["onnx/*", "openvino/*"], max_workers=1,
            )
    print("Building development reference index (not a clinical validation corpus).", flush=True)
    stats = build_knowledge_index(args.input_dir, config.index_path, config=config, rebuild=args.rebuild)
    print(f"Ready: {stats.document_count} documents, {stats.chunk_count} chunks, {stats.embedding_dimension} dimensions")


if __name__ == "__main__":
    main()
