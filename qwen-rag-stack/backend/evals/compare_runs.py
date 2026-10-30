"""Compare benchmark runs (e.g. E1 base vs E2/E3 LoRA) on identical items.

Differences are paired per item and their 95% CIs come from a bootstrap that
resamples whole conversations, since items from one conversation are
correlated. Runs must share the same test file hash and item ids.

  python -m evals.compare_runs reports/benchmark/E1_base reports/benchmark/E2_lora \
      --output reports/benchmark/comparison.md
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

PAIRED_METRICS = (
    ("asks_question", "Hỏi bổ sung (tỷ lệ lượt có câu hỏi)", True),
    ("non_redundant", "Không hỏi lại thông tin đã có", True),
    ("targets_missing", "Hỏi đúng thông tin còn thiếu", True),
    ("relevance", "Question relevance (tỷ lệ slot hỏi thuộc thông tin thiếu)", True),
    ("reference_slot_f1", "F1 slot so với câu hỏi tham chiếu (synthetic)", True),
    ("premature_diagnosis", "Nêu bệnh sớm ở lượt 1–2", False),
    ("over_question_limit", "Hỏi quá 2 câu/lượt", False),
    ("unsafe", "Phản hồi không an toàn (liều thuốc / chẩn đoán chắc chắn)", False),
)


def load_run(path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    run = json.loads((path / "metrics.json").read_text(encoding="utf-8"))
    question_rows, behavior_rows = {}, {}
    for line in (path / "predictions.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        (behavior_rows if "kind" in row else question_rows)[row["item_id"]] = row
    return run, question_rows, behavior_rows


def paired_difference(
    base: dict[str, dict[str, Any]], other: dict[str, dict[str, Any]], metric: str, *, resamples: int = 2000, seed: int = 0
) -> dict[str, Any]:
    clusters: dict[str, list[float]] = defaultdict(list)
    for item_id, row in base.items():
        if item_id not in other or row.get(metric) is None or other[item_id].get(metric) is None:
            continue
        clusters[row["conversation_id"]].append(float(other[item_id][metric]) - float(row[metric]))
    values = [value for items in clusters.values() for value in items]
    if not values:
        return {"diff": None, "ci95": [None, None], "n": 0}
    keys = sorted(clusters)
    rng = random.Random(seed)
    means = []
    for _ in range(resamples):
        sample = [value for _ in keys for value in clusters[keys[rng.randrange(len(keys))]]]
        means.append(sum(sample) / len(sample))
    means.sort()
    return {
        "diff": sum(values) / len(values),
        "ci95": [means[int(0.025 * resamples)], means[int(0.975 * resamples) - 1]],
        "n": len(values),
        "conversations": len(keys),
    }


def _fmt(value: Any, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def compare(paths: list[Path]) -> tuple[dict[str, Any], str]:
    runs = [load_run(path) for path in paths]
    hashes = {run["test_file_sha256"] for run, _, _ in runs}
    if len(hashes) != 1:
        raise ValueError("Runs were evaluated on different test files; comparison would be invalid")
    names = [run["run_name"] for run, _, _ in runs]
    base_run, base_rows, base_behavior = runs[0]
    result: dict[str, Any] = {"runs": names, "baseline": names[0], "metrics": {}, "paired": {}}
    lines = [
        "# So sánh mô hình trên benchmark hỏi bệnh", "",
        f"- Tập kiểm thử: `{base_run['test_file']}` (sha256 `{base_run['test_file_sha256'][:12]}…`)",
        f"- Số mục hỏi bệnh: {len(base_rows)}; số ca hành vi: {len(base_behavior)}",
        "- Chỉ số tự động dựa trên luật, trên dữ liệu synthetic; không phải đánh giá lâm sàng.",
        "- Khoảng tin cậy 95%: bootstrap theo hội thoại.", "",
        "| Chỉ số | " + " | ".join(names) + " |", "|---|" + "---|" * len(names),
    ]
    for metric, label, _ in PAIRED_METRICS:
        cells = []
        for run, _, _ in runs:
            value = run["metrics"]["question_generation"].get(metric, {})
            cells.append(f"{_fmt(value.get('mean'))} [{_fmt(value.get('ci95', [None])[0])}, {_fmt(value.get('ci95', [None, None])[1])}]")
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    coverage = [run["metrics"]["information_completeness"] for run, _, _ in runs]
    lines.append("| Information completeness (độ phủ thông tin cốt lõi) | " + " | ".join(
        f"{_fmt(c.get('mean'))} [{_fmt(c['ci95'][0])}, {_fmt(c['ci95'][1])}]" for c in coverage) + " |")
    for kind in sorted({k for run, _, _ in runs for k, v in run["metrics"]["behavior"].items() if isinstance(v, dict)}):
        cells = []
        for run, _, _ in runs:
            value = run["metrics"]["behavior"].get(kind)
            cells.append(f"{value['passed']}/{value['n']}" if isinstance(value, dict) else "—")
        lines.append(f"| Ca hành vi: {kind} (đạt/tổng) | " + " | ".join(cells) + " |")
    lines.append("| Unsafe response rate | " + " | ".join(
        _fmt(run["metrics"]["unsafe_response_rate"]["mean"]) for run, _, _ in runs) + " |")
    lines.append("| Latency trung bình (giây/mục, batch) | " + " | ".join(
        _fmt(run["metrics"]["question_generation"]["latency_seconds"]["mean"], 2) for run, _, _ in runs) + " |")
    lines.append("| Peak GPU memory (GB) | " + " | ".join(
        _fmt(run["runtime"].get("peak_gpu_memory_gb"), 2) for run, _, _ in runs) + " |")
    lines += ["", f"## Chênh lệch ghép cặp so với `{names[0]}`", "",
              "| So sánh | Chỉ số | Chênh lệch | CI 95% | n mục |", "|---|---|---|---|---|"]
    for run, rows, _ in runs[1:]:
        result["paired"][run["run_name"]] = {}
        for metric, label, higher_is_better in PAIRED_METRICS:
            diff = paired_difference(base_rows, rows, metric)
            result["paired"][run["run_name"]][metric] = diff
            low, high = diff["ci95"]
            significant = low is not None and (low > 0 or high < 0)
            marker = ""
            if significant:
                marker = " ✓" if (diff["diff"] > 0) == higher_is_better else " ✗"
            lines.append(f"| {run['run_name']} − {names[0]} | {label} | {_fmt(diff['diff'])}{marker} | "
                         f"[{_fmt(low)}, {_fmt(high)}] | {diff['n']} |")
    lines += ["", "✓ = cải thiện có CI không chứa 0; ✗ = xấu đi có CI không chứa 0."]
    for run, _, _ in runs:
        result["metrics"][run["run_name"]] = run["metrics"]
    return result, "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", type=Path, help="Run directories; the first is the baseline")
    parser.add_argument("--output", type=Path, default=Path("reports/benchmark/comparison.md"))
    args = parser.parse_args(argv)
    result, markdown = compare(args.runs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    args.output.with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
