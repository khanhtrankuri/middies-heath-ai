"""Stage-1 Qwen3-8B QLoRA for Kaggle GPU T4 x2 (run from the backend directory).

Kaggle setup
===========
1. Select Accelerator = GPU T4 x2 and enable Internet in notebook settings.
2. Upload/clone this repository into /kaggle/working/meddies-health-ai, then:

   %cd /kaggle/working/meddies-health-ai/backend
   %pip install "transformers==4.57.6" "trl==0.29.1" "peft==0.20.0" "accelerate>=1.4,<2" "bitsandbytes>=0.45.5,<1" "datasets>=3,<5"

   Keep Kaggle's CUDA-enabled PyTorch. Restart the notebook session after pip
   if any of these libraries were already imported.

3. Upload prepared data and pass --data-dir /kaggle/input/YOUR-DATASET/processed,
   or prepare it once (in a notebook shell cell, before launching torchrun):

   !python -m training.data.prepare_meddies --configs vietnamese english --output-dir /kaggle/working/processed --seed 42

   Expected layout: processed/{vietnamese,english}/{train,validation}.jsonl.
   Each line contains a messages list with role/content chat messages.

4. Smoke test, then train (separate notebook cells):

   !torchrun --standalone --nnodes=1 --nproc-per-node=2 -m training.train_kaggle_t4 --data-dir /kaggle/working/processed --smoke-test --output-dir /kaggle/working/stage1_t4_smoke

   !torchrun --standalone --nnodes=1 --nproc-per-node=2 -m training.train_kaggle_t4 --data-dir /kaggle/working/processed --output-dir /kaggle/working/stage1_t4

Defaults: up to 10,000 training / 256 validation conversations, one epoch,
1024 tokens, LoRA r=8/alpha=16, NF4 + FP16 + SDPA, batch 1/GPU, accumulation 8.
Effective batch = 1 * 8 * 2 = 16. Set --max-train-samples 0 for all training
data; --max-eval-samples 0 evaluates all validation data (may be expensive).
DDP replicates the quantized model: each copy must fit in one T4's ~16 GB.

Smoke mode caps data at 100/30 conversations and trains 3 optimizer steps,
then evaluates and saves an adapter; it does not run generation/reload.
For OOM, try --max-seq-length 512 --lora-r 4 --lora-alpha 8.
--max-steps can limit a longer run to the available Kaggle session time.

Resume by adding --resume-from-checkpoint /kaggle/input/YOUR-OUTPUT/checkpoint-N
and choosing a new writable --output-dir (or reuse the original output dir).
A checkpoint contains optimizer/scheduler/RNG state; final_adapter alone
cannot resume training. Save/download Kaggle outputs before the session ends.
Only rank 0 writes final_adapter/ and run_metadata/run.json. Intermediate
checkpoint-N directories are managed by Trainer with a retention limit of 2.

This script uses the repository's training/data and training/trainer helpers;
upload the backend folder, not only this file. No 4090 YAML is required.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
DATASET_MIX = {"vietnamese": 0.65, "english": 0.35}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model-name", default="Qwen/Qwen3-8B")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("/kaggle/working/stage1_t4"))
    parser.add_argument("--max-train-samples", type=int, default=10000, help="0 = all")
    parser.add_argument("--max-eval-samples", type=int, default=256, help="0 = all")
    parser.add_argument("--max-seq-length", type=int, default=1024)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--num-train-epochs", type=float, default=1.0)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--eval-steps", type=int, default=100)
    parser.add_argument("--save-steps", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume-from-checkpoint", type=Path)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args(argv)
    for name in ("gradient_accumulation_steps", "learning_rate", "num_train_epochs",
                 "lora_r", "lora_alpha", "eval_steps", "save_steps"):
        if getattr(args, name) <= 0:
            parser.error(f"--{name.replace('_', '-')} must be positive")
    if args.max_seq_length < 128 or args.max_seq_length % 8:
        parser.error("--max-seq-length must be at least 128 and a multiple of 8")
    if args.max_steps != -1 and args.max_steps < 1:
        parser.error("--max-steps must be -1 or a positive integer")
    if args.max_train_samples < 0 or args.max_eval_samples < 0:
        parser.error("sample limits must be nonnegative (0 = all)")
    if args.smoke_test:
        args.max_steps = 3
        args.max_train_samples = min(args.max_train_samples or 100, 100)
        args.max_eval_samples = min(args.max_eval_samples or 30, 30)
    return args


def distributed_ranks(environ: Any) -> tuple[int, int]:
    if (environ.get("WORLD_SIZE") != "2" or environ.get("LOCAL_WORLD_SIZE") != "2"
            or environ.get("LOCAL_RANK") not in {"0", "1"}
            or environ.get("RANK") != environ.get("LOCAL_RANK")):
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
                raise FileNotFoundError(f"Missing prepared data: {path}. See --help for preparation instructions.")
    if args.resume_from_checkpoint:
        checkpoint = args.resume_from_checkpoint
        for filename in ("trainer_state.json", "optimizer.pt", "scheduler.pt", "adapter_config.json"):
            if not (checkpoint / filename).is_file():
                raise ValueError(f"Not a complete resumable Trainer checkpoint: missing {checkpoint / filename}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()) and not args.resume_from_checkpoint:
        raise ValueError("Output directory is not empty. Choose a new --output-dir or use --resume-from-checkpoint.")


def trainer_kwargs(args: argparse.Namespace, local_rank: int) -> dict[str, Any]:
    return dict(
        output_dir=str(args.output_dir),
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        num_train_epochs=args.num_train_epochs,
        max_steps=args.max_steps,
        fp16=True,
        bf16=False,
        tf32=False,
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        local_rank=local_rank,
        ddp_backend="nccl",
        ddp_find_unused_parameters=False,
        ddp_broadcast_buffers=False,
        ddp_timeout=3600,
        logging_steps=1 if args.smoke_test else 10,
        eval_strategy="steps",
        eval_steps=1 if args.smoke_test else args.eval_steps,
        save_strategy="steps",
        save_steps=1 if args.smoke_test else args.save_steps,
        save_total_limit=2,
        save_only_model=False,
        prediction_loss_only=True,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        weight_decay=0.01,
        max_grad_norm=1.0,
        optim="paged_adamw_8bit",
        seed=args.seed,
        data_seed=args.seed,
        dataloader_num_workers=0,
        report_to="none",
        push_to_hub=False,
        remove_unused_columns=False,
        label_names=["labels"],
    )


def tokenize_rows(rows: list[dict[str, Any]], tokenizer: Any, max_length: int) -> tuple[list, int]:
    from training.data.processing import tokenize_with_assistant_only_loss

    tokenized = []
    skipped = 0
    for row in rows:
        try:
            tokenized.append(tokenize_with_assistant_only_loss(
                tokenizer, row["messages"], max_length=max_length,
            ))
        except ValueError as error:
            # A long initial prompt may consume the entire token budget. Never
            # train on an all-masked example; other malformed data must fail.
            if str(error) != "No assistant tokens remain after truncation":
                raise
            skipped += 1
    if not tokenized:
        raise ValueError("No usable conversations remain. Increase --max-seq-length or check the data.")
    return tokenized, skipped


def prepare_adapter_precision(model: Any) -> None:
    import torch

    trainable = [(name, parameter) for name, parameter in model.named_parameters() if parameter.requires_grad]
    if not trainable:
        raise RuntimeError("No trainable LoRA parameters were found")
    for name, parameter in trainable:
        if "lora_" not in name:
            raise RuntimeError(f"Unexpected trainable base weight: {name}")
        # FP16 AMP's GradScaler expects trainable adapter weights in FP32.
        parameter.data = parameter.data.to(torch.float32)


def load_t4_model(args: argparse.Namespace, local_rank: int) -> Any:
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig

    from training.modeling import discover_lora_targets

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
        model, use_gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
    )
    model = get_peft_model(model, LoraConfig(
        task_type="CAUSAL_LM", r=args.lora_r, lora_alpha=args.lora_alpha,
        lora_dropout=0.05, bias="none", target_modules=discover_lora_targets(model),
    ))
    prepare_adapter_precision(model)
    return model


def main() -> None:
    args = parse_args()
    rank, local_rank = distributed_ranks(os.environ)
    validate_paths(args)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    # Kaggle T4 pairs communicate over PCIe; NCCL still uses SHM/socket paths.
    os.environ.setdefault("NCCL_P2P_DISABLE", "1")
    os.environ.setdefault("NCCL_IB_DISABLE", "1")
    logging.basicConfig(
        level=logging.INFO if rank == 0 else logging.WARNING,
        format=f"%(asctime)s [rank {rank}] %(levelname)s %(message)s",
    )

    import torch
    import torch.distributed as dist
    from datasets import Dataset
    from transformers import AutoTokenizer, Trainer, TrainingArguments, set_seed

    from training.data.processing import AssistantOnlyDataCollator
    from training.trainer import load_mixed_rows, save_run_metadata

    if not torch.cuda.is_available() or torch.cuda.device_count() != 2:
        raise RuntimeError("Exactly two visible CUDA GPUs are required. Select Kaggle GPU T4 x2.")
    torch.cuda.set_device(local_rank)
    set_seed(args.seed)
    properties = torch.cuda.get_device_properties(local_rank)
    LOGGER.info("GPU %d: %s (%.2f GiB); global effective batch = %d",
                local_rank, properties.name, properties.total_memory / 1024**3,
                2 * args.gradient_accumulation_steps)
    if "T4" not in properties.name:
        LOGGER.warning("This profile targets T4; detected %s", properties.name)

    try:
        # Initialize Accelerate/DDP before loading each rank's quantized copy.
        training_args = TrainingArguments(**trainer_kwargs(args, local_rank))
        tokenizer = AutoTokenizer.from_pretrained(args.model_name, use_fast=True)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "right"
        datasets = {}
        data_stats = {}
        for split, limit in (("train", args.max_train_samples), ("validation", args.max_eval_samples)):
            rows = load_mixed_rows(args.data_dir, DATASET_MIX, split, max_samples=limit or None, seed=args.seed)
            tokenized, skipped = tokenize_rows(rows, tokenizer, args.max_seq_length)
            datasets[split] = Dataset.from_list(tokenized)
            data_stats[split] = {"loaded": len(rows), "used": len(tokenized), "no_assistant_tokens": skipped}
            LOGGER.info("%s: %s", split, data_stats[split])
            del rows, tokenized

        torch.cuda.reset_peak_memory_stats(local_rank)
        model = load_t4_model(args, local_rank)
        if rank == 0:
            model.print_trainable_parameters()
        # Already-tokenized assistant-only labels work with the base Trainer.
        # TRL 0.29.1 SFTTrainer unconditionally casts QLoRA adapters to BF16,
        # which is unsuitable for T4 + FP16 AMP; keep our adapters in FP32.
        trainer = Trainer(
            model=model, args=training_args,
            train_dataset=datasets["train"], eval_dataset=datasets["validation"],
            processing_class=tokenizer, data_collator=AssistantOnlyDataCollator(tokenizer),
        )
        result = trainer.train(resume_from_checkpoint=(
            str(args.resume_from_checkpoint) if args.resume_from_checkpoint else None
        ))
        metrics = {**result.metrics, **trainer.evaluate()}
        memory = {
            "rank": rank, "gpu": properties.name,
            "total_vram_gib": properties.total_memory / 1024**3,
            "peak_allocated_gib": torch.cuda.max_memory_allocated(local_rank) / 1024**3,
        }
        gpu_metrics: list[Any] = [None, None]
        dist.all_gather_object(gpu_metrics, memory)
        adapter_dir = args.output_dir / "final_adapter"
        # All ranks enter Trainer's save API; Trainer restricts writes to rank 0.
        trainer.save_model(str(adapter_dir))
        trainer.save_state()
        if trainer.is_world_process_zero():
            tokenizer.save_pretrained(adapter_dir)
            config = {
                "model": {"name": args.model_name},
                "quantization": {"bits": 4, "quant_type": "nf4", "compute_dtype": "float16"},
                "dataset_mix": DATASET_MIX, "arguments": vars(args),
                "world_size": 2, "effective_batch_size": 2 * args.gradient_accumulation_steps,
            }
            save_run_metadata(config, args.output_dir, {**metrics, "gpus": gpu_metrics, "data": data_stats})
            LOGGER.info("Saved final adapter: %s", adapter_dir)
        trainer.accelerator.wait_for_everyone()
    except torch.cuda.OutOfMemoryError as error:
        raise RuntimeError(
            "T4 out of memory. Retry with --max-seq-length 512 --lora-r 4 --lora-alpha 8 "
            "and a new output directory. Each DDP model copy must fit on one GPU."
        ) from error
    finally:
        if dist.is_initialized():
            dist.destroy_process_group()


if __name__ == "__main__":
    main()
