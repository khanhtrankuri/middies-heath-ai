from __future__ import annotations

import inspect
import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any

import torch
from datasets import Dataset
from transformers import TrainerCallback
from trl import SFTConfig, SFTTrainer

from training.data.processing import (
    AssistantOnlyDataCollator,
    UntrainableConversationError,
    load_jsonl_rows,
    pack_tokenized_examples,
    tokenize_conversation_windows,
)

LOGGER = logging.getLogger(__name__)


def _resolve_dataloader_workers(configured: int, *, platform_name: str | None = None) -> int:
    if configured < 0:
        raise ValueError("dataloader_num_workers cannot be negative")
    platform_name = os.name if platform_name is None else platform_name
    if platform_name == "nt" and configured:
        LOGGER.warning(
            "Windows spawn cannot safely serialize the full in-memory tokenized dataset; "
            "forcing dataloader_num_workers=0 (configured=%d)",
            configured,
        )
        return 0
    return configured


def configure_wandb(tracking: dict[str, Any], output_dir: str) -> tuple[str, str | None]:
    """Configure the Transformers W&B integration from the training profile."""

    if not tracking.get("enabled", False):
        return "none", None

    try:
        import wandb  # noqa: F401
    except ImportError as error:
        raise RuntimeError(
            "W&B tracking is enabled but wandb is not installed. Install the backend dependencies."
        ) from error

    project = str(tracking.get("project", "meddies-health-ai"))
    run_name = tracking.get("run_name") or Path(output_dir).name
    mode = str(tracking.get("mode", "online"))
    log_model = str(tracking.get("log_model", "false"))
    if mode not in {"online", "offline", "disabled"}:
        raise ValueError("tracking.mode must be online, offline, or disabled")
    if log_model not in {"false", "end", "checkpoint"}:
        raise ValueError("tracking.log_model must be false, end, or checkpoint")

    os.environ["WANDB_PROJECT"] = project
    os.environ["WANDB_MODE"] = mode
    os.environ["WANDB_LOG_MODEL"] = log_model
    os.environ["WANDB_SILENT"] = "true"
    return "wandb", str(run_name)


