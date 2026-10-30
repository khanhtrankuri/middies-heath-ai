import json

import pytest

from training.data.dialogue_quality import assess_conversation, clean_structure, strip_reasoning
from training.data.near_dedup import near_duplicate_clusters
from training.data.prepare_dialogue import E2_DIR, E3_DIR, assign_splits, prepare


def conversation(*turns):
    roles = ["assistant", "user"]
    return [{"role": roles[i % 2], "content": text} for i, text in enumerate(turns)]


GOOD = conversation(
    "<think>plan</think>Chào bạn, hôm nay bạn gặp vấn đề gì?",
    "Tôi bị đau bụng từ hôm qua, đau vùng trên rốn.",
    "<thinking>notes</thinking>Bạn đau mức độ nào trên thang 10? Có buồn nôn không?",
    "Khoảng 5 điểm, có hơi buồn nôn.",
    "Bạn có đang dùng thuốc gì không?",
    "Tôi chưa uống thuốc gì.",
    "Cảm ơn bạn. Bạn nên đi khám nếu đau tăng hoặc nôn ra máu.",
)


def test_strip_reasoning_variants():
    assert strip_reasoning("<think>a</think> Xin chào") == "Xin chào"
    assert strip_reasoning("<thinking>a</thinking>Xin chào") == "Xin chào"
    assert strip_reasoning("lộn xộn</think>Xin chào") == "Xin chào"
    assert strip_reasoning("<think>chưa đóng") is None


def test_good_conversation_passes_both_levels():
    result = assess_conversation(GOOD)
    assert result["standard"] and result["strict"], result["reasons"]
    assert all("<think" not in m["content"] for m in result["messages"])


@pytest.mark.parametrize(("messages", "reason"), [
    ("not a list", "malformed_messages"),
    ([{"role": "tool", "content": "x"}], "invalid_role_or_content"),
    (conversation("<think>x", "Tôi đau"), "unclosed_reasoning"),
    (conversation("<think>x</think>", "Tôi đau"), "empty_message"),
    ([{"role": "assistant", "content": "Chào"}, {"role": "assistant", "content": "Chào"},
      {"role": "user", "content": "Tôi đau đầu"}, {"role": "assistant", "content": "Bao lâu?"}], "consecutive_same_role"),
    (conversation("Chào bạn?", "Tôi đau đầu"), "too_few_turns"),
    (conversation("Hello?", "I have a headache", "How long?", "Two days", "Ok."), "not_vietnamese"),
])
def test_structural_rejections(messages, reason):
    cleaned, reasons = clean_structure(messages)
    assert cleaned is None and reasons == [reason]


def test_unsafe_doctor_turns_are_rejected_at_standard_level():
    dosed = list(GOOD)
    dosed[-1] = {"role": "assistant", "content": "Bạn uống paracetamol 500 mg mỗi 6 giờ."}
    assert "medication_dose" in assess_conversation(dosed)["standard_reasons"]
    emergency = conversation(
        "Chào bạn?", "Tôi đau ngực dữ dội và khó thở.", "Bạn bị bao lâu rồi?", "Từ sáng.", "Bạn nghỉ ngơi nhé.",
    )
    assert "emergency_not_escalated" in assess_conversation(emergency)["standard_reasons"]


def test_role_inversion_and_quality_are_strict_only():
    inverted = list(GOOD)
    inverted[5] = {"role": "user", "content": "Cảm ơn em đã chia sẻ. **Về thuốc:** chị khuyên em đi khám."}
    result = assess_conversation(inverted)
    assert result["standard"] and not result["strict"]
    assert "role_inversion_user" in result["strict_reasons"]
    no_question = conversation(
        "Chào bạn?", "Tôi đau đầu 2 ngày.", "Có thể là đau nửa đầu.", "Vâng.", "Bạn nên nghỉ ngơi.", "Cảm ơn.", "Chúc bạn khỏe.",
    )
    reasons = assess_conversation(no_question)["strict_reasons"]
    assert {"no_followup_question", "premature_diagnosis", "insufficient_history_taking"} <= set(reasons)


