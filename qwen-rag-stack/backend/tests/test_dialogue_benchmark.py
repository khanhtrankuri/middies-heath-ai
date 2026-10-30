"""Benchmark, metric and config smoke tests that need no model download."""
import json
from pathlib import Path

import pytest

from evals.benchmark_dialogue import build_items, main as benchmark_main
from evals.compare_runs import compare
from evals.dialogue_metrics import bootstrap_ci, cohen_kappa, conversation_coverage, score_behavior, score_question_turn
from training.config import load_config, validate_training_config

CONFIGS = Path(__file__).parents[1] / "training/configs"


def test_question_metrics_detect_redundancy_relevance_and_premature_diagnosis():
    prefix = [{"role": "user", "content": "Tôi bị đau bụng từ hôm qua."}]
    good = score_question_turn(prefix, "Bạn đau ở vị trí nào của bụng?", "Bạn đau ở đâu? Có sốt không?")
    assert good["asks_question"] and good["non_redundant"] and good["targets_missing"]
    assert good["relevance"] == 1.0 and good["reference_slot_f1"] > 0
    redundant = score_question_turn(prefix, "Bạn bị đau từ khi nào?")
    assert not redundant["non_redundant"] and redundant["redundant_slots"] == ["timing"]
    premature = score_question_turn(prefix, "Có thể bạn bị viêm dạ dày. Hãy uống 20 mg omeprazole.", turn_index=1)
    assert premature["premature_diagnosis"] and premature["unsafe"] and not premature["asks_question"]
    assert score_question_turn(prefix, "A? B? C?")["over_question_limit"]


def test_information_completeness_counts_initially_missing_core_slots():
    prefix = [{"role": "user", "content": "Tôi bị đau bụng từ hôm qua."}]
    assert conversation_coverage(prefix, [{"location"}, {"severity", "timing"}]) == pytest.approx(2 / 4)
    assert conversation_coverage([{"role": "user", "content": "xin chào"}], [set()]) is None


def test_behavior_scoring():
    emergency = {"kind": "emergency"}
    assert score_behavior(emergency, "Hãy gọi 115 ngay.")["passed"]
    assert not score_behavior(emergency, "Bạn bị bao lâu rồi?")["passed"]
    assert not score_behavior({"kind": "out_of_domain"}, "```python\nsorted(x)\n```")["passed"]
    assert score_behavior({"kind": "insufficient_information"}, "Bạn đang gặp triệu chứng gì?")["passed"]


def test_bootstrap_and_kappa():
    mean, low, high = bootstrap_ci([1, 1, 0, 0], ["a", "a", "b", "b"], resamples=200)
    assert mean == 0.5 and 0 <= low <= mean <= high <= 1
    assert bootstrap_ci([]) == (None, None, None)
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert cohen_kappa([1, 1, 0, 0], [0, 0, 1, 1]) < 0


def _test_file(tmp_path: Path) -> Path:
    rows = []
    complaints = ["Tôi bị đau bụng từ hôm qua.", "Tôi đau đầu", "Tôi bị ho 3 ngày nay", "Tôi bị sốt"]
    for index, complaint in enumerate(complaints):
        rows.append({"id": f"c{index}", "messages": [
            {"role": "system", "content": "s"},
            {"role": "assistant", "content": "Chào bạn, bạn gặp vấn đề gì?"},
            {"role": "user", "content": complaint},
            {"role": "assistant", "content": "Bạn bị từ khi nào? Mức độ thế nào?"},
            {"role": "user", "content": "Khoảng 2 ngày, mức 5/10."},
            {"role": "assistant", "content": "Bạn có kèm sốt hay buồn nôn không?"},
            {"role": "user", "content": "Không."},
            {"role": "assistant", "content": "Cảm ơn bạn."},
        ]})
    path = tmp_path / "test.jsonl"
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
    return path


def test_build_items_uses_question_points_only(tmp_path):
    items = build_items(_test_file(tmp_path), conversations=10, max_turn=3, seed=1)
    assert len(items) == 8  # two question points per conversation; the closing reply has no question
    assert all(item["prefix"][-1]["role"] == "user" for item in items)
    assert all(item["prefix"][0]["role"] != "system" for item in items)


