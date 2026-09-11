from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

from app.services.rag.config import RAGConfig
from app.services.rag.service import build_knowledge_index


def parse_args() -> argparse.Namespace:
    defaults = RAGConfig.from_env()
    parser = argparse.ArgumentParser(description="Build a local FAISS medical knowledge index")
    parser.add_argument(
        "--input-dir", "--input", dest="input_dir", type=Path, default=Path("data/knowledge")
    )
    parser.add_argument(
        "--output-dir", "--output", dest="output_dir", type=Path, default=defaults.index_path
    )
    parser.add_argument("--embedding-model", default=defaults.embedding_model)
    parser.add_argument("--device", choices=("cpu", "cuda"), default=defaults.embedding_device)
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--batch-size", type=int, default=defaults.embedding_batch_size)
    parser.add_argument("--chunk-size", type=int, default=defaults.chunk_size)
    parser.add_argument("--chunk-overlap", type=int, default=defaults.chunk_overlap)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    defaults = RAGConfig.from_env()
    config = dataclasses.replace(
        defaults,
        enabled=True,
        index_path=args.output_dir.resolve(),
        embedding_model=args.embedding_model,
        embedding_device=args.device,
        embedding_batch_size=args.batch_size,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    config.validate()
    stats = build_knowledge_index(
        args.input_dir,
        args.output_dir,
        config=config,
        rebuild=args.rebuild,
    )
    payload = dataclasses.asdict(stats)
    payload.update(
        documents_processed=stats.document_count,
        chunks_created=stats.chunk_count,
        duplicates_removed=stats.duplicate_records + stats.duplicate_chunks,
        embedding_model=config.embedding_model,
        index_path=str(stats.output_path),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
