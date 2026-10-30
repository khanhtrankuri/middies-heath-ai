from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.dataset_loader import DatasetConfig, load_meddies_dataset
from training.data.processing import clean_messages, conversation_key, deterministic_split

LOGGER = logging.getLogger(__name__)
SUPPORTED_SUBSETS = ("vietnamese", "english", "RandomQA", "RandomQuestion")


def _qa_messages(row: Mapping[str, Any]) -> list[dict[str, str]] | None:
    messages = clean_messages(row.get("messages"))
    if messages is not None:
        return messages
    question, answer = row.get("question"), row.get("answer")
    if isinstance(question, str) and question.strip() and isinstance(answer, str) and answer.strip():
        return clean_messages(
            [
                {"role": "user", "content": question.strip()},
                {"role": "assistant", "content": answer.strip()},
            ]
        )
    return None


def _prompt_messages(row: Mapping[str, Any]) -> list[dict[str, str]] | None:
    question = row.get("question")
    if isinstance(question, str) and question.strip():
        return [{"role": "user", "content": question.strip()}]
    messages = row.get("messages")
    if not isinstance(messages, list):
        return None
    prompt = [
        {"role": item.get("role"), "content": item.get("content", "").strip()}
        for item in messages
        if isinstance(item, Mapping) and item.get("role") in {"system", "user"}
        and isinstance(item.get("content"), str) and item.get("content", "").strip()
    ]
    return prompt if any(item["role"] == "user" for item in prompt) else None


def prepare_config(
    config: DatasetConfig,
    output_dir: Path,
    *,
    validation_ratio: float,
    max_samples: int | None,
    seed: int,
) -> dict[str, int]:
    target = output_dir / config
    target.mkdir(parents=True, exist_ok=True)
    prompt_only = config == "RandomQuestion"
    filenames = {
        split: target / (f"prompts_{split}.jsonl" if prompt_only else f"{split}.jsonl")
        for split in ("train", "validation")
    }
    handles = {split: path.open("w", encoding="utf-8") for split, path in filenames.items()}
    counts = {
        "total_seen": 0,
        "valid": 0,
        "invalid": 0,
        "duplicates": 0,
        "train": 0,
        "validation": 0,
    }
    seen: set[str] = set()
    try:
        dataset = load_meddies_dataset(config, streaming=True)
        for index, row in enumerate(dataset):
            if max_samples is not None and index >= max_samples:
                break
            counts["total_seen"] += 1
            messages = _prompt_messages(row) if prompt_only else _qa_messages(row)
            if messages is None:
                counts["invalid"] += 1
                continue
            key = conversation_key(messages)
            if key in seen:
                counts["duplicates"] += 1
                continue
            seen.add(key)
            counts["valid"] += 1
            split = deterministic_split(key, validation_ratio, seed=seed)
            prepared: dict[str, Any] = {
                "id": row.get("id", key),
                "source": config,
                "usage": "rag_or_preference_prompt" if prompt_only else "sft",
                "messages": messages,
            }
            handles[split].write(json.dumps(prepared, ensure_ascii=False) + "\n")
            counts[split] += 1
    finally:
        for handle in handles.values():
            handle.close()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare all Meddies subsets by intended training use")
    parser.add_argument("--configs", nargs="+", default=list(SUPPORTED_SUBSETS))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--validation-ratio", type=float, default=0.05)
    parser.add_argument("--max-samples", type=int)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    metadata: dict[str, Any] = {"seed": args.seed, "configs": {}}
    for name in args.configs:
        if name not in SUPPORTED_SUBSETS:
            parser.error(f"Unsupported dataset config: {name}")
        stats = prepare_config(
            name,
            args.output_dir,
            validation_ratio=args.validation_ratio,
            max_samples=args.max_samples,
            seed=args.seed,
        )
        metadata["configs"][name] = stats
        LOGGER.info("Prepared %s: %s", name, stats)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
