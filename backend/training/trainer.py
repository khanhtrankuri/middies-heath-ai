from __future__ import annotations

import json
import logging
import math
import time
from pathlib import Path
from typing import Any

import torch
from datasets import Dataset
from transformers import TrainerCallback
from trl import SFTConfig, SFTTrainer

from training.data.processing import (
    AssistantOnlyDataCollator,
    load_jsonl_rows,
    pack_tokenized_examples,
    tokenize_with_assistant_only_loss,
)

LOGGER = logging.getLogger(__name__)


class MemoryAndProgressCallback(TrainerCallback):
    def __init__(self) -> None:
        self.started = time.monotonic()

    def on_log(self, args: Any, state: Any, control: Any, logs: dict[str, Any] | None = None, **_: Any) -> None:
        if logs is None:
            return
        elapsed = time.monotonic() - self.started
        peak = torch.cuda.max_memory_allocated() / 1024**3 if torch.cuda.is_available() else 0.0
        remaining = max(state.max_steps - state.global_step, 0) if state.max_steps else None
        LOGGER.info(
            "progress epoch=%s step=%d train_loss=%s eval_loss=%s lr=%s "
            "tokens/sec=%s samples/sec=%s gpu_peak_gb=%.2f elapsed_sec=%.1f remaining_steps=%s",
            logs.get("epoch", state.epoch),
            state.global_step,
            logs.get("loss", "n/a"),
            logs.get("eval_loss", "n/a"),
            logs.get("learning_rate", "n/a"),
            logs.get("train_tokens_per_second", logs.get("eval_tokens_per_second", "n/a")),
            logs.get("train_samples_per_second", logs.get("eval_samples_per_second", "n/a")),
            peak,
            elapsed,
            remaining if remaining is not None else "n/a",
        )


def load_mixed_rows(
    data_dir: str | Path,
    mix: dict[str, float],
    split: str,
    *,
    max_samples: int | None,
    seed: int,
) -> list[dict[str, Any]]:
    data_dir = Path(data_dir)
    if not mix or any(weight <= 0 for weight in mix.values()):
        raise ValueError("dataset_mix must contain only positive weights")
    if max_samples is not None and max_samples < 1:
        raise ValueError("max_samples must be at least 1")
    weight_total = sum(mix.values())
    sources: dict[str, list[dict[str, Any]]] = {}
    for name in mix:
        path = data_dir / name / f"{split}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"Prepared dataset is missing: {path}")
        source_limit = (
            math.ceil(max_samples * mix[name] / weight_total)
            if max_samples is not None
            else None
        )
        sources[name] = load_jsonl_rows([path], limit=source_limit)
        if not sources[name]:
            raise ValueError(f"Prepared dataset split is empty: {path}")
    smallest_normalized = min(len(rows) / mix[name] for name, rows in sources.items() if mix[name] > 0)
    mixed: list[dict[str, Any]] = []
    for name, weight in mix.items():
        count = max(1, round(smallest_normalized * weight))
        rows = sorted(sources[name], key=lambda row: f"{row.get('id', '')}:{seed}")
        mixed.extend(rows[index % len(rows)] for index in range(count))
    mixed.sort(key=lambda row: f"{row.get('id', '')}:{seed}:mixed")
    return mixed[:max_samples] if max_samples is not None else mixed


def build_dataset(
    rows: list[dict[str, Any]], tokenizer: Any, *, max_length: int, packing: bool
) -> Dataset:
    tokenized = [
        tokenize_with_assistant_only_loss(tokenizer, row["messages"], max_length=max_length)
        for row in rows
    ]
    if packing:
        if tokenizer.eos_token_id is None:
            raise ValueError("Packing requires an EOS token")
        tokenized = pack_tokenized_examples(
            tokenized, max_length=max_length, eos_token_id=tokenizer.eos_token_id
        )
    return Dataset.from_list(tokenized)


def build_trainer(
    model: Any,
    tokenizer: Any,
    train_dataset: Dataset,
    eval_dataset: Dataset,
    config: dict[str, Any],
    *,
    smoke_test: bool,
) -> SFTTrainer:
    training = config["training"]
    output_dir = config["output"]["dir"]
    args = SFTConfig(
        output_dir=output_dir,
        per_device_train_batch_size=int(training["per_device_train_batch_size"]),
        per_device_eval_batch_size=int(training["per_device_eval_batch_size"]),
        gradient_accumulation_steps=int(training["gradient_accumulation_steps"]),
        learning_rate=float(training["learning_rate"]),
        num_train_epochs=float(training["num_train_epochs"]),
        max_steps=3 if smoke_test else -1,
        bf16=bool(training["bf16"]),
        fp16=bool(training["fp16"]),
        gradient_checkpointing=bool(training["gradient_checkpointing"]),
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_steps=1 if smoke_test else int(training["logging_steps"]),
        eval_strategy=training.get("eval_strategy", "steps"),
        eval_steps=1 if smoke_test else int(training["eval_steps"]),
        save_strategy=training.get("save_strategy", "steps"),
        save_steps=1 if smoke_test else int(training["save_steps"]),
        save_total_limit=int(training["save_total_limit"]),
        warmup_ratio=float(training["warmup_ratio"]),
        lr_scheduler_type=training["lr_scheduler_type"],
        weight_decay=float(training["weight_decay"]),
        max_grad_norm=float(training["max_grad_norm"]),
        optim=training.get("optim", "paged_adamw_8bit"),
        seed=int(training["seed"]),
        data_seed=int(training["seed"]),
        dataloader_num_workers=int(training.get("dataloader_num_workers", 4)),
        report_to="none",
        include_tokens_per_second=True,
        remove_unused_columns=False,
        dataset_kwargs={"skip_prepare_dataset": True},
    )
    return SFTTrainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=AssistantOnlyDataCollator(tokenizer),
        processing_class=tokenizer,
        callbacks=[MemoryAndProgressCallback()],
    )


def save_run_metadata(config: dict[str, Any], output_dir: Path, metrics: dict[str, Any]) -> None:
    metadata_dir = output_dir / "run_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    with (metadata_dir / "run.json").open("w", encoding="utf-8") as handle:
        json.dump({"config": config, "metrics": metrics}, handle, indent=2, default=str)


OOM_GUIDANCE = """CUDA out of memory. Parameters were not changed automatically.
Recommended fallback order:
1. reduce per-device batch size to 1
2. keep gradient checkpointing enabled
3. reduce max_seq_length: 4096 -> 3072 -> 2048
4. reduce LoRA rank: 32 -> 16
5. increase gradient accumulation to preserve effective batch size
"""
