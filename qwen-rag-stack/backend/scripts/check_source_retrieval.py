"""Small real-embedding retrieval smoke check, not a clinical benchmark."""
import argparse
import asyncio
import json
from dataclasses import replace
from pathlib import Path

from app.services.rag.config import RAGConfig
from app.services.rag.service import create_rag_service


async def check(index):
    config = replace(RAGConfig.from_env(), enabled=True, index_path=index.resolve(), reranker="score")
    service = create_rag_service(config)
    service.load()
    rows = []
    for query, expected in (("What is a stroke?", "nlm-stroke-excerpt-20261031"),
                            ("Headache suddenly extremely painful", "nhs-headache-excerpts-20261031")):
        results = await service.retrieve(query, top_k=2)
        assert results and results[0].metadata.source_id == expected
        assert all(r.metadata.review_status == "source_checked" for r in results)
        rows.append({"query": query, "expected_source": expected,
                     "retrieved_sources": [r.metadata.source_id for r in results]})
    return {"method": "two_excerpt_retrieval_smoke_not_clinical_benchmark", "embedding_model": config.embedding_model,
            "reranker": "score", "passed": True, "rows": rows, "clinical_review": "pending"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Report exists")
    result = asyncio.run(check(args.index))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
