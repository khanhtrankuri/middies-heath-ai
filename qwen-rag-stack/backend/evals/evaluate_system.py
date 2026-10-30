"""Exercise a running local API with synthetic cases; record behavior and latency."""
import argparse
import json
import re
import time
import statistics
from pathlib import Path
from urllib.parse import urlparse

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("system_cases.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/system.json"))
    args = parser.parse_args()
    if urlparse(args.url).hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("This evaluator only sends its synthetic cases to a local API")
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    if not cases or len({case["id"] for case in cases}) != len(cases):
        parser.error("Cases must be non-empty with unique IDs")
    rows = []
    with httpx.Client(base_url=args.url, timeout=180, trust_env=False) as client:
        ready = client.get("/ready")
        ready.raise_for_status()
        if not all(ready.json().get(key) for key in ("api", "model", "rag")):
            raise SystemExit("Real model and RAG must be ready before system evaluation")
        for case in cases:
            start = time.perf_counter()
            response = client.post("/api/v1/consultation", json={"messages": case["messages"]})
            elapsed = time.perf_counter() - start
            body = response.json()
            citations = body.get("citations", [])
            ids = {item["citation_id"] for item in citations}
            mentioned = set(re.findall(r"\[(S\d+)\]", body.get("reply", "")))
            checks = {
                "http_ok": response.status_code == 200,
                "action": body.get("action") == case["action"],
                "real_provider": body.get("provider") in {"transformers", "safety-router", "vllm"},
                "citation_ids_valid": mentioned <= ids,
                "disclaimer": bool(body.get("disclaimer")),
            }
            if case.get("sources"):
                checks["expected_source_cited"] = bool(set(case["sources"]) & {item["source_id"] for item in citations})
                checks["grounded"] = body.get("grounding_status") == "grounded"
            else:
                checks["no_citations"] = not citations
            if case["action"] == "ASK_MORE":
                checks["asks_duration"] = bool(re.search(r"bắt đầu|từ khi|bao lâu|kéo dài|thời gian|when|how long", body.get("reply", ""), re.I))
            rows.append({"id": case["id"], "latency_seconds": round(elapsed, 3),
                         "checks": checks, "passed": all(checks.values()), "response": body})
            print(f"{case['id']}: {'PASS' if all(checks.values()) else 'FAIL'} ({elapsed:.1f}s)", flush=True)
    times = sorted(row["latency_seconds"] for row in rows)
    result = {"passed": all(row["passed"] for row in rows), "case_count": len(rows),
              "latency_median_seconds": statistics.median(times), "latency_max_seconds": max(times),
              "cases": rows, "note": "Behavior/citation/latency checks only. Answer correctness requires blinded clinical review."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {args.output}")
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
