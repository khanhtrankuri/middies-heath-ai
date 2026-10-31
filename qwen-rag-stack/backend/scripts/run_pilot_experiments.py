"""Run the E1/E2/E3 pilot comparison end to end on one GPU.

Steps (each in its own process so CUDA memory is released between them):

1. E1 benchmark: Qwen3-1.7B without adapter
2. E2 LoRA training on N standard-level conversations, then its benchmark
3. E3 LoRA training on N strict-level conversations, then its benchmark
4. Paired comparison report

A *pilot* trains both adapters on the same number of conversations with the
hyperparameters from the E2/E3 configs, so the comparison isolates data
quality at a budget that fits a single consumer GPU. It is not a full-data
run; results must be reported as pilot results.

  python scripts/run_pilot_experiments.py --train-samples 640
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def run(step: str, args: list[str], log_dir: Path) -> None:
    log = log_dir / f"{step}.log"
    print(f"[{time.strftime('%H:%M:%S')}] {step}: {' '.join(args)}", flush=True)
    started = time.perf_counter()
    with log.open("w", encoding="utf-8") as handle:
        result = subprocess.run([sys.executable, *args], cwd=BACKEND, stdout=handle, stderr=subprocess.STDOUT)
    elapsed = time.perf_counter() - started
    print(f"[{time.strftime('%H:%M:%S')}] {step}: exit {result.returncode} after {elapsed / 60:.1f} min (log {log})", flush=True)
    if result.returncode:
        raise SystemExit(f"{step} failed; see {log}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--train-samples", type=int, default=640)
    parser.add_argument("--eval-samples", type=int, default=80)
    parser.add_argument("--eval-steps", type=int, default=10)
    parser.add_argument("--conversations", type=int, default=100, help="test conversations in the benchmark")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--prefix", default="pilot")
    parser.add_argument("--skip", nargs="*", default=[], choices=("E1", "E2", "E3"))
    args = parser.parse_args(argv)
    log_dir = BACKEND / "reports" / f"{args.prefix}_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    bench_common = ["-m", "evals.benchmark_dialogue", "--backend", "hf", "--model", "Qwen/Qwen3-1.7B",
                    "--conversations", str(args.conversations), "--batch-size", str(args.batch_size), "--local-files-only"]
    runs = []
    if "E1" not in args.skip:
        run("E1_benchmark", [*bench_common, "--run-name", "E1_base"], log_dir)
    runs.append("reports/benchmark/E1_base")
    for experiment, config in (("E2", "medical_dialogue_v1.yaml"), ("E3", "medical_dialogue_v1_strict.yaml")):
        output = f"models/{args.prefix}_{experiment}"
        name = f"{experiment}_{args.prefix}_lora"
        if experiment not in args.skip:
            run(f"{experiment}_train", [
                "-m", "training.train_stage1", "--config", f"training/configs/{config}",
                "--max-train-samples", str(args.train_samples), "--max-eval-samples", str(args.eval_samples),
                "--eval-steps", str(args.eval_steps), "--logging-steps", "5", "--save-steps", "100000",
                "--output-dir", output,
            ], log_dir)
            run(f"{experiment}_benchmark", [*bench_common, "--run-name", name, "--adapter", f"{output}/final_adapter"], log_dir)
        runs.append(f"reports/benchmark/{name}")
    run("compare", ["-m", "evals.compare_runs", *runs, "--output", f"reports/benchmark/{args.prefix}_comparison.md"], log_dir)
    (log_dir / "settings.json").write_text(json.dumps(vars(args), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
