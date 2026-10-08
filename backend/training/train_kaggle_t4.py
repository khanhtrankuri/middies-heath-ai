"""Train Stage-1 Qwen3 with QLoRA on a Kaggle T4 x2 accelerator.

Run from the repository's ``backend`` directory. In Kaggle, select the
``GPU T4 x2`` accelerator and enable Internet for the initial model download.

Install the dependencies without replacing Kaggle's CUDA-enabled PyTorch::

    %pip install -q \
      "transformers==4.57.6" "trl==0.29.1" "peft==0.20.0" \
      "accelerate>=1.4,<2" "bitsandbytes>=0.45.5,<1" "datasets>=3,<5"

Smoke test first::

    !torchrun --standalone --nnodes=1 --nproc-per-node=2 \
      -m training.train_kaggle_t4 \
      --data-dir /kaggle/input/meddies-processed/processed \
      --output-dir /kaggle/working/stage1_t4_smoke \
      --smoke-test

Then start a normal run in a fresh output directory::

    !torchrun --standalone --nnodes=1 --nproc-per-node=2 \
      -m training.train_kaggle_t4 \
      --data-dir /kaggle/input/meddies-processed/processed \
      --output-dir /kaggle/working/stage1_t4

Defaults use Qwen3-8B, NF4 QLoRA, FP16, SDPA, 1 sample per GPU and eight
gradient-accumulation steps. The global effective batch size is therefore 16.
Each DDP rank owns one quantized model replica on one T4. Pass
``--max-train-samples 0 --max-eval-samples 0`` to consume all prepared rows.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any, Mapping

LOGGER = logging.getLogger(__name__)
DATASET_MIX = {"vietnamese": 0.45, "english": 0.20, "RandomQA": 0.35}
WORLD_SIZE = 2


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--model-name", default="Qwen/Qwen3-8B")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("/kaggle/working/stage1_t4")
    )
    parser.add_argument("--max-train-samples", type=int, default=10_000, help="0 = all")
    parser.add_argument("--max-eval-samples", type=int, default=256, help="0 = all")
    parser.add_argument("--max-seq-length", type=int, default=1024)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--num-train-epochs", type=float, default=1.0)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument(
        "--lora-target-modules", nargs="+", default=["q_proj", "v_proj"]
    )
    parser.add_argument("--eval-steps", type=int, default=100)
    parser.add_argument("--save-steps", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume-from-checkpoint", type=Path)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args(argv)

    positive = (
        "gradient_accumulation_steps",
        "learning_rate",
        "num_train_epochs",
        "lora_r",
        "lora_alpha",
        "eval_steps",
        "save_steps",
    )
    for name in positive:
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if not 0 <= args.lora_dropout < 1:
        parser.error("--lora-dropout must be in [0, 1)")
    if args.max_seq_length < 128 or args.max_seq_length % 8:
        parser.error("--max-seq-length must be at least 128 and a multiple of 8")
    if args.max_steps != -1 and args.max_steps < 1:
        parser.error("--max-steps must be -1 or a positive integer")
    if args.max_train_samples < 0 or args.max_eval_samples < 0:
        parser.error("sample limits must be nonnegative (0 = all)")
    if len(set(args.lora_target_modules)) != len(args.lora_target_modules):
        parser.error("--lora-target-modules cannot contain duplicates")
    if args.smoke_test:
        args.max_steps = 3
        args.max_train_samples = min(args.max_train_samples or 100, 100)
        args.max_eval_samples = min(args.max_eval_samples or 30, 30)
    return args


def distributed_ranks(environ: Mapping[str, str]) -> tuple[int, int]:
    valid = (
        environ.get("WORLD_SIZE") == str(WORLD_SIZE)
        and environ.get("LOCAL_WORLD_SIZE") == str(WORLD_SIZE)
        and environ.get("LOCAL_RANK") in {"0", "1"}
        and environ.get("RANK") == environ.get("LOCAL_RANK")
    )
    if not valid:
        raise RuntimeError(
            "Launch with torchrun --standalone --nnodes=1 --nproc-per-node=2 "
            "-m training.train_kaggle_t4 --data-dir PATH. Select Kaggle GPU T4 x2."
        )
    return int(environ["RANK"]), int(environ["LOCAL_RANK"])


def validate_paths(args: argparse.Namespace) -> None:
    for source in DATASET_MIX:
        for split in ("train", "validation"):
            path = args.data_dir / source / f"{split}.jsonl"
            if not path.is_file():
                raise FileNotFoundError(
                    f"Missing prepared data: {path}. Upload backend/data/processed "
                    "as a Kaggle Dataset and pass its processed directory to --data-dir."
                )
    if args.resume_from_checkpoint:
        checkpoint = args.resume_from_checkpoint
        required = (
            "trainer_state.json",
            "optimizer.pt",
            "scheduler.pt",
            "adapter_config.json",
        )
        for filename in required:
            if not (checkpoint / filename).is_file():
                raise ValueError(
                    f"Not a complete resumable Trainer checkpoint: missing "
                    f"{checkpoint / filename}"
                )
    if (
        args.output_dir.exists()
        and any(args.output_dir.iterdir())
        and not args.resume_from_checkpoint
    ):
        raise ValueError(
            "Output directory is not empty. Choose a new --output-dir or use "
            "--resume-from-checkpoint."
        )


def trainer_kwargs(args: argparse.Namespace, local_rank: int) -> dict[str, Any]:
    return {
        "output_dir": str(args.output_dir),
        "per_device_train_batch_size": 1,
        "per_device_eval_batch_size": 1,
        "gradient_accumulation_steps": args.gradient_accumulation_steps,
        "learning_rate": args.learning_rate,
        "num_train_epochs": args.num_train_epochs,
        "max_steps": args.max_steps,
        "fp16": True,
        "bf16": False,
        "tf32": False,
        "gradient_checkpointing": True,
        "gradient_checkpointing_kwargs": {"use_reentrant": False},
        "local_rank": local_rank,
        "ddp_backend": "nccl",
        "ddp_find_unused_parameters": False,
        "ddp_broadcast_buffers": False,
        "ddp_timeout": 3600,
        "logging_steps": 1 if args.smoke_test else 10,
        "eval_strategy": "steps",
        "eval_steps": 1 if args.smoke_test else args.eval_steps,
        "save_strategy": "steps",
        "save_steps": 1 if args.smoke_test else args.save_steps,
        "save_total_limit": 2,
        "save_only_model": False,
        "prediction_loss_only": True,
        "warmup_ratio": 0.03,
        "lr_scheduler_type": "cosine",
        "weight_decay": 0.01,
        "max_grad_norm": 1.0,
        "optim": "paged_adamw_8bit",
        "seed": args.seed,
        "data_seed": args.seed,
        "dataloader_num_workers": 0,
        "report_to": "none",
        "push_to_hub": False,
        "remove_unused_columns": False,
        "label_names": ["labels"],
    }


def prepare_adapter_precision(model: Any) -> None:
    """Keep only LoRA parameters trainable and FP32 for FP16 GradScaler."""

    import torch

    trainable = [
        (name, parameter)
        for name, parameter in model.named_parameters()
        if parameter.requires_grad
    ]
    if not trainable:
        raise RuntimeError("No trainable LoRA parameters were found")
    for name, parameter in trainable:
        if "lora_" not in name:
            raise RuntimeError(f"Unexpected trainable base weight: {name}")
        parameter.data = parameter.data.to(torch.float32)


def load_t4_model(args: argparse.Namespace, local_rank: int) -> Any:
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    from training.modeling import validate_lora_targets

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        quantization_config=BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.float16,
        ),
        dtype=torch.float16,
        device_map={"": local_rank},
        attn_implementation="sdpa",
    )
    model.config.use_cache = False
    model = prepare_model_for_kbit_training(
        model,
        use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    validate_lora_targets(model, args.lora_target_modules)
    model = get_peft_model(
        model,
        LoraConfig(
            task_type="CAUSAL_LM",
            r=args.lora_r,
            lora_alpha=args.lora_alpha,
            lora_dropout=args.lora_dropout,
            bias="none",
            target_modules=args.lora_target_modules,
        ),
    )
    prepare_adapter_precision(model)
    return model


def main() -> None:
    args = parse_args()
    rank, local_rank = distributed_ranks(os.environ)
    validate_paths(args)

    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    os.environ.setdefault("NCCL_P2P_DISABLE", "1")
    os.environ.setdefault("NCCL_IB_DISABLE", "1")
    os.environ.setdefault("TORCH_NCCL_ASYNC_ERROR_HANDLING", "1")
    logging.basicConfig(
        level=logging.INFO if rank == 0 else logging.WARNING,
        format=f"%(asctime)s [rank {rank}] %(levelname)s %(name)s: %(message)s",
    )

    import torch
    import torch.distributed as dist
    from transformers import AutoTokenizer, Trainer, TrainingArguments, set_seed

    from training.data.processing import AssistantOnlyDataCollator
    from training.trainer import build_dataset, load_mixed_rows, save_run_metadata

    if not torch.cuda.is_available() or torch.cuda.device_count() != WORLD_SIZE:
        raise RuntimeError(
            "Exactly two visible CUDA GPUs are required. Select Kaggle GPU T4 x2."
        )
    torch.cuda.set_device(local_rank)
    set_seed(args.seed)
    properties = torch.cuda.get_device_properties(local_rank)
    effective_batch = WORLD_SIZE * args.gradient_accumulation_steps
    LOGGER.info(
        "GPU %d: %s (%.2f GiB); global effective batch size=%d",
        local_rank,
        properties.name,
        properties.total_memory / 1024**3,
        effective_batch,
    )
    if "T4" not in properties.name:
        LOGGER.warning("This profile targets T4; detected %s", properties.name)

    try:
        training_args = TrainingArguments(**trainer_kwargs(args, local_rank))
        tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "right"

        datasets = {}
        data_stats = {}
        for split, limit, packing in (
            ("train", args.max_train_samples, True),
            ("validation", args.max_eval_samples, False),
        ):
            rows = load_mixed_rows(
                args.data_dir,
                DATASET_MIX,
                split,
                max_samples=limit or None,
                seed=args.seed,
            )
            dataset = build_dataset(
                rows, tokenizer, max_length=args.max_seq_length, packing=packing
            )
            datasets[split] = dataset
            data_stats[split] = {
                "loaded_conversations": len(rows),
                "tokenized_examples": len(dataset),
                "packing": packing,
            }
            LOGGER.info("%s data: %s", split, data_stats[split])
            del rows

        torch.cuda.reset_peak_memory_stats(local_rank)
        model = load_t4_model(args, local_rank)
        if rank == 0:
            model.print_trainable_parameters()

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=datasets["train"],
            eval_dataset=datasets["validation"],
            processing_class=tokenizer,
            data_collator=AssistantOnlyDataCollator(tokenizer),
        )
        result = trainer.train(
            resume_from_checkpoint=(
                str(args.resume_from_checkpoint) if args.resume_from_checkpoint else None
            )
        )
        metrics = {**result.metrics, **trainer.evaluate()}
        memory = {
            "rank": rank,
            "gpu": properties.name,
            "total_vram_gib": properties.total_memory / 1024**3,
            "peak_allocated_gib": torch.cuda.max_memory_allocated(local_rank) / 1024**3,
        }
        gpu_metrics: list[Any] = [None] * WORLD_SIZE
        dist.all_gather_object(gpu_metrics, memory)

        adapter_dir = args.output_dir / "final_adapter"
        trainer.save_model(str(adapter_dir))
        trainer.save_state()
        if trainer.is_world_process_zero():
            tokenizer.save_pretrained(adapter_dir)
            config = {
                "model": {"name": args.model_name},
                "quantization": {
                    "bits": 4,
                    "quant_type": "nf4",
                    "compute_dtype": "float16",
                },
                "dataset_mix": DATASET_MIX,
                "arguments": vars(args),
                "world_size": WORLD_SIZE,
                "effective_batch_size": effective_batch,
            }
            save_run_metadata(
                config,
                args.output_dir,
                {**metrics, "gpus": gpu_metrics, "data": data_stats},
            )
            LOGGER.info("Saved final adapter: %s", adapter_dir)
        trainer.accelerator.wait_for_everyone()
    except torch.cuda.OutOfMemoryError as error:
        raise RuntimeError(
            "T4 out of memory. Retry in a new output directory with "
            "--max-seq-length 512 --lora-r 4 --lora-alpha 8. Each DDP model "
            "replica must fit on one GPU."
        ) from error
    finally:
        if dist.is_initialized():
            dist.destroy_process_group()


if __name__ == "__main__":
    main()
