"""Validation loss of a model (base or base + LoRA adapter) on the training validation set.

Uses the same rows, windowing, assistant-only masking and per-window averaging
as Trainer.evaluate in train_stage1, so the base model's number is directly
comparable with the eval_loss reported for fine-tuned adapters.

  python scripts/eval_val_loss.py --config training/configs/medical_dialogue_v1_strict.yaml --max-eval-samples 80
  python scripts/eval_val_loss.py --config ... --adapter models/pilot_E3/final_adapter
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch  # noqa: E402

from training.config import load_config  # noqa: E402
from training.data.processing import AssistantOnlyDataCollator  # noqa: E402
from training.modeling import load_adapter, load_base_model, load_tokenizer  # noqa: E402
from training.trainer import build_dataset, load_mixed_rows  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True)
    parser.add_argument("--adapter")
    parser.add_argument("--max-eval-samples", type=int, default=80)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = load_config(args.config)
    name = config["model"]["name"]
    tokenizer = load_tokenizer(name)
    rows = load_mixed_rows(config["data"]["processed_dir"], config["dataset_mix"], "validation",
                           max_samples=args.max_eval_samples, seed=int(config["training"]["seed"]))
    dataset = build_dataset(rows, tokenizer, max_length=int(config["training"]["max_seq_length"]), packing=False)
    model = load_base_model(name, dtype=torch.bfloat16, attention_implementation="sdpa", device_map={"": 0})
    if args.adapter:
        model = load_adapter(model, args.adapter, trainable=False)
    model.eval()
    collator = AssistantOnlyDataCollator(tokenizer)
    losses = []
    with torch.inference_mode():
        for index in range(len(dataset)):
            batch = {key: value.to(model.device) for key, value in collator([dataset[index]]).items()}
            losses.append(float(model(**batch).loss))
    result = {"model": name, "adapter": args.adapter, "conversations": len(rows), "windows": len(losses),
              "eval_loss": sum(losses) / len(losses)}
    print(json.dumps(result, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
