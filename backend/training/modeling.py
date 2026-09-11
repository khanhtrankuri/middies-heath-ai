from __future__ import annotations

import logging
from typing import Any

import torch
from peft import LoraConfig, PeftModel, get_peft_model, prepare_model_for_kbit_training
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from transformers.utils import is_flash_attn_2_available

LOGGER = logging.getLogger(__name__)
LORA_CANDIDATES = ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj")


def resolve_attention_implementation(preference: str) -> str:
    if preference not in {"auto", "flash_attention_2", "sdpa"}:
        raise ValueError("attention implementation must be auto, flash_attention_2, or sdpa")
    if preference == "sdpa":
        return "sdpa"
    if preference == "flash_attention_2":
        if not is_flash_attn_2_available():
            raise RuntimeError("flash-attn was requested but is not installed or CUDA-compatible")
        return "flash_attention_2"
    if not is_flash_attn_2_available():
        LOGGER.info("flash-attn is unavailable; using PyTorch SDPA")
        return "sdpa"
    LOGGER.info("flash-attn detected; using FlashAttention2")
    return "flash_attention_2"


def discover_lora_targets(model: Any) -> list[str]:
    """Inspect the loaded architecture and return validated linear-layer suffixes."""

    matched_full_names: list[str] = []
    for name, module in model.named_modules():
        leaf = name.rsplit(".", 1)[-1]
        module_type = module.__class__.__name__.lower()
        if leaf in LORA_CANDIDATES and "linear" in module_type:
            matched_full_names.append(name)
    targets = [candidate for candidate in LORA_CANDIDATES if any(
        name == candidate or name.endswith(f".{candidate}") for name in matched_full_names
    )]
    if not targets:
        raise RuntimeError("No supported LoRA linear modules were found in the loaded Qwen architecture")
    LOGGER.info("Exact modules receiving LoRA (%d):\n%s", len(matched_full_names), "\n".join(matched_full_names))
    return targets


def quantization_config(config: dict[str, Any]) -> BitsAndBytesConfig:
    quant = config["quantization"]
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type=quant.get("quant_type", "nf4"),
        bnb_4bit_use_double_quant=bool(quant.get("double_quant", True)),
        bnb_4bit_compute_dtype=torch.bfloat16,
    )


def load_tokenizer(model_name: str) -> Any:
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    return tokenizer


def load_qlora_model(
    config: dict[str, Any], *, adapter_path: str | None = None, trainable_adapter: bool = True
) -> Any:
    model_name = config["model"]["name"]
    attention = resolve_attention_implementation(config["model"].get("attention_implementation", "auto"))
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=quantization_config(config),
        dtype=torch.bfloat16,
        device_map={"": 0},
        attn_implementation=attention,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    if adapter_path:
        model = PeftModel.from_pretrained(model, adapter_path, is_trainable=trainable_adapter)
        LOGGER.info("Loaded %s adapter from %s", "trainable" if trainable_adapter else "frozen", adapter_path)
    else:
        targets = discover_lora_targets(model)
        lora = config["lora"]
        model = get_peft_model(
            model,
            LoraConfig(
                task_type="CAUSAL_LM",
                r=int(lora["r"]),
                lora_alpha=int(lora["alpha"]),
                lora_dropout=float(lora["dropout"]),
                bias=lora.get("bias", "none"),
                target_modules=targets,
            ),
        )
    unexpected_trainable = [
        name for name, parameter in model.named_parameters()
        if parameter.requires_grad and "lora_" not in name
    ]
    if unexpected_trainable:
        raise RuntimeError(
            "Base model parameters must remain frozen; unexpected trainable parameters: "
            + ", ".join(unexpected_trainable[:10])
        )
    model.print_trainable_parameters()
    return model


def model_parameter_counts(model: Any) -> tuple[int, int]:
    if hasattr(model, "get_nb_trainable_parameters"):
        trainable, total = model.get_nb_trainable_parameters()
        return int(trainable), int(total)
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    total = sum(parameter.numel() for parameter in model.parameters())
    return trainable, total


def log_gpu_and_model(model: Any, config: dict[str, Any]) -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required: this workflow is designed for one NVIDIA RTX 4090")
    if torch.cuda.device_count() != 1:
        raise RuntimeError(
            f"Expected exactly one visible CUDA device, found {torch.cuda.device_count()}. "
            "Set CUDA_VISIBLE_DEVICES=0."
        )
    properties = torch.cuda.get_device_properties(0)
    total_vram = properties.total_memory / 1024**3
    trainable, total = model_parameter_counts(model)
    base_dtype = getattr(model.get_input_embeddings().weight, "dtype", "unknown")
    LOGGER.info(
        "GPU: %s\nVRAM total: %.2f GB\nVRAM allocated: %.2f GB\nVRAM reserved: %.2f GB\n"
        "Model: %s\nBase model embedding dtype: %s\nCompute dtype: bfloat16\nQuantization: NF4 4-bit\n"
        "Trainable parameters: %.2f M\nTotal parameters represented: %.2f B",
        properties.name,
        total_vram,
        torch.cuda.memory_allocated() / 1024**3,
        torch.cuda.memory_reserved() / 1024**3,
        config["model"]["name"],
        base_dtype,
        trainable / 1e6,
        total / 1e9,
    )
    if "4090" not in properties.name:
        LOGGER.warning("Validated for RTX 4090 24GB; detected %s", properties.name)
    if total_vram > 25:
        LOGGER.warning("More than 24GB is visible, but no setting will rely on the extra memory")


def configure_greedy_generation(model: Any) -> None:
    """Clear sampling-only defaults so greedy generation is warning-free."""

    for name in ("temperature", "top_p", "top_k", "min_p"):
        if hasattr(model.generation_config, name):
            setattr(model.generation_config, name, None)
