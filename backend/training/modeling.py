from __future__ import annotations

import logging
from typing import Any

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.utils import is_flash_attn_2_available

from training.config import SUPPORTED_MODELS

LOGGER = logging.getLogger(__name__)


def resolve_attention_implementation(preference: str) -> str:
    if preference not in {"auto", "flash_attention_2", "sdpa"}:
        raise ValueError("attention implementation must be auto, flash_attention_2, or sdpa")
    if preference == "sdpa":
        return "sdpa"
    if preference == "flash_attention_2":
        if not is_flash_attn_2_available():
            raise RuntimeError("flash-attn was requested but is not installed or CUDA-compatible")
        return "flash_attention_2"
    if is_flash_attn_2_available():
        LOGGER.info("FlashAttention2 is available and selected")
        return "flash_attention_2"
    LOGGER.info("FlashAttention2 is unavailable; using PyTorch SDPA")
    return "sdpa"


def load_tokenizer(model_name: str, *, local_files_only: bool = False) -> Any:
    tokenizer = AutoTokenizer.from_pretrained(
        model_name, use_fast=True, local_files_only=local_files_only
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return tokenizer


def load_base_model(
    model_name: str,
    *,
    dtype: torch.dtype = torch.bfloat16,
    attention_implementation: str = "auto",
    device_map: Any = None,
    local_files_only: bool = False,
    use_cache: bool = False,
) -> Any:
    """Shared, non-quantized loader for SFT, future preference training, and inference."""
    if model_name not in SUPPORTED_MODELS and not local_files_only:
        raise ValueError(f"Unsupported pretrained model {model_name!r}")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=dtype,
        device_map=device_map,
        attn_implementation=resolve_attention_implementation(attention_implementation),
        local_files_only=local_files_only,
    )
    model.config.use_cache = use_cache
    return model


def _available_linear_suffixes(model: Any) -> dict[str, list[str]]:
    available: dict[str, list[str]] = {}
    for name, module in model.named_modules():
        if "linear" not in module.__class__.__name__.lower():
            continue
        available.setdefault(name.rsplit(".", 1)[-1], []).append(name)
    return available


def validate_lora_targets(model: Any, target_modules: list[str]) -> list[str]:
    available = _available_linear_suffixes(model)
    missing = [target for target in target_modules if target not in available]
    if missing:
        raise ValueError(
            "Configured LoRA target module(s) do not exist as linear layers: " + ", ".join(missing)
        )
    matched = [name for target in target_modules for name in available[target]]
    LOGGER.info("Validated %d exact LoRA target layers", len(matched))
    return matched


def assert_only_lora_trainable(model: Any) -> None:
    unexpected = [
        name for name, parameter in model.named_parameters()
        if parameter.requires_grad and "lora_" not in name
    ]
    if unexpected:
        raise RuntimeError(
            "Base model parameters must remain frozen; unexpected trainable parameters: "
            + ", ".join(unexpected[:10])
        )


def attach_lora(model: Any, lora: dict[str, Any]) -> Any:
    targets = list(lora["target_modules"])
    validate_lora_targets(model, targets)
    for parameter in model.parameters():
        parameter.requires_grad = False
    model = get_peft_model(
        model,
        LoraConfig(
            task_type="CAUSAL_LM",
            r=int(lora["r"]),
            lora_alpha=int(lora["alpha"]),
            lora_dropout=float(lora["dropout"]),
            bias=str(lora.get("bias", "none")),
            target_modules=targets,
        ),
    )
    assert_only_lora_trainable(model)
    return model


def load_adapter(model: Any, adapter_path: str, *, trainable: bool = False) -> Any:
    model = PeftModel.from_pretrained(model, adapter_path, is_trainable=trainable)
    if trainable:
        assert_only_lora_trainable(model)
    return model


def load_training_model(
    config: dict[str, Any], *, adapter_path: str | None = None, trainable_adapter: bool = True
) -> Any:
    model = load_base_model(
        config["model"]["name"],
        dtype=torch.bfloat16,
        attention_implementation=config["model"].get("attention_implementation", "auto"),
        device_map={"": 0},
        use_cache=False,
    )
    if config["training"].get("gradient_checkpointing"):
        model.gradient_checkpointing_enable(
            gradient_checkpointing_kwargs={"use_reentrant": False}
        )
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
    if adapter_path:
        model = load_adapter(model, adapter_path, trainable=trainable_adapter)
    else:
        model = attach_lora(model, config["lora"])
    assert_only_lora_trainable(model)
    log_model_summary(model, config)
    return model


def model_parameter_counts(model: Any) -> tuple[int, int]:
    if hasattr(model, "get_nb_trainable_parameters"):
        trainable, total = model.get_nb_trainable_parameters()
        return int(trainable), int(total)
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total = sum(parameter.numel() for parameter in model.parameters())
    return trainable, total


def log_model_summary(model: Any, config: dict[str, Any]) -> None:
    trainable, total = model_parameter_counts(model)
    LOGGER.info(
        "Base model: %s\nTotal parameters: %d\nTrainable parameters: %d\nTrainable %%: %.6f\n"
        "LoRA rank: %s\nLoRA alpha: %s\nLoRA target modules: %s",
        config["model"]["name"], total, trainable, 100 * trainable / total if total else 0.0,
        config["lora"]["r"], config["lora"]["alpha"], ", ".join(config["lora"]["target_modules"]),
    )


def log_hardware(config: dict[str, Any]) -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; BF16 LoRA training requires a CUDA GPU")
    properties = torch.cuda.get_device_properties(0)
    LOGGER.info(
        "GPU name: %s\nVRAM total: %.2f GB\nCUDA version: %s\nPyTorch version: %s\n"
        "BF16 support: %s\nFlashAttention availability: %s",
        properties.name, properties.total_memory / 1024**3, torch.version.cuda, torch.__version__,
        torch.cuda.is_bf16_supported(), is_flash_attn_2_available(),
    )
    if config["training"].get("bf16") and not torch.cuda.is_bf16_supported():
        raise RuntimeError(f"{properties.name} does not support BF16 required by this profile")


def configure_greedy_generation(model: Any) -> None:
    for name in ("temperature", "top_p", "top_k", "min_p"):
        if hasattr(model.generation_config, name):
            setattr(model.generation_config, name, None)
