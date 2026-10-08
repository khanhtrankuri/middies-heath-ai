from __future__ import annotations

import argparse
import asyncio
import json
import math
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
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Evaluation requires non-empty cases with unique IDs")
    if any(not case.get("expected_source_ids") for case in cases):
        raise ValueError("Every case requires expected_source_ids relevance labels")
    service = create_rag_service(RAGConfig.from_env())
    service.load()
    if not service.ready:
        raise RAGUnavailableError(service.error or "RAG is not ready")

    recall_values: list[float] = []
    reciprocal_ranks: list[float] = []
    source_hits: list[float] = []
    ndcg_values: list[float] = []
    rows: list[dict[str, object]] = []
    for case in cases:
        results = await service.retrieve(case["query"], top_k=service.config.final_k)
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
        # Repeated chunks from one source do not earn repeated relevance credit.
        seen = set()
        dcg = 0.0
        for rank, source in enumerate(ranked, start=1):
            if source in expected and source not in seen:
                dcg += 1.0 / math.log2(rank + 1)
            seen.add(source)
        ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, min(len(expected), service.config.final_k) + 1))
        ndcg_values.append(dcg / ideal)
        rows.append(
            {
                "id": case["id"],
                "recall_at_k": recall,
                "reciprocal_rank": reciprocal_rank,
                "source_hit": bool(hits),
                "ranked_source_ids": ranked,
                "ndcg_at_k": ndcg_values[-1],
            }
        )
    count = len(rows) or 1
    return {
        "case_count": len(rows),
        "recall_at_k": sum(recall_values) / count,
        "mrr": sum(reciprocal_ranks) / count,
        "source_hit_rate": sum(source_hits) / count,
        "ndcg_at_k": sum(ndcg_values) / count,
        "k": service.config.final_k,
        "candidate_k": service.config.top_k,
        "embedding_model": service.config.embedding_model,
        "reranker": service.config.reranker,
        "corpus_hash": service.vector_store.manifest.get("corpus_hash"),
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
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-recall", type=float, default=0.0)
    parser.add_argument("--min-mrr", type=float, default=0.0)
    args = parser.parse_args()
    if not 0 <= args.min_recall <= 1 or not 0 <= args.min_mrr <= 1:
        parser.error("Metric thresholds must be between zero and one")
    result = asyncio.run(evaluate(args.cases))
    result["passed"] = result["recall_at_k"] >= args.min_recall and result["mrr"] >= args.min_mrr
    report = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print(report)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
