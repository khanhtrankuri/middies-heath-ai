"""Extract train/validation loss curves from a train_stage1 log.

The Hugging Face Trainer prints one dict per logging/eval step; this script
collects them so loss curves can be reported without a saved trainer state.

  python scripts/training_log_summary.py reports/pilot_logs/E2_train.log --output reports/E2_loss.json
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

RECORD = re.compile(r"\{'(?:loss|eval_loss|train_runtime)'[^{}]*\}")


def parse(log: Path) -> dict:
    text = log.read_text(encoding="utf-8", errors="replace").replace("\r", "\n")
    train, evaluation, summary = [], [], {}
    for match in RECORD.finditer(text):
        try:
            record = ast.literal_eval(match.group(0))
        except (ValueError, SyntaxError):
            continue
        if "eval_loss" in record:
            evaluation.append({k: record[k] for k in ("epoch", "eval_loss", "eval_mean_token_accuracy", "eval_runtime") if k in record})
        elif "loss" in record:
            train.append({k: record[k] for k in ("epoch", "loss", "learning_rate", "grad_norm", "mean_token_accuracy") if k in record})
        else:
            summary = record
    # Trainer dicts may still be buffered; the progress lines of
    # MemoryAndProgressCallback are always flushed, so prefer them per series.
    progress_train, progress_eval = [], []
    for line in re.finditer(r"progress epoch=([0-9.]+) step=(\d+) train_loss=(\S+) eval_loss=(\S+) lr=(\S+)", text):
        epoch, step, loss, eval_loss, lr = line.groups()
        if loss != "n/a" and not any(item["step"] == int(step) for item in progress_train):
            progress_train.append({"epoch": float(epoch), "step": int(step), "loss": float(loss),
                                   "learning_rate": None if lr == "n/a" else float(lr)})
        if eval_loss != "n/a" and not any(item["step"] == int(step) for item in progress_eval):
            progress_eval.append({"epoch": float(epoch), "step": int(step), "eval_loss": float(eval_loss)})
    if len(progress_train) > len(train):
        train = progress_train
    if len(progress_eval) > len(evaluation):
        evaluation = progress_eval
    peak = re.findall(r"gpu_peak_gb=([0-9.]+)", text)
    trainable = re.search(r"Trainable parameters: (\d+)\nTrainable %: ([0-9.]+)", text)
    return {
        "train": train, "eval": evaluation, "summary": summary,
        "peak_gpu_gb": max(map(float, peak)) if peak else None,
        "trainable_parameters": int(trainable.group(1)) if trainable else None,
        "trainable_percent": float(trainable.group(2)) if trainable else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = parse(args.log)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    first_eval = result["eval"][0]["eval_loss"] if result["eval"] else None
    last_eval = result["eval"][-1]["eval_loss"] if result["eval"] else None
    print(json.dumps({"train_points": len(result["train"]), "eval_points": len(result["eval"]),
                      "first_eval_loss": first_eval, "last_eval_loss": last_eval,
                      "peak_gpu_gb": result["peak_gpu_gb"], "trainable_parameters": result["trainable_parameters"],
                      "summary": result["summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