def test_near_duplicates_cluster_and_distinct_texts_do_not():
    base = "tôi bị đau bụng vùng trên rốn từ hôm qua kèm buồn nôn và ợ chua sau khi ăn đồ cay rất khó chịu"
    roots, pairs = near_duplicate_clusters([base, base + " ạ", "con tôi bị ho có đờm và sốt nhẹ ba ngày nay rồi bác sĩ"])
    assert roots[0] == roots[1] == 0 and roots[2] == 2 and pairs >= 1


def test_group_split_is_deterministic_and_keeps_groups_whole():
    sizes = {f"g{i}": 10 + i % 7 for i in range(200)}
    first = assign_splits(sizes, (0.8, 0.1, 0.1), seed=7)
    assert first == assign_splits(sizes, (0.8, 0.1, 0.1), seed=7)
    assert first != assign_splits(sizes, (0.8, 0.1, 0.1), seed=8)
    totals = {split: sum(sizes[g] for g, s in first.items() if s == split) for split in ("train", "validation", "test")}
    total = sum(sizes.values())
    assert abs(totals["train"] / total - 0.8) < 0.03
    assert abs(totals["test"] / total - 0.1) < 0.03
    with pytest.raises(ValueError):
        assign_splits(sizes, (0.5, 0.5, 0.5), seed=1)


def _row(index, disease, user_text):
    return {
        "id": f"id-{index:03d}", "target_disease": disease,
        "messages": conversation(
            "<think>p</think>Chào bạn, bạn gặp vấn đề gì?", user_text,
            "Triệu chứng bắt đầu từ khi nào? Mức độ ra sao?", f"Từ hôm qua, mức {index % 9}.",
            "Bạn có dùng thuốc gì chưa?", "Chưa ạ.", "Bạn nên đi khám nếu nặng hơn.",
        ),
    }


def test_prepare_end_to_end_writes_leakage_free_splits(tmp_path):
    symptoms = ["đau đầu", "đau bụng", "ho khan", "sốt", "ngứa da", "đau lưng", "chóng mặt", "tiêu chảy"]
    rows = [
        _row(i, f"Bệnh {i % 12}", f"Tôi bị {symptoms[i % 8]} lần {i}, kèm mệt mỏi thứ {i * 7} không rõ lý do {i * 13}")
        for i in range(120)
    ]
    rows.append(dict(rows[0], id="dup-exact"))  # exact duplicate content
    rows.append({"id": "bad", "messages": "oops"})
    summary = prepare(rows, tmp_path, revision="test-rev", seed=3)
    assert summary["rejected_reasons"]["exact_duplicate"] == 1
    assert summary["rejected_reasons"]["malformed_messages"] == 1
    assert all(value == 0 for value in summary["leakage_checks"]["group_overlap"].values())
    manifest = json.loads((tmp_path / "meddies_dialogue_v1_manifest.json").read_text(encoding="utf-8"))
    ids = manifest["ids"]["standard"]
    assert not set(ids["train"]) & set(ids["test"])
    assert (tmp_path / E2_DIR / "validation.jsonl").read_bytes() == (tmp_path / E3_DIR / "validation.jsonl").read_bytes()
    record = json.loads((tmp_path / E2_DIR / "train.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert record["messages"][0]["role"] == "system"
    assert record["metadata"]["revision"] == "test-rev"
    assert record["metadata"]["cleaning_version"]
    model_input = json.dumps(record["messages"], ensure_ascii=False)
    assert record["metadata"]["target_disease"] not in model_input  # label never in model input
    rejected = (tmp_path / "meddies_dialogue_v1_rejected.jsonl").read_text(encoding="utf-8")
    assert "Tôi bị" not in rejected  # rejection log holds ids and reasons only


def test_fast_red_flag_check_matches_triage_on_regression_cases():
    from pathlib import Path

    from app.triage import find_red_flags
    from training.data.dialogue_quality import has_red_flag

    cases = json.loads((Path(__file__).parents[1] / "evals/safety_cases.json").read_text(encoding="utf-8"))
    for case in cases:
        assert has_red_flag(case["text"]) == bool(find_red_flags(case["text"])), case["id"]
