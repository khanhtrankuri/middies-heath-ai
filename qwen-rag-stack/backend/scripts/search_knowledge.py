from __future__ import annotations

import argparse
import asyncio
import json

from app.services.rag.config import RAGConfig
from app.services.rag.service import RAGUnavailableError, create_rag_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search the local medical FAISS index")
    parser.add_argument("query_positional", nargs="?")
    parser.add_argument("--query")
    parser.add_argument("--top-k", type=int, default=5)
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    query = args.query or args.query_positional
    if not query:
        raise SystemExit("Provide a query with --query or as a positional argument")
    service = create_rag_service(RAGConfig.from_env())
    service.load()
    try:
        results = await service.retrieve(query, top_k=args.top_k)
    except RAGUnavailableError as error:
        raise SystemExit(f"RAG unavailable: {error}") from error
    print(
        json.dumps(
            [item.model_dump(mode="json") for item in results],
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(run())
