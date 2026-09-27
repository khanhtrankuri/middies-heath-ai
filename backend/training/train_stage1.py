from __future__ import annotations

import argparse
import gc
import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _select_gpu_from_cli_before_cuda(argv: list[str]) -> None:
    """Apply --gpu before importing libraries that may initialize CUDA."""

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--gpu", type=int)
    args, _ = parser.parse_known_args(argv)
    if args.gpu is not None and args.gpu >= 0:
        os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu)


_select_gpu_from_cli_before_cuda(sys.argv[1:])

import torch
from peft import PeftConfig

from training.config import add_training_overrides, apply_cli_overrides, load_config, validate_training_config
from training.modeling import (
    configure_greedy_generation,
    load_training_model,
    load_tokenizer,
    log_hardware,
)
from training.trainer import OOM_GUIDANCE, build_dataset, build_trainer, load_mixed_rows, save_run_metadata

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for noisy in ("httpx", "httpcore", "urllib3", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def select_gpu(gpu_index: int | None) -> None:
    """Restrict this process to one physical GPU before CUDA is initialized."""

    if gpu_index is None:
        return
    if gpu_index < 0:
        raise ValueError("--gpu must be a non-negative physical GPU index")
    if torch.cuda.is_initialized():
        if os.environ.get("CUDA_VISIBLE_DEVICES") == str(gpu_index):
            LOGGER.info("Physical GPU %d was selected before CUDA initialization", gpu_index)
            return
        raise RuntimeError("GPU selection must happen before CUDA is initialized")
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_index)
    LOGGER.info("Selected physical GPU %d via CUDA_VISIBLE_DEVICES", gpu_index)


def smoke_reload_and_generate(config: dict[str, Any], adapter_dir: Path, prompt: str) -> float:
    """Release the training graph, reload the saved adapter, and generate once."""

    adapter_config = PeftConfig.from_pretrained(adapter_dir)
    LOGGER.info("Verified saved adapter configuration for base model %s", adapter_config.base_model_name_or_path)
    model = load_training_model(config, adapter_path=str(adapter_dir), trainable_adapter=False)
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
    if isinstance(inputs, Mapping):
        prompt_length = inputs["input_ids"].shape[-1]
        generation_inputs = dict(inputs)
    else:
        prompt_length = inputs.shape[-1]
        generation_inputs = {"inputs": inputs}
    model.config.use_cache = True
    configure_greedy_generation(model)
    with torch.inference_mode():
        output = model.generate(
            **generation_inputs,
            max_new_tokens=32,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    LOGGER.info(
        "Smoke generation: %s",
        tokenizer.decode(output[0][prompt_length:], skip_special_tokens=True),
    )
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
    validate_training_config(config)
    if not torch.cuda.is_available():
        if torch.version.cuda is None:
            raise RuntimeError(
                "The installed PyTorch build is CPU-only. Install a CUDA-enabled "
                "PyTorch wheel for this environment, then retry training."
            )
        raise RuntimeError("CUDA is unavailable. Training requires an NVIDIA CUDA GPU.")
    log_hardware(config)
    tokenizer = load_tokenizer(config["model"]["name"])
    data_dir = config["data"]["processed_dir"]
    mix = config["dataset_mix"]
    seed = int(config["training"]["seed"])
    effective_batch = (
        int(config["training"]["per_device_train_batch_size"])
        * int(config["training"]["gradient_accumulation_steps"])
    )
    LOGGER.info("Single-GPU effective training batch size: %d", effective_batch)
    if config["model"]["name"] == "Qwen/Qwen3-0.6B":
        LOGGER.info(
            "Qwen3-0.6B detected. Current batch=%d. Estimated VRAM headroom may allow "
            "a larger batch; no setting was changed automatically.",
            int(config["training"]["per_device_train_batch_size"]),
        )
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

    model = load_training_model(config, adapter_path=initial_adapter)
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage-1 BF16 LoRA training on a CUDA GPU")
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--gpu",
        type=int,
        help="Physical GPU index from nvidia-smi (overrides CUDA_VISIBLE_DEVICES)",
    )
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--max-eval-samples", type=int)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--resume-from-checkpoint")
    add_training_overrides(parser)
    return parser.parse_args(argv)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parse_args()
    configure_logging()
    select_gpu(args.gpu)
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
