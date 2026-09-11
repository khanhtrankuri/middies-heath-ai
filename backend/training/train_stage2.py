from __future__ import annotations

import argparse
import logging

from training.config import add_training_overrides, apply_cli_overrides, load_config
from training.train_stage1 import run_training


def main() -> None:
    parser = argparse.ArgumentParser(description="Optional Stage-2 mixed-replay QLoRA training")
    parser.add_argument("--config", required=True)
    parser.add_argument("--stage1-adapter")
    parser.add_argument("--strategy", choices=("continue", "fresh-after-merge"), default="continue")
    parser.add_argument("--merged-stage1-model")
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--max-eval-samples", type=int)
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--resume-from-checkpoint")
    add_training_overrides(parser)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config = apply_cli_overrides(load_config(args.config), args)

    if args.strategy == "continue":
        if not args.stage1_adapter:
            parser.error("--stage1-adapter is required for the continue strategy")
        initial_adapter = args.stage1_adapter
    else:
        if not args.merged_stage1_model:
            parser.error("--merged-stage1-model is required for fresh-after-merge")
        config["model"]["name"] = args.merged_stage1_model
        initial_adapter = None
    run_training(
        config,
        max_train_samples=args.max_train_samples,
        max_eval_samples=args.max_eval_samples,
        smoke_test=args.smoke_test,
        resume_from_checkpoint=args.resume_from_checkpoint,
        initial_adapter=initial_adapter,
    )


if __name__ == "__main__":
    main()
