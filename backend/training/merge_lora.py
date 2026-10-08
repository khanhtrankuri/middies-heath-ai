from __future__ import annotations

import argparse
import logging
from pathlib import Path

import torch
from peft import PeftConfig

from training.config import SUPPORTED_MODELS
from training.modeling import load_adapter, load_base_model, load_tokenizer

LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge a LoRA adapter without relying on 24GB GPU VRAM")
    parser.add_argument("--base-model", choices=sorted(SUPPORTED_MODELS))
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    adapter_config = PeftConfig.from_pretrained(args.adapter)
    base_model = args.base_model or adapter_config.base_model_name_or_path
    if base_model not in SUPPORTED_MODELS:
        parser.error("Adapter does not identify a supported base model; pass --base-model")
    if args.device == "cpu":
        LOGGER.info("Merging on CPU keeps GPU VRAM free but requires sufficient host RAM")

    base = load_base_model(
        base_model,
        dtype=torch.bfloat16,
        device_map={"": args.device},
        attention_implementation="sdpa",
    )
    merged = load_adapter(base, args.adapter, trainable=False).merge_and_unload()
    args.output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(args.output, safe_serialization=True, max_shard_size="5GB")
    load_tokenizer(base_model).save_pretrained(args.output)
    LOGGER.info("Merged model saved to %s", args.output)


if __name__ == "__main__":
    main()
