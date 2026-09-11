from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import yaml

from app.services.rag.citations import cited_source_ids
from app.services.rag.config import RAGConfig
from app.services.rag.service import RAGUnavailableError, create_rag_service


def generation_metrics(
    answer: str,
    available_citation_ids: set[str],
    *,
    unsupported_claims: int | None = None,
    total_claims: int | None = None,
) -> dict[str, float | None]:
    cited = cited_source_ids(answer)
    citation_correctness = 1.0 if cited and cited <= available_citation_ids else 0.0
    unsupported_rate = None
    if unsupported_claims is not None and total_claims:
        unsupported_rate = unsupported_claims / total_claims
    return {
        "citation_correctness": citation_correctness,
        "unsupported_claim_rate": unsupported_rate,
    }


async def evaluate(path: Path) -> dict[str, object]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    service = create_rag_service(RAGConfig.from_env())
    service.load()
    if not service.ready:
        raise RAGUnavailableError(service.error or "RAG is not ready")

    recall_values: list[float] = []
    reciprocal_ranks: list[float] = []
    source_hits: list[float] = []
    rows: list[dict[str, object]] = []
    for case in cases:
        results = await service.retrieve(case["query"], top_k=service.config.top_k)
        expected = set(case.get("expected_source_ids", []))
        ranked = [item.metadata.source_id for item in results]
        retrieved = {item for item in ranked if item}
        hits = expected & retrieved
        recall = len(hits) / len(expected) if expected else 0.0
        reciprocal_rank = next(
            (1.0 / rank for rank, source_id in enumerate(ranked, start=1) if source_id in expected),
            0.0,
        )
        recall_values.append(recall)
        reciprocal_ranks.append(reciprocal_rank)
        source_hits.append(1.0 if hits else 0.0)
        rows.append(
            {
                "id": case["id"],
                "recall_at_k": recall,
                "reciprocal_rank": reciprocal_rank,
                "source_hit": bool(hits),
            }
        )
    count = len(rows) or 1
    return {
        "case_count": len(rows),
        "recall_at_k": sum(recall_values) / count,
        "mrr": sum(reciprocal_ranks) / count,
        "source_hit_rate": sum(source_hits) / count,
        "cases": rows,
        "safety_note": "Retrieval metrics are not evidence of clinical safety.",
        "generation_note": (
            "Use generation_metrics with human-labeled claim counts; unsupported claim rate "
            "is intentionally not guessed."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval against reviewed cases")
    parser.add_argument("--cases", type=Path, default=Path("evals/rag_cases.yaml"))
    args = parser.parse_args()
    print(json.dumps(asyncio.run(evaluate(args.cases)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

