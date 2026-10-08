from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_MODELS = frozenset({"Qwen/Qwen3-1.7B", "Qwen/Qwen3-0.6B"})

# Resolution order is always: defaults -> hardware YAML -> explicit CLI.
DEFAULT_CONFIG: dict[str, Any] = {
    "model": {"name": "Qwen/Qwen3-1.7B", "dtype": "bfloat16", "attention_implementation": "auto"},
    "lora": {"r": 8, "alpha": 16, "dropout": 0.05, "bias": "none", "target_modules": ["q_proj", "v_proj"]},
    "data": {"processed_dir": "data/processed"},
    "dataset_mix": {"vietnamese": 0.45, "english": 0.20, "RandomQA": 0.35},
    "training": {
        "max_seq_length": 1024,
        "per_device_train_batch_size": 1,
        "per_device_eval_batch_size": 1,
        "gradient_accumulation_steps": 16,
        "learning_rate": 1.0e-4,
        "num_train_epochs": 1,
        "bf16": True,
        "fp16": False,
        "gradient_checkpointing": True,
        "packing": True,
        "optim": "adamw_torch",
        "warmup_ratio": 0.03,
        "lr_scheduler_type": "cosine",
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        "dataloader_num_workers": 2,
        "logging_steps": 10,
        "eval_strategy": "steps",
        "eval_steps": 500,
        "save_strategy": "steps",
        "save_steps": 500,
        "save_total_limit": 2,
        "seed": 42,
    },
    "output": {"dir": "models/stage1_consult"},
    "tracking": {"enabled": False},
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"Training config must be a YAML mapping: {config_path}")
    return deep_merge(DEFAULT_CONFIG, loaded)


def apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Apply only explicit CLI values; CLI has the highest precedence."""
    result = deepcopy(config)
    mappings = {
        "model_name": ("model", "name"),
        "attention_implementation": ("model", "attention_implementation"),
        "output_dir": ("output", "dir"),
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
        "lora_target_modules": ("lora", "target_modules"),
        "packing": ("training", "packing"),
        "wandb": ("tracking", "enabled"),
        "wandb_project": ("tracking", "project"),
        "wandb_run_name": ("tracking", "run_name"),
        "wandb_mode": ("tracking", "mode"),
        "wandb_log_model": ("tracking", "log_model"),
    }
    for argument, path_parts in mappings.items():
        value = getattr(args, argument, None)
        if value is None:
            continue
        cursor = result
        for key in path_parts[:-1]:
            cursor = cursor.setdefault(key, {})
        cursor[path_parts[-1]] = value
    return result


def add_training_overrides(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-name", choices=sorted(SUPPORTED_MODELS))
    parser.add_argument("--attention-implementation", choices=("auto", "flash_attention_2", "sdpa"))
    parser.add_argument("--output-dir")
    parser.add_argument("--max-seq-length", type=int)
    parser.add_argument("--per-device-train-batch-size", type=int)
    parser.add_argument("--per-device-eval-batch-size", type=int)
    parser.add_argument("--gradient-accumulation-steps", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--num-train-epochs", type=float)
    parser.add_argument("--bf16", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--fp16", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--gradient-checkpointing", action=argparse.BooleanOptionalAction, default=None)
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
    parser.add_argument("--optim", choices=("adamw_torch_fused", "adamw_torch"))
    parser.add_argument("--seed", type=int)
    parser.add_argument("--dataloader-num-workers", type=int)
    parser.add_argument("--lora-r", type=int)
    parser.add_argument("--lora-alpha", type=int)
    parser.add_argument("--lora-dropout", type=float)
    parser.add_argument("--lora-target-modules", nargs="+")
    parser.add_argument("--packing", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--wandb", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--wandb-project")
    parser.add_argument("--wandb-run-name")
    parser.add_argument("--wandb-mode", choices=("online", "offline", "disabled"))
    parser.add_argument("--wandb-log-model", choices=("false", "end", "checkpoint"))


def validate_training_config(config: dict[str, Any]) -> None:
    """Validate BF16 LoRA independently of a particular NVIDIA GPU model."""
    model = config.get("model", {})
    training = config.get("training", {})
    lora = config.get("lora", {})
    if model.get("name") not in SUPPORTED_MODELS:
        raise ValueError(f"model.name must be one of: {', '.join(sorted(SUPPORTED_MODELS))}")
    if model.get("dtype") != "bfloat16":
        raise ValueError("model.dtype must be bfloat16 for the BF16 LoRA training path")
    if not training.get("bf16") or training.get("fp16"):
        raise ValueError("BF16 LoRA requires training.bf16=true and training.fp16=false")
    for key in ("per_device_train_batch_size", "per_device_eval_batch_size", "gradient_accumulation_steps"):
        if int(training.get(key, 0)) < 1:
            raise ValueError(f"training.{key} must be at least 1")
    if int(training.get("max_seq_length", 0)) < 128:
        raise ValueError("training.max_seq_length is unexpectedly small")
    if training.get("optim") not in {"adamw_torch", "adamw_torch_fused"}:
        raise ValueError("training.optim must be adamw_torch or adamw_torch_fused")
    if int(lora.get("r", 0)) < 1 or int(lora.get("alpha", 0)) < 1:
        raise ValueError("LoRA rank and alpha must be positive")
    if not 0 <= float(lora.get("dropout", -1)) < 1:
        raise ValueError("lora.dropout must be in [0, 1)")
    targets = lora.get("target_modules")
    if not isinstance(targets, list) or not targets or not all(isinstance(x, str) and x for x in targets):
        raise ValueError("lora.target_modules must be a non-empty list of module names")
    if len(set(targets)) != len(targets):
        raise ValueError("lora.target_modules cannot contain duplicates")
    mix = config.get("dataset_mix", {})
    if not mix or "RandomQuestion" in mix or any(float(weight) <= 0 for weight in mix.values()):
        raise ValueError("dataset_mix must use positive SFT subsets and cannot include prompt-only RandomQuestion")
