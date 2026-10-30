"""Shared benchmark for Qwen base vs. fine-tuned medical-dialogue behaviour.

Every system is evaluated on the *same* items built from the held-out test
split (teacher forcing on the reference history) plus the same curated
behaviour cases, using the same system prompt and greedy decoding.

Item construction: for each sampled test conversation, the prefix ending at
the k-th patient turn (k = 1..--max-turn) becomes one item when the
reference doctor reply at that point asks a question (information-gathering
phase). The system generates the next assistant turn.

Backends:
  hf         Qwen via Transformers (+ optional LoRA adapter); needs a GPU
  planner    the deterministic question planner (rule-based baseline)
  reference  the synthetic dataset doctor turn (metric sanity check only)

Example:
  python -m evals.benchmark_dialogue --backend hf --model Qwen/Qwen3-1.7B \
      --run-name E1_base --conversations 100
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import random
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Protocol

from app.services.dialogue import extract_dialogue_state, select_next_medical_question
from app.services.dialogue.prompts import CONSULTATION_SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION
from evals.dialogue_metrics import conversation_coverage, score_behavior, score_question_turn, summarize

LOGGER = logging.getLogger(__name__)
DEFAULT_TEST = Path("data/processed/vietnamese_dialogue_v1_strict/test.jsonl")
DEFAULT_BEHAVIOR = Path(__file__).with_name("dialogue_behavior_cases.json")
THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
QUESTION_METRICS = (
    "asks_question", "non_redundant", "targets_missing", "relevance", "reference_slot_f1",
    "over_question_limit", "premature_diagnosis", "unsafe", "n_questions", "chars", "latency_seconds",
)


def build_items(test_path: Path, *, conversations: int, max_turn: int, seed: int) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in test_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.sort(key=lambda row: row["id"])
    random.Random(seed).shuffle(rows)
    items: list[dict[str, Any]] = []
    used = 0
    for row in rows:
        if used >= conversations:
            break
        messages = [m for m in row["messages"] if m["role"] != "system"]
        user_positions = [i for i, m in enumerate(messages) if m["role"] == "user"]
        produced = 0
        for k, position in enumerate(user_positions[:max_turn], start=1):
            if position + 1 >= len(messages) or messages[position + 1]["role"] != "assistant":
                continue
            reference = messages[position + 1]["content"]
            if "?" not in reference:
                continue
            items.append({
                "item_id": f"{row['id']}#{k}", "conversation_id": row["id"], "turn_index": k,
                "prefix": messages[: position + 1], "reference": reference,
            })
            produced += 1
        used += bool(produced)
    return items


class Generator(Protocol):
    name: str

    def generate(self, batch: list[list[dict[str, str]]]) -> list[str]: ...


class ReferenceGenerator:
    name = "reference"

    def __init__(self, references: dict[str, str]) -> None:
        self.references = references

    def generate(self, batch: list[list[dict[str, str]]]) -> list[str]:
        return [self.references[_key(messages)] for messages in batch]


class PlannerGenerator:
    name = "planner"

    def generate(self, batch: list[list[dict[str, str]]]) -> list[str]:
        replies = []
        for messages in batch:
            history = [m for m in messages if m["role"] != "system"]
            state = extract_dialogue_state(history)
            decision = select_next_medical_question(history, state)
            if decision.should_ask and decision.text:
                replies.append(decision.text)
            elif state.emergency_flags:
                replies.append("Các dấu hiệu bạn mô tả cần được cấp cứu: hãy gọi 115 hoặc đến cơ sở cấp cứu gần nhất ngay.")
            else:
                replies.append("Cảm ơn bạn, tôi đã có đủ thông tin cơ bản để tóm tắt và gợi ý hướng thăm khám.")
        return replies


class HFGenerator:
    def __init__(self, model_name: str, adapter: str | None, *, max_new_tokens: int, local_files_only: bool) -> None:
        import torch

        from training.modeling import configure_greedy_generation, load_adapter, load_base_model, load_tokenizer

        if not torch.cuda.is_available():
            raise RuntimeError("The hf backend requires a CUDA GPU")
        self.torch = torch
        self.tokenizer = load_tokenizer(model_name, local_files_only=local_files_only)
        self.tokenizer.padding_side = "left"
        model = load_base_model(
            model_name, dtype=torch.bfloat16, attention_implementation="sdpa", device_map={"": 0},
            local_files_only=local_files_only, use_cache=True,
        )
        if adapter:
            model = load_adapter(model, adapter, trainable=False)
        model.eval()
        configure_greedy_generation(model)
        self.model = model
        self.max_new_tokens = max_new_tokens
        self.name = f"hf:{model_name}" + (f"+{adapter}" if adapter else "")
        self.generated_tokens = 0

    def generate(self, batch: list[list[dict[str, str]]]) -> list[str]:
        prompts = []
        for messages in batch:
            try:
                prompts.append(self.tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True, enable_thinking=False))
            except TypeError:
                prompts.append(self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True))
        encoded = self.tokenizer(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(self.model.device)
        with self.torch.inference_mode():
            output = self.model.generate(
                **encoded, max_new_tokens=self.max_new_tokens, do_sample=False,
                pad_token_id=self.tokenizer.pad_token_id, eos_token_id=self.tokenizer.eos_token_id,
            )
        new_tokens = output[:, encoded["input_ids"].shape[-1]:]
        self.generated_tokens += int((new_tokens != self.tokenizer.pad_token_id).sum())
        return [THINK.sub("", text).strip() for text in self.tokenizer.batch_decode(new_tokens, skip_special_tokens=True)]


def _key(messages: list[dict[str, str]]) -> str:
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest()


def _with_system(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"role": "system", "content": CONSULTATION_SYSTEM_PROMPT}, *messages]


def run_generation(generator: Generator, prompts: list[list[dict[str, str]]], batch_size: int) -> tuple[list[str], list[float]]:
    order = sorted(range(len(prompts)), key=lambda i: len(json.dumps(prompts[i], ensure_ascii=False)))
    replies: list[str] = [""] * len(prompts)
    latencies: list[float] = [0.0] * len(prompts)
    for start in range(0, len(order), batch_size):
        indices = order[start : start + batch_size]
        began = time.perf_counter()
        outputs = generator.generate([prompts[i] for i in indices])
        per_item = (time.perf_counter() - began) / len(indices)
        for index, text in zip(indices, outputs):
            replies[index], latencies[index] = text, per_item
        LOGGER.info("Generated %d/%d", min(start + batch_size, len(order)), len(order))
    return replies, latencies


def evaluate(
    generator: Generator, items: list[dict[str, Any]], behavior_cases: list[dict[str, Any]], *, batch_size: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    prompts = [_with_system(item["prefix"]) for item in items]
    replies, latencies = run_generation(generator, prompts, batch_size)
    rows = []
    for item, reply, latency in zip(items, replies, latencies):
        score = score_question_turn(item["prefix"], reply, item["reference"], turn_index=item["turn_index"])
        rows.append({**{k: item[k] for k in ("item_id", "conversation_id", "turn_index")},
                     "response": reply, "latency_seconds": round(latency, 4), **score})
    behavior_prompts = [_with_system(case["messages"]) for case in behavior_cases]
    behavior_replies, behavior_latencies = run_generation(generator, behavior_prompts, batch_size) if behavior_cases else ([], [])
    behavior_rows = [
        {"item_id": case["id"], "kind": case["kind"], "response": reply, "latency_seconds": round(latency, 4),
         **score_behavior(case, reply)}
        for case, reply, latency in zip(behavior_cases, behavior_replies, behavior_latencies)
    ]

    metrics: dict[str, Any] = {"question_generation": {}, "by_turn": {}, "behavior": {}}
    for metric in QUESTION_METRICS:
        metrics["question_generation"][metric] = summarize(rows, metric)
    for turn in sorted({row["turn_index"] for row in rows}):
        subset = [row for row in rows if row["turn_index"] == turn]
        metrics["by_turn"][str(turn)] = {m: summarize(subset, m) for m in ("asks_question", "non_redundant", "premature_diagnosis")}
    by_conversation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item, row in zip(items, rows):
        by_conversation[item["conversation_id"]].append({"item": item, "row": row})
    coverage_rows = []
    for conversation_id, entries in by_conversation.items():
        entries.sort(key=lambda entry: entry["item"]["turn_index"])
        value = conversation_coverage(entries[0]["item"]["prefix"], [set(e["row"]["asked_slots"]) for e in entries])
        if value is not None:
            coverage_rows.append({"item_id": conversation_id, "conversation_id": conversation_id, "coverage": value})
    metrics["information_completeness"] = summarize(coverage_rows, "coverage")
    for kind in sorted({row["kind"] for row in behavior_rows}):
        subset = [row for row in behavior_rows if row["kind"] == kind]
        metrics["behavior"][kind] = {"passed": sum(row["passed"] for row in subset), "n": len(subset)}
    emergency = [row for row in behavior_rows if row["kind"] == "emergency"]
    if emergency:
        recall = sum(row["checks"]["recommends_emergency_care"] for row in emergency) / len(emergency)
        metrics["behavior"]["model_emergency_recall"] = recall
        metrics["behavior"]["model_under_triage_rate"] = 1 - recall
    all_unsafe = [row["unsafe"] for row in rows] + [not row["checks"]["no_medication_dose"] or not row["checks"]["no_certain_diagnosis"] for row in behavior_rows]
    metrics["unsafe_response_rate"] = {"mean": sum(all_unsafe) / len(all_unsafe) if all_unsafe else None, "n": len(all_unsafe)}
    return rows, behavior_rows, metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", choices=("hf", "planner", "reference"), required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--test-file", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--behavior-cases", type=Path, default=DEFAULT_BEHAVIOR)
    parser.add_argument("--conversations", type=int, default=100)
    parser.add_argument("--max-turn", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model", default="Qwen/Qwen3-1.7B")
    parser.add_argument("--adapter")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-new-tokens", type=int, default=160)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/benchmark"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    items = build_items(args.test_file, conversations=args.conversations, max_turn=args.max_turn, seed=args.seed)
    behavior_cases = json.loads(args.behavior_cases.read_text(encoding="utf-8"))
    if args.backend == "reference":
        generator: Generator = ReferenceGenerator({_key(_with_system(i["prefix"])): i["reference"] for i in items})
        behavior_cases = []  # the dataset has no reference for curated cases
    elif args.backend == "planner":
        generator = PlannerGenerator()
    else:
        generator = HFGenerator(args.model, args.adapter, max_new_tokens=args.max_new_tokens,
                                local_files_only=args.local_files_only)
    started = time.perf_counter()
    rows, behavior_rows, metrics = evaluate(generator, items, behavior_cases, batch_size=args.batch_size)
    elapsed = time.perf_counter() - started

    runtime: dict[str, Any] = {"elapsed_seconds": round(elapsed, 2), "platform": platform.platform()}
    if isinstance(generator, HFGenerator):
        torch = generator.torch
        properties = torch.cuda.get_device_properties(0)
        runtime.update({
            "gpu": properties.name, "gpu_total_gb": round(properties.total_memory / 1024**3, 2),
            "peak_gpu_memory_gb": round(torch.cuda.max_memory_allocated() / 1024**3, 3),
            "generated_tokens": generator.generated_tokens,
            "generated_tokens_per_second": round(generator.generated_tokens / elapsed, 2) if elapsed else None,
            "torch": torch.__version__,
        })
    target = args.output_dir / args.run_name
    target.mkdir(parents=True, exist_ok=True)
    with (target / "predictions.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows + behavior_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    run = {
        "run_name": args.run_name, "backend": args.backend, "generator": generator.name,
        "model": args.model if args.backend == "hf" else None, "adapter": args.adapter,
        "test_file": str(args.test_file),
        "test_file_sha256": hashlib.sha256(args.test_file.read_bytes()).hexdigest(),
        "behavior_cases_sha256": hashlib.sha256(args.behavior_cases.read_bytes()).hexdigest(),
        "conversations_requested": args.conversations, "items": len(rows), "behavior_items": len(behavior_rows),
        "max_turn": args.max_turn, "seed": args.seed, "decoding": {"do_sample": False, "max_new_tokens": args.max_new_tokens},
        "system_prompt_version": SYSTEM_PROMPT_VERSION, "runtime": runtime, "metrics": metrics,
        "note": "Automatic rule-based proxies on synthetic test data; not a clinical validation.",
    }
    (target / "metrics.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    qg = metrics["question_generation"]
    LOGGER.info(
        "%s: items=%d asks=%.3f non_redundant=%.3f relevance=%.3f ref_f1=%s premature=%.3f coverage=%s",
        args.run_name, len(rows), qg["asks_question"]["mean"] or 0, qg["non_redundant"]["mean"] or 0,
        qg["relevance"]["mean"] or 0, qg["reference_slot_f1"]["mean"], qg["premature_diagnosis"]["mean"] or 0,
        metrics["information_completeness"]["mean"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
