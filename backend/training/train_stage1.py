from __future__ import annotations

import argparse
import gc
import logging
import sys
from pathlib import Path
from typing import Any

import torch
from peft import PeftConfig

from training.config import add_training_overrides, apply_cli_overrides, load_config, validate_4090_config
from training.modeling import (
    configure_greedy_generation,
    load_qlora_model,
    load_tokenizer,
    log_gpu_and_model,
)
from training.trainer import OOM_GUIDANCE, build_dataset, build_trainer, load_mixed_rows, save_run_metadata

LOGGER = logging.getLogger(__name__)


def smoke_reload_and_generate(config: dict[str, Any], adapter_dir: Path, prompt: str) -> float:
    """Release the training graph, reload the saved adapter, and generate once."""

    adapter_config = PeftConfig.from_pretrained(adapter_dir)
    LOGGER.info("Verified saved adapter configuration for base model %s", adapter_config.base_model_name_or_path)
    model = load_qlora_model(config, adapter_path=str(adapter_dir), trainable_adapter=False)
    tokenizer = load_tokenizer(config["model"]["name"])
    messages = [{"role": "user", "content": prompt}]
    template_arguments = {"tokenize": True, "add_generation_prompt": True, "return_tensors": "pt"}
    try:
        inputs = tokenizer.apply_chat_template(
            messages, enable_thinking=False, **template_arguments
        )
    except TypeError:
        inputs = tokenizer.apply_chat_template(messages, **template_arguments)
    inputs = inputs.to(model.device)
    model.config.use_cache = True
    configure_greedy_generation(model)
    with torch.inference_mode():
        output = model.generate(
            inputs,
            max_new_tokens=32,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    LOGGER.info("Smoke generation: %s", tokenizer.decode(output[0][inputs.shape[-1] :], skip_special_tokens=True))
    peak_gb = torch.cuda.max_memory_allocated() / 1024**3
    total_vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    LOGGER.info("Smoke-test peak CUDA allocator memory: %.2f GB", peak_gb)
    if peak_gb > total_vram_gb:
        LOGGER.warning(
            "Smoke-test peak %.2f GB exceeds %.2f GB dedicated VRAM under WDDM; "
            "the allocator counter includes shared/virtual GPU memory",
            peak_gb,
            total_vram_gb,
        )
    return peak_gb


def _run_training(
    config: dict[str, Any],
    *,
    max_train_samples: int | None,
    max_eval_samples: int | None,
    smoke_test: bool,
    resume_from_checkpoint: str | None,
    initial_adapter: str | None = None,
) -> Path:
    validate_4090_config(config)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable. Training requires one NVIDIA RTX 4090 24GB GPU.")
    if torch.cuda.device_count() != 1:
        raise RuntimeError(
            f"Expected exactly one visible CUDA device, found {torch.cuda.device_count()}. "
            "Set CUDA_VISIBLE_DEVICES=0."
        )
    tokenizer = load_tokenizer(config["model"]["name"])
    data_dir = config["data"]["processed_dir"]
    mix = config["dataset_mix"]
    seed = int(config["training"]["seed"])
    effective_batch = (
        int(config["training"]["per_device_train_batch_size"])
        * int(config["training"]["gradient_accumulation_steps"])
    )
    LOGGER.info("Single-GPU effective training batch size: %d", effective_batch)
    train_rows = load_mixed_rows(
        data_dir, mix, "train", max_samples=max_train_samples, seed=seed
    )
    eval_rows = load_mixed_rows(
        data_dir, mix, "validation", max_samples=max_eval_samples, seed=seed
    )
    if not train_rows or not eval_rows:
        raise ValueError("Prepared training and validation splits must both contain data")
    LOGGER.info("Loaded %d train and %d evaluation conversations on CPU", len(train_rows), len(eval_rows))

    max_length = int(config["training"]["max_seq_length"])
    packing = bool(config["training"].get("packing", False))
    train_dataset = build_dataset(train_rows, tokenizer, max_length=max_length, packing=packing)
    eval_dataset = build_dataset(eval_rows, tokenizer, max_length=max_length, packing=False)
    LOGGER.info("Tokenized datasets on CPU (packing=%s)", packing)

    model = load_qlora_model(config, adapter_path=initial_adapter)
    log_gpu_and_model(model, config)
    trainer = build_trainer(model, tokenizer, train_dataset, eval_dataset, config, smoke_test=smoke_test)
    try:
        train_result = trainer.train(resume_from_checkpoint=resume_from_checkpoint)
        eval_metrics = trainer.evaluate()
    except torch.cuda.OutOfMemoryError as error:
        LOGGER.error(OOM_GUIDANCE)
        raise RuntimeError(OOM_GUIDANCE) from error

    output_dir = Path(config["output"]["dir"])
    adapter_dir = output_dir / "final_adapter"
    trainer.model.save_pretrained(adapter_dir, safe_serialization=True)
    tokenizer.save_pretrained(adapter_dir)
    peak_gb = torch.cuda.max_memory_allocated() / 1024**3
    total_vram_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    metrics = {
        **train_result.metrics,
        **eval_metrics,
        "peak_gpu_memory_gb": peak_gb,
        "gpu_total_vram_gb": total_vram_gb,
        "gpu_memory_accounting": "PyTorch CUDA allocator; may include shared/virtual memory under WDDM",
    }
    if peak_gb > total_vram_gb:
        LOGGER.warning(
            "PyTorch peak %.2f GB exceeds %.2f GB dedicated VRAM under WDDM; "
            "the allocator counter includes shared/virtual GPU memory",
            peak_gb,
            total_vram_gb,
        )
    LOGGER.info("Saved adapter to %s; peak allocated VRAM %.2f GB", adapter_dir, peak_gb)

    if smoke_test:
        del trainer, model, train_dataset, eval_dataset
        gc.collect()
        torch.cuda.empty_cache()
        metrics["smoke_test_peak_cuda_allocator_gb"] = smoke_reload_and_generate(
            config, adapter_dir, "Tôi bị đau bụng."
        )
    save_run_metadata(config, output_dir, metrics)
    return adapter_dir


def run_training(
    config: dict[str, Any],
    *,
    max_train_samples: int | None,
    max_eval_samples: int | None,
    smoke_test: bool,
    resume_from_checkpoint: str | None,
    initial_adapter: str | None = None,
) -> Path:
    try:
        return _run_training(
            config,
            max_train_samples=max_train_samples,
            max_eval_samples=max_eval_samples,
            smoke_test=smoke_test,
            resume_from_checkpoint=resume_from_checkpoint,
            initial_adapter=initial_adapter,
        )
    except torch.cuda.OutOfMemoryError as error:
        LOGGER.error(OOM_GUIDANCE)
        raise RuntimeError(OOM_GUIDANCE) from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage-1 QLoRA training on one RTX 4090")
    parser.add_argument("--config", required=True)
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--max-eval-samples", type=int)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--resume-from-checkpoint")
    add_training_overrides(parser)
    return parser.parse_args()


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = apply_cli_overrides(load_config(args.config), args)
    run_training(
        config,
        max_train_samples=args.max_train_samples,
        max_eval_samples=args.max_eval_samples,
        smoke_test=args.smoke_test,
        resume_from_checkpoint=args.resume_from_checkpoint,
    )


if __name__ == "__main__":
    main()
