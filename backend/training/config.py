from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"Training config must be a YAML mapping: {config_path}")
    return loaded


def apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Apply explicit CLI values without silently changing YAML defaults."""

    result = deepcopy(config)
    mappings = {
        "model_name": ("model", "name"),
        "attention_implementation": ("model", "attention_implementation"),
        "output_dir": ("output", "dir"),
        "quant_type": ("quantization", "quant_type"),
        "double_quant": ("quantization", "double_quant"),
        "max_seq_length": ("training", "max_seq_length"),
        "per_device_train_batch_size": ("training", "per_device_train_batch_size"),
        "per_device_eval_batch_size": ("training", "per_device_eval_batch_size"),
        "gradient_accumulation_steps": ("training", "gradient_accumulation_steps"),
        "learning_rate": ("training", "learning_rate"),
        "num_train_epochs": ("training", "num_train_epochs"),
        "bf16": ("training", "bf16"),
        "fp16": ("training", "fp16"),
        "gradient_checkpointing": ("training", "gradient_checkpointing"),
        "logging_steps": ("training", "logging_steps"),
        "eval_strategy": ("training", "eval_strategy"),
        "eval_steps": ("training", "eval_steps"),
        "save_strategy": ("training", "save_strategy"),
        "save_steps": ("training", "save_steps"),
        "save_total_limit": ("training", "save_total_limit"),
        "warmup_ratio": ("training", "warmup_ratio"),
        "lr_scheduler_type": ("training", "lr_scheduler_type"),
        "weight_decay": ("training", "weight_decay"),
        "max_grad_norm": ("training", "max_grad_norm"),
        "optim": ("training", "optim"),
        "seed": ("training", "seed"),
        "dataloader_num_workers": ("training", "dataloader_num_workers"),
        "lora_r": ("lora", "r"),
        "lora_alpha": ("lora", "alpha"),
        "lora_dropout": ("lora", "dropout"),
        "packing": ("training", "packing"),
    }
    for argument, path in mappings.items():
        value = getattr(args, argument, None)
        if value is None:
            continue
        cursor = result
        for key in path[:-1]:
            cursor = cursor.setdefault(key, {})
        cursor[path[-1]] = value
    return result


def add_training_overrides(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-name")
    parser.add_argument(
        "--attention-implementation", choices=("auto", "flash_attention_2", "sdpa")
    )
    parser.add_argument("--output-dir")
    parser.add_argument("--quant-type", choices=("nf4", "fp4"))
    parser.add_argument("--double-quant", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--max-seq-length", type=int)
    parser.add_argument("--per-device-train-batch-size", type=int)
    parser.add_argument("--per-device-eval-batch-size", type=int)
    parser.add_argument("--gradient-accumulation-steps", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--num-train-epochs", type=float)
    parser.add_argument("--bf16", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--fp16", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument(
        "--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=None
    )
    parser.add_argument("--logging-steps", type=int)
    parser.add_argument("--eval-strategy", choices=("steps", "epoch", "no"))
    parser.add_argument("--eval-steps", type=int)
    parser.add_argument("--save-strategy", choices=("steps", "epoch", "no"))
    parser.add_argument("--save-steps", type=int)
    parser.add_argument("--save-total-limit", type=int)
    parser.add_argument("--warmup-ratio", type=float)
    parser.add_argument("--lr-scheduler-type")
    parser.add_argument("--weight-decay", type=float)
    parser.add_argument("--max-grad-norm", type=float)
    parser.add_argument("--optim", choices=("paged_adamw_8bit", "adamw_torch"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--dataloader-num-workers", type=int)
    parser.add_argument("--lora-r", type=int)
    parser.add_argument("--lora-alpha", type=int)
    parser.add_argument("--lora-dropout", type=float)
    parser.add_argument("--packing", action=argparse.BooleanOptionalAction, default=None)


def validate_4090_config(config: dict[str, Any]) -> None:
    training = config["training"]
    quantization = config["quantization"]
    if not quantization.get("enabled") or quantization.get("bits") != 4:
        raise ValueError("The RTX 4090 workflow requires 4-bit QLoRA quantization")
    if quantization.get("quant_type") != "nf4":
        raise ValueError("The production RTX 4090 workflow requires NF4 quantization")
    if quantization.get("compute_dtype") != "bfloat16":
        raise ValueError("The production RTX 4090 workflow requires BF16 compute")
    if training.get("per_device_train_batch_size", 0) < 1:
        raise ValueError("per_device_train_batch_size must be at least 1")
    if training.get("gradient_accumulation_steps", 0) < 1:
        raise ValueError("gradient_accumulation_steps must be at least 1")
    if training.get("max_seq_length", 0) < 128:
        raise ValueError("max_seq_length is unexpectedly small")
    if not training.get("gradient_checkpointing"):
        raise ValueError("gradient checkpointing is mandatory for this workflow")
    if not training.get("bf16") or training.get("fp16"):
        raise ValueError("The default RTX 4090 workflow requires bf16=true and fp16=false")
