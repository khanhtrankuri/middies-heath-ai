#!/usr/bin/env python3
"""Research-only evaluation harness for Meddies Consultant and Middies Health AI.

This is NOT a clinical benchmark: synthetic references and target_disease are
not validated triage or diagnostic labels. Never report clinical accuracy until
independently reviewed gold labels are available.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

DATASET = "Meddies/meddies-consultant"
TRIAGE = {"NORMAL", "MONITOR", "SOON", "EMERGENCY"}
REQUIRED_STRINGS = (
    "triageLevel", "triageTitle", "summary", "detailedExplanation",
    "personalizedNotes",
)
REQUIRED_LISTS = ("possibleCauses", "selfCareSteps", "redFlags", "followUpQuestions")
THINK_BLOCK = re.compile(r"<think\b[^>]*>.*?</think\s*>|<think\b[^>]*>.*$", re.I | re.S)
SPACE = re.compile(r"\s+")


def visible_text(value: Any) -> str:
    """Remove synthetic chain-of-thought blocks before using any dialogue."""
    if isinstance(value, str):
        raw = value
    elif isinstance(value, list):
        raw = " ".join(visible_text(item) for item in value)
    elif isinstance(value, dict):
        raw = visible_text(value.get("text") or value.get("content") or "")
    else:
        raw = ""
    return THINK_BLOCK.sub("", raw).strip()


def first_patient_message(messages: Any, min_chars: int) -> str:
    """Use only a standalone first patient turn; never pass doctor turns."""
    if not isinstance(messages, list):
        return ""
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role", "")).lower()
        if role in {"user", "patient", "human"}:
            text = visible_text(msg.get("content", ""))
            # The first patient turn is the only eligible one: later turns
            # may rely on omitted history and would produce invalid tests.
            return text if len(text) >= min_chars else ""
    return ""


def normalize(text: str) -> str:
    return SPACE.sub(" ", text).strip().casefold()


def stable_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_case(row: dict[str, Any], config: str, min_chars: int = 25) -> dict | None:
    if config == "vietnamese":
        message = first_patient_message(row.get("messages"), min_chars)
        reference = ""
        target_disease = visible_text(row.get("target_disease", ""))
    elif config == "RandomQA":
        message = visible_text(row.get("question", ""))
        reference = visible_text(row.get("answer", ""))
        target_disease = ""
    else:
        raise ValueError("Unsupported config: " + config)

    if not (min_chars <= len(message) <= 3000):
        return None

    source_id = str(row.get("id") or stable_hash(normalize(message))[:20])
    content_key = stable_hash(normalize(message))
    # Group consultations by disease for a more conservative development/
    # holdout separation. This is NOT a clinically validated test split.
    group = target_disease.casefold() if config == "vietnamese" and target_disease else content_key
    fraction = int(stable_hash(config + ":" + group)[:8], 16) / 0xFFFFFFFF
    return {
        "id": config + ":" + source_id,
        "source_dataset": DATASET,
        "source_config": config,
        "source_id": source_id,
        "split": "holdout" if fraction >= 0.8 else "dev",
        "message": message,
        "history": [],
        "patientProfile": {},
        "target_disease_metadata_not_gold": target_disease,
        "synthetic_reference_not_gold": reference,
        "content_hash": content_key,
        "gold_triage": None,
        "clinical_review_status": "NOT_REVIEWED",
    }


def stream_hf(config: str, revision: str, seed: int) -> Iterable[dict]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit("Missing dependency. Run: pip install -r evaluation/requirements.txt") from exc
    ds = load_dataset(DATASET, config, split="train", revision=revision, streaming=True)
    # Shuffle is bounded-memory, seed-controlled; pin --revision to a commit
    # for reproducible upstream data.
    yield from ds.shuffle(seed=seed, buffer_size=1000)


def prepare(args: argparse.Namespace) -> None:
    selected = [("vietnamese", args.consultations), ("RandomQA", args.qa)]
    if all(n <= 0 for _, n in selected):
        raise SystemExit("Specify --consultations and/or --qa above zero.")
    seen: set[str] = set()
    cases: list[dict] = []
    for config, limit in selected:
        if limit <= 0:
            continue
        count = 0
        for row in stream_hf(config, args.revision, args.seed):
            case = make_case(row, config, min_chars=args.min_chars)
            if not case or case["content_hash"] in seen:
                continue
            seen.add(case["content_hash"])
            cases.append(case)
            count += 1
            if count >= limit:
                break
        print(f"{config}: selected {count}/{limit} cases")
    if not cases:
        raise SystemExit("No usable cases selected.")
    write_jsonl(Path(args.output), cases)
    print(f"Saved {len(cases)} cases to {args.output}")
    print("WARNING: all references are synthetic. No clinical accuracy was measured.")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def valid_schema(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    if not all(isinstance(result.get(key), str) for key in REQUIRED_STRINGS):
        return False
    if result["triageLevel"] not in TRIAGE:
        return False
    if not all(
        isinstance(result.get(key), list)
        and all(isinstance(item, str) for item in result[key])
        for key in REQUIRED_LISTS
    ):
        return False
    return True


def call_api(url: str, payload: dict, timeout: float) -> tuple[dict | None, int | None, str | None]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            body = res.read().decode("utf-8")
            return json.loads(body), res.status, None
    except urllib.error.HTTPError as exc:
        details = exc.read(500).decode("utf-8", "replace")
        return None, exc.code, details
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        return None, None, str(exc)[:500]


def run(args: argparse.Namespace) -> None:
    cases = read_jsonl(Path(args.cases))
    if args.split != "all":
        cases = [case for case in cases if case.get("split") == args.split]
    cases = cases[: args.limit]

    if not args.execute:
        print(f"DRY RUN: {len(cases)} requests to {args.url}")
        print("Add --execute to send requests and incur Gemini API costs.")
        return

    output_path = Path(args.output)
    previous = read_jsonl(output_path) if args.resume and output_path.exists() else []
    done = {row["id"] for row in previous}
    results = list(previous)
    for i, case in enumerate(cases, 1):
        if case["id"] in done:
            continue
        # Do not send target_disease, synthetic answer, or patient persona.
        payload = {
            "message": case["message"],
            "history": case.get("history", []),
            "patientProfile": {},
        }
        start = time.monotonic()
        response, status, error = call_api(args.url, payload, args.timeout)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        record = {
            "id": case["id"],
            "source_config": case["source_config"],
            "split": case["split"],
            "http_status": status,
            "api_ok": status is not None and 200 <= status < 300 and error is None,
            "schema_ok": valid_schema(response),
            "latency_ms": elapsed_ms,
            "triage": response.get("triageLevel") if isinstance(response, dict) else None,
            "response": response,
            "error": error,
        }
        results.append(record)
        write_jsonl(output_path, results)  # checkpoint after each request
        print(f"[{i}/{len(cases)}] {case['id']} status={status} schema={record['schema_ok']}")
        if args.pause_ms > 0:
            time.sleep(args.pause_ms / 1000)
    print(f"Saved {len(results)} results to {output_path}")


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    index = max(0, min(len(values) - 1, int((len(values) - 1) * pct + 0.999999)))
    return round(values[index], 1)


def score_reviews(rows: list[dict]) -> dict:
    """Calculate clinician-reviewed metrics ONLY from filled review labels."""
    triage_rated = [
        r for r in rows if str(r.get("reviewer_gold_triage", "")).upper() in TRIAGE
    ]
    triage_correct = sum(
        str(r["reviewer_gold_triage"]).upper() == str(r.get("model_triage", "")).upper()
        for r in triage_rated
    )
    emergency = [
        r for r in triage_rated if str(r["reviewer_gold_triage"]).upper() == "EMERGENCY"
    ]
    caught = sum(str(r.get("model_triage", "")).upper() == "EMERGENCY" for r in emergency)
    safety_rated = [
        r for r in rows if str(r.get("reviewer_safety_violation", "")).strip().lower()
        in {"yes", "no"}
    ]
    harmful = sum(
        str(r["reviewer_safety_violation"]).lower() == "yes" for r in safety_rated
    )
    return {
        "clinician_labeled_triage_cases": len(triage_rated),
        "triage_accuracy_reviewed_only": triage_correct / len(triage_rated) if triage_rated else None,
        "clinician_labeled_emergencies": len(emergency),
        "emergency_recall_reviewed_only": caught / len(emergency) if emergency else None,
        "clinician_labeled_safety_cases": len(safety_rated),
        "safety_violation_rate_reviewed_only": harmful / len(safety_rated) if safety_rated else None,
    }


def report(args: argparse.Namespace) -> None:
    cases = {c["id"]: c for c in read_jsonl(Path(args.cases))}
    predictions = read_jsonl(Path(args.results))
    # If a prior run was resumed, keep one prediction per case ID.
    unique_predictions = {r["id"]: r for r in predictions}
    predictions = list(unique_predictions.values())
    api_ok = [p for p in predictions if p.get("api_ok")]
    latency = [float(p["latency_ms"]) for p in predictions if p.get("api_ok")]
    summary = {
        "dataset": DATASET,
        "data_is_synthetic": True,
        "clinical_accuracy_verified": False,
        "total_predictions": len(predictions),
        "api_success": len(api_ok),
        "api_success_rate": len(api_ok) / len(predictions) if predictions else None,
        "schema_valid": sum(bool(p.get("schema_ok")) for p in predictions),
        "schema_valid_rate": (
            sum(bool(p.get("schema_ok")) for p in predictions) / len(predictions)
            if predictions else None
        ),
        "median_latency_ms": round(statistics.median(latency), 1) if latency else None,
        "p95_latency_ms": percentile(latency, 0.95),
        "observed_triage_distribution_not_accuracy": dict(Counter(
            str(p.get("triage")) for p in predictions if p.get("schema_ok")
        )),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    review_path = Path(args.review_csv)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "id", "source_config", "split", "patient_message",
        "synthetic_reference_NOT_GOLD", "model_triage", "model_summary",
        "model_explanation", "reviewer_gold_triage",
        "reviewer_medically_correct", "reviewer_safety_violation",
        "reviewer_id", "reviewer_notes",
    )
    if review_path.exists() and not args.overwrite_review:
        print(f"Review sheet exists; keeping clinician edits: {review_path}")
    else:
        with review_path.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            for pred in predictions:
                case = cases.get(pred["id"], {})
                response = pred.get("response") or {}
                writer.writerow({
                    "id": pred["id"],
                    "source_config": pred.get("source_config", ""),
                    "split": pred.get("split", ""),
                    "patient_message": case.get("message", ""),
                    "synthetic_reference_NOT_GOLD": case.get("synthetic_reference_not_gold", ""),
                    "model_triage": pred.get("triage", ""),
                    "model_summary": response.get("summary", ""),
                    "model_explanation": response.get("detailedExplanation", ""),
                })
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {output}, {review_path}")
    print("No clinical accuracy score: clinician gold labels are not provided by this dataset.")


def grade(args: argparse.Namespace) -> None:
    with Path(args.review_csv).open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    print(json.dumps(score_reviews(rows), ensure_ascii=False, indent=2))
    print("Reviewer-entered labels must be independently validated before reporting.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare", help="Stream and sample Meddies Consultant")
    prep.add_argument("--consultations", type=int, default=200)
    prep.add_argument("--qa", type=int, default=100)
    prep.add_argument("--seed", type=int, default=42)
    prep.add_argument("--revision", default="main", help="Pin to a dataset commit SHA for reproducibility")
    prep.add_argument("--min-chars", type=int, default=25)
    prep.add_argument("--output", default="evaluation/data/meddies_cases.jsonl")
    prep.set_defaults(func=prepare)

    runner = sub.add_parser("run", help="Call the existing Middies /api/health/chat")
    runner.add_argument("--cases", default="evaluation/data/meddies_cases.jsonl")
    runner.add_argument("--output", default="evaluation/results/predictions.jsonl")
    runner.add_argument("--url", default="http://localhost:3000/api/health/chat")
    runner.add_argument("--split", choices=["dev", "holdout", "all"], default="dev")
    runner.add_argument("--limit", type=int, default=20)
    runner.add_argument("--timeout", type=float, default=90)
    runner.add_argument("--pause-ms", type=int, default=200)
    runner.add_argument("--execute", action="store_true", help="Actually send billable API requests")
    runner.add_argument("--resume", action="store_true")
    runner.set_defaults(func=run)

    rep = sub.add_parser("report", help="Summarize API reliability and generate clinician review CSV")
    rep.add_argument("--cases", default="evaluation/data/meddies_cases.jsonl")
    rep.add_argument("--results", default="evaluation/results/predictions.jsonl")
    rep.add_argument("--output", default="evaluation/results/summary.json")
    rep.add_argument("--review-csv", default="evaluation/results/clinical_review.csv")
    rep.add_argument("--overwrite-review", action="store_true")
    rep.set_defaults(func=report)

    grades = sub.add_parser("grade", help="Metrics from externally reviewed clinical labels")
    grades.add_argument("--review-csv", default="evaluation/results/clinical_review.csv")
    grades.set_defaults(func=grade)
    return p


if __name__ == "__main__":
    arguments = build_parser().parse_args()
    arguments.func(arguments)
