from __future__ import annotations

import argparse
import logging
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge a LoRA adapter without relying on 24GB GPU VRAM")
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.device == "cuda":
        LOGGER.warning("An 8B BF16 merge may exceed RTX 4090 memory; CPU merging is recommended")
    else:
        LOGGER.warning("CPU merge requires sufficient host RAM (64GB preferred) and disk space")

    base = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        dtype=torch.bfloat16,
        device_map={"": args.device},
        low_cpu_mem_usage=True,
    )
    merged = PeftModel.from_pretrained(base, args.adapter).merge_and_unload()
    args.output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(args.output, safe_serialization=True, max_shard_size="5GB")
    AutoTokenizer.from_pretrained(args.base_model).save_pretrained(args.output)
    LOGGER.info("Merged model saved to %s", args.output)


if __name__ == "__main__":
    main()