class MemoryAndProgressCallback(TrainerCallback):
    def __init__(self, effective_batch_size: int) -> None:
        self.started = time.monotonic()
        self.effective_batch_size = effective_batch_size

    def on_log(self, args: Any, state: Any, control: Any, logs: dict[str, Any] | None = None, **_: Any) -> None:
        if logs is None:
            return
        elapsed = time.monotonic() - self.started
        peak = torch.cuda.max_memory_allocated() / 1024**3 if torch.cuda.is_available() else 0.0
        tokens_seen = int(getattr(state, "num_input_tokens_seen", 0) or 0)
        tokens_per_second = tokens_seen / elapsed if elapsed > 0 and tokens_seen else 0.0
        samples_seen = state.global_step * self.effective_batch_size
        samples_per_second = samples_seen / elapsed if elapsed > 0 else 0.0
        estimated_epoch_seconds = None
        if state.global_step >= 50 and state.max_steps and state.global_step:
            estimated_epoch_seconds = elapsed * state.max_steps / state.global_step
            hours, remainder = divmod(int(estimated_epoch_seconds), 3600)
            minutes, seconds = divmod(remainder, 60)
            LOGGER.info("Estimated full-dataset epoch: %02d:%02d:%02d", hours, minutes, seconds)
            if estimated_epoch_seconds > 1800:
                LOGGER.warning("Estimated full-dataset epoch exceeds 30 minutes; the dataset remains unchanged")
        LOGGER.info(
            "progress epoch=%s step=%d train_loss=%s eval_loss=%s lr=%s tokens_seen=%d "
            "tokens/sec=%.2f samples/sec=%.2f gpu_peak_gb=%.2f effective_batch_size=%d "
            "estimated_full_epoch_seconds=%s",
            logs.get("epoch", state.epoch),
            state.global_step,
            logs.get("loss", "n/a"),
            logs.get("eval_loss", "n/a"),
            logs.get("learning_rate", "n/a"),
            tokens_seen,
            tokens_per_second,
            samples_per_second,
            peak,
            self.effective_batch_size,
            f"{estimated_epoch_seconds:.1f}" if estimated_epoch_seconds is not None else "pending",
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
    if max_samples is None:
        # A full run consumes every valid SFT row exactly once. Mix weights are
        # used only for bounded smoke/debug sampling; they never truncate the
        # published dataset during normal training.
        mixed = [row for rows in sources.values() for row in rows]
        mixed.sort(key=lambda row: f"{row.get('id', '')}:{seed}:full")
        return mixed

    smallest_normalized = min(len(rows) / mix[name] for name, rows in sources.items() if mix[name] > 0)
    mixed: list[dict[str, Any]] = []
    for name, weight in mix.items():
        count = max(1, round(smallest_normalized * weight))
        rows = sorted(sources[name], key=lambda row: f"{row.get('id', '')}:{seed}")
        mixed.extend(rows[index % len(rows)] for index in range(count))
    mixed.sort(key=lambda row: f"{row.get('id', '')}:{seed}:mixed")
    return mixed[:max_samples]


def build_dataset(
    rows: list[dict[str, Any]], tokenizer: Any, *, max_length: int, packing: bool
) -> Dataset:
    tokenized: list[dict[str, list[int]]] = []
    skipped: list[tuple[str, str]] = []
    for row in rows:
        try:
            tokenized.extend(
                tokenize_conversation_windows(
                    tokenizer, row["messages"], max_length=max_length
                )
            )
        except UntrainableConversationError as error:
            skipped.append((str(row.get("id", "unknown")), str(error)))
    if skipped:
        examples = "; ".join(f"{row_id}: {reason}" for row_id, reason in skipped[:5])
        LOGGER.warning(
            "Skipped %d/%d conversation(s) that cannot produce assistant-supervised "
            "windows at max_seq_length=%d. Examples: %s",
            len(skipped),
            len(rows),
            max_length,
            examples,
        )
    if not tokenized:
        raise ValueError("No trainable assistant-supervised examples remain after tokenization")
    if packing:
        if tokenizer.eos_token_id is None:
            raise ValueError("Packing requires an EOS token")
        tokenized = pack_tokenized_examples(
            tokenized, max_length=max_length, eos_token_id=tokenizer.eos_token_id
        )
    return Dataset.from_list(tokenized)


def build_sft_config(
    training: dict[str, Any], output_dir: str, *, smoke_test: bool
) -> SFTConfig:
    """Build an SFT config across the Transformers 4 and 5 scheduler APIs."""

    configured_optim = str(training.get("optim", "adamw_torch"))
    if configured_optim == "adamw_torch_fused":
        supports_fused = "fused" in inspect.signature(torch.optim.AdamW).parameters
        if not supports_fused:
            LOGGER.warning(
                "adamw_torch_fused is unavailable in this PyTorch build; falling back to adamw_torch"
            )
            configured_optim = "adamw_torch"
    kwargs: dict[str, Any] = dict(
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
        lr_scheduler_type=training["lr_scheduler_type"],
        weight_decay=float(training["weight_decay"]),
        max_grad_norm=float(training["max_grad_norm"]),
        optim=configured_optim,
        seed=int(training["seed"]),
        data_seed=int(training["seed"]),
        dataloader_num_workers=_resolve_dataloader_workers(
            int(training.get("dataloader_num_workers", 4))
        ),
        report_to="none",
        remove_unused_columns=False,
        dataset_kwargs={"skip_prepare_dataset": True},
    )
    parameters = inspect.signature(SFTConfig).parameters
    warmup_ratio = float(training["warmup_ratio"])
    if "warmup_ratio" in parameters:
        kwargs["warmup_ratio"] = warmup_ratio
    elif "warmup_steps" in parameters:
        # Transformers 5 accepts a fraction in warmup_steps when the value is < 1.
        kwargs["warmup_steps"] = warmup_ratio
    else:
        raise RuntimeError("Installed SFTConfig exposes no supported warmup setting")
    if "include_tokens_per_second" in parameters:
        kwargs["include_tokens_per_second"] = True
    if "include_num_input_tokens_seen" in parameters:
        kwargs["include_num_input_tokens_seen"] = True
    try:
        return SFTConfig(**kwargs)
    except ValueError:
        if configured_optim != "adamw_torch_fused":
            raise
        LOGGER.warning(
            "Installed Transformers does not accept adamw_torch_fused; falling back to adamw_torch"
        )
        kwargs["optim"] = "adamw_torch"
        return SFTConfig(**kwargs)


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
    report_to, run_name = configure_wandb(config.get("tracking", {}), output_dir)
    args = build_sft_config(training, output_dir, smoke_test=smoke_test)
    args.report_to = [report_to] if report_to != "none" else []
    args.run_name = run_name
    return SFTTrainer(
        model=model,
        args=args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=AssistantOnlyDataCollator(tokenizer),
        processing_class=tokenizer,
        callbacks=[MemoryAndProgressCallback(
            int(training["per_device_train_batch_size"])
            * int(training["gradient_accumulation_steps"])
        )],
    )


def save_run_metadata(config: dict[str, Any], output_dir: Path, metrics: dict[str, Any]) -> None:
    metadata_dir = output_dir / "run_metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    with (metadata_dir / "run.json").open("w", encoding="utf-8") as handle:
        json.dump({"config": config, "metrics": metrics}, handle, indent=2, default=str)


OOM_GUIDANCE = """CUDA out of memory. BF16 LoRA settings were not changed automatically.
Recommended fallback order:
1. reduce max_seq_length: 1024 -> 768
2. reduce max_seq_length: 768 -> 512
3. reduce LoRA q+v rank: r8 -> r4
4. keep per-device batch size = 1
5. increase gradient accumulation to preserve effective batch size
The training path will not switch to quantization automatically.
"""
