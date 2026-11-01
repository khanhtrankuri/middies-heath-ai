import copy
import json
from pathlib import Path

import pytest

from app.services.dialogue import extract_dialogue_state, select_next_medical_question
from app.services.dialogue.prompts import planner_messages
from training.data.prepare_planner_sft import build_examples, prepare


def source_row():
    return {"id": "c1", "metadata": {"split": "train", "revision": "revision", "group_id": "g1",
             "cleaning_version": "dialogue-clean-v1", "target_disease": "SECRET_FUTURE_DISEASE"},
            "messages": [{"role": "system", "content": "old prompt"},
                         {"role": "user", "content": "Tôi đau bụng từ hôm qua"},
                         {"role": "assistant", "content": "Bạn đau ở vị trí nào của bụng?"},
                         {"role": "user", "content": "Tôi đau bụng dưới"},
                         {"role": "assistant", "content": "Bạn đau mấy điểm trên thang 0 đến 10?"}]}


def test_prefix_only_no_future_disease_and_train_inference_parity():
    row = source_row()
    first = next(example for example, _ in build_examples(row) if example)
    changed = copy.deepcopy(row)
    changed["messages"][3]["content"] = "UNSEEN_FUTURE đau đầu"
    other = next(example for example, _ in build_examples(changed) if example)
    assert first == other
    assert "SECRET_FUTURE" not in json.dumps(first)
    assert first["metadata"]["label_source"] == "auto_filtered_dataset_question"
    history = row["messages"][1:2]
    state = extract_dialogue_state(history)
    assert first["messages"][:-1] == planner_messages(history, state, select_next_medical_question(history, state))
    assert [m["role"] for m in first["messages"]] == ["system", "user", "assistant"]


def test_no_fake_clinician_labels_or_unsafe_targets():
    row = source_row()
    row["messages"][2]["content"] = "<think>reason</think> Bạn đau ở đâu?"
    records = list(build_examples(row))
    assert records[0][0] is None
    assert "reasoning" in records[0][1]["reason"]
    templates = list(build_examples(row, allow_templates=True))
    assert templates[0][0]["metadata"]["label_source"] == "planner_template_unreviewed"


def test_immutable_output_directory(tmp_path):
    with pytest.raises(FileExistsError):
        prepare(Path("unused"), tmp_path, Path("unused"))


def test_e5c_config_selects_only_planner_data_and_best_validation_checkpoint():
    from training.config import load_config, validate_training_config
    config = load_config(Path(__file__).parents[1] / "training/configs/medical_planner_sft_v1.yaml")
    validate_training_config(config)
    assert config["dataset_mix"] == {"vietnamese_planner_sft_v1": 1.0}
    assert config["training"]["load_best_model_at_end"] and not config["training"]["packing"]


def frozen_fixture(tmp_path, *, opening_overlap=False, group_overlap=False):
    from training.data.prepare_planner_sft import digest
    from training.data.prepare_dialogue import DEFAULT_REVISION
    source = tmp_path / "vietnamese_dialogue_v1_strict"
    source.mkdir()
    manifest = {"revision": DEFAULT_REVISION, "file_sha256": {}, "ids": {"strict": {}}}
    for split in ("train", "validation", "test"):
        row = source_row()
        row["id"] = split
        row["metadata"].update(split=split, revision=DEFAULT_REVISION, group_id="same" if group_overlap else split)
        row["messages"][1]["content"] += " " + ("same" if opening_overlap else split)
        path = source / f"{split}.jsonl"
        path.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest["file_sha256"][f"{source.name}/{split}.jsonl"] = digest(path)
        manifest["ids"]["strict"][split] = [split]
    path = tmp_path / "source_manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return source, path


def test_frozen_split_hashes_provenance_and_no_test_targets(tmp_path):
    source, manifest = frozen_fixture(tmp_path)
    output = tmp_path / "derived"
    stats = prepare(source, output, manifest)
    from training.data.planner_validation import verify_prepared
    assert verify_prepared(output)["output_sha256"] == stats["output_sha256"]
    assert stats["splits"]["train"]["kept"] >= 1
    assert not (output / "test.jsonl").exists()
    for split in ("train", "validation"):
        rows = [json.loads(line) for line in (output / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]
        assert all(row["conversation_id"] == split and row["metadata"]["split"] == split for row in rows)
    with (output / "train.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("tampered")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_prepared(output)
    (source / "train.jsonl").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        prepare(source, tmp_path / "invalid", manifest)


def test_leakage_is_excluded_without_reshuffling_and_group_overlap_fails(tmp_path):
    source, manifest = frozen_fixture(tmp_path, opening_overlap=True)
    stats = prepare(source, tmp_path / "derived", manifest)
    assert stats["splits"]["train"]["cross_split_opening_excluded"] == 1
    assert not (tmp_path / "derived/train.jsonl").read_text(encoding="utf-8")
    other = tmp_path / "groups"
    other.mkdir()
    source, manifest = frozen_fixture(other, group_overlap=True)
    with pytest.raises(ValueError, match="leakage"):
        prepare(source, other / "derived", manifest)