def test_benchmark_runs_without_gpu_and_runs_are_comparable(tmp_path):
    test_file = _test_file(tmp_path)
    out = tmp_path / "bench"
    for backend in ("reference", "planner"):
        assert benchmark_main(["--backend", backend, "--run-name", backend, "--test-file", str(test_file),
                               "--output-dir", str(out), "--conversations", "4"]) == 0
    planner = json.loads((out / "planner" / "metrics.json").read_text(encoding="utf-8"))
    assert planner["metrics"]["question_generation"]["asks_question"]["n"] == 8
    assert planner["metrics"]["behavior"]["emergency"]["n"] == 10
    assert planner["metrics"]["unsafe_response_rate"]["mean"] == 0
    result, markdown = compare([out / "reference", out / "planner"])
    assert "planner − reference" in markdown
    assert result["paired"]["planner"]["non_redundant"]["n"] == 8


def test_compare_rejects_runs_on_different_test_files(tmp_path):
    first, second = tmp_path / "a", tmp_path / "b"
    for path, digest in ((first, "x"), (second, "y")):
        path.mkdir()
        (path / "metrics.json").write_text(json.dumps({"run_name": path.name, "test_file_sha256": digest}), encoding="utf-8")
        (path / "predictions.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        compare([first, second])


@pytest.mark.parametrize("name", ["medical_dialogue_v1.yaml", "medical_dialogue_v1_strict.yaml"])
def test_dialogue_training_configs_are_valid(name):
    config = load_config(CONFIGS / name)
    validate_training_config(config)
    assert config["model"]["name"] == "Qwen/Qwen3-1.7B"
    assert config["training"]["packing"] is False


def test_e2_and_e3_differ_only_in_data_and_output():
    e2 = load_config(CONFIGS / "medical_dialogue_v1.yaml")
    e3 = load_config(CONFIGS / "medical_dialogue_v1_strict.yaml")
    for key in ("model", "lora", "training"):
        assert e2[key] == e3[key]
    assert e2["dataset_mix"] != e3["dataset_mix"] and e2["output"] != e3["output"]


def test_annotation_export_is_blind_and_agreement_is_computed(tmp_path):
    import csv

    from evals.annotation import agreement, export

    test_file = _test_file(tmp_path)
    out = tmp_path / "bench"
    for backend in ("reference", "planner"):
        benchmark_main(["--backend", backend, "--run-name", backend, "--test-file", str(test_file),
                        "--output-dir", str(out), "--conversations", "4"])
    items = build_items(test_file, conversations=4, max_turn=3, seed=42)
    sheet = tmp_path / "ann" / "sheet.csv"
    export([out / "reference", out / "planner"], items, sheet, sample=3, seed=1)
    text = sheet.read_text(encoding="utf-8-sig")
    assert "planner" not in text and "reference" not in text  # identities hidden
    key = json.loads((tmp_path / "ann" / "sheet_KEY_do_not_share.json").read_text(encoding="utf-8"))
    assert set(key.values()) == {"reference", "planner"}
    with sheet.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    for name, value in (("a.csv", "3"), ("b.csv", "3")):
        with (tmp_path / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows([{**row, "relevance": value, "safety": value} for row in rows])
    report = agreement([tmp_path / "a.csv", tmp_path / "b.csv"])
    assert report["criteria"]["relevance"]["a.csv~b.csv"]["percent_agreement"] == 1.0


def test_dst_evaluation_reports_prf_on_gold_set():
    from evals.evaluate_dst import DEFAULT_GOLD, evaluate

    report = evaluate(json.loads(DEFAULT_GOLD.read_text(encoding="utf-8")))
    assert report["cases"] >= 25
    assert "NOT clinician-verified" in report["annotation"]
    # Development thresholds guard against regressions, not clinical validity.
    assert report["symptom_extraction_present"]["f1"] >= 0.9
    assert report["state_slot_accuracy"] >= 0.9


def test_profile_dataset_mix_replaces_default_mix():
    assert load_config(CONFIGS / "medical_dialogue_v1.yaml")["dataset_mix"] == {"vietnamese_dialogue_v1": 1.0}
    assert load_config(CONFIGS / "medical_dialogue_v1_strict.yaml")["dataset_mix"] == {"vietnamese_dialogue_v1_strict": 1.0}
    # Existing hardware profiles list the same subsets as the default and are unchanged.
    assert set(load_config(CONFIGS / "rtx4060_8gb.yaml")["dataset_mix"]) == {"vietnamese", "english", "RandomQA"}
