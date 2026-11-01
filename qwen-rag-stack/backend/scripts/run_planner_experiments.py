"""Sequential E5A/B/C ablation on one GPU; fail on error or existing artifacts.

Prepare planner data first. This runner never downloads a teacher, changes
splits, substitutes providers or overwrites historical pilots.
"""
import argparse
from pathlib import Path

from scripts.run_pilot_experiments import BACKEND, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--e3-adapter", required=True)
    parser.add_argument("--e5c-adapter", help="Evaluate an already trained E5C adapter; skip smoke/training")
    parser.add_argument("--train-samples", type=int, default=640)
    parser.add_argument("--eval-samples", type=int, default=64)
    parser.add_argument("--conversations", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--max-turn", type=int, default=3)
    args = parser.parse_args()
    logs = BACKEND / "reports" / (args.prefix + "_logs")
    logs.mkdir(parents=True, exist_ok=False)
    config = "training/configs/medical_planner_sft_v1.yaml"
    smoke = f"models/{args.prefix}_smoke"
    pilot = f"models/{args.prefix}_E5C"
    if not args.e5c_adapter:
        run("smoke", ["-m", "training.train_stage1", "--config", config, "--smoke-test",
                       "--max-train-samples", "32", "--max-eval-samples", "8", "--output-dir", smoke], logs)
        run("E5C_train", ["-m", "training.train_stage1", "--config", config,
                           "--max-train-samples", str(args.train_samples), "--max-eval-samples", str(args.eval_samples),
                           "--output-dir", pilot], logs)
    runs = []
    for experiment, adapter in (("E5A", None), ("E5B", args.e3_adapter), ("E5C", args.e5c_adapter or f"{pilot}/final_adapter")):
        name = f"{args.prefix}_{experiment}"
        command = ["-m", "evals.benchmark_dialogue", "--backend", "guided", "--experiment", experiment,
                   "--run-name", name, "--conversations", str(args.conversations), "--max-turn", str(args.max_turn),
                   "--batch-size", str(args.batch_size), "--local-files-only"]
        if adapter:
            command += ["--adapter", adapter]
        run(experiment, command, logs)
        runs.append(f"reports/benchmark/{name}")
    run("compare", ["-m", "evals.compare_runs", *runs, "--output", f"reports/benchmark/{args.prefix}_comparison.md"], logs)


if __name__ == "__main__":
    main()
