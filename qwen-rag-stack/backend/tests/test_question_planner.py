import pytest

from app.services.dialogue import extract_dialogue_state, generate_hypotheses, select_next_medical_question
from app.services.dialogue.knowledge import CONDITIONS, candidates_for
from app.services.dialogue.planner import binary_information_gain, categorical_information_gain
from app.services.dialogue.prompts import validate_generated_question


def plan(*texts):
    roles = ["user", "assistant"]
    messages = [{"role": roles[i % 2], "content": text} for i, text in enumerate(texts)]
    state = extract_dialogue_state(messages)
    return state, select_next_medical_question(messages, state)


def test_spec_example_asks_location_not_diagnosis():
    state, question = plan("Tôi bị đau bụng từ hôm qua.")
    assert question.should_ask and question.slot == "location"
    assert "vị trí" in question.text
    assert question.strategy == "information_gain"
    assert question.information_gain and question.information_gain > 0


def test_timing_is_asked_first_when_missing():
    _, question = plan("Tôi đau đầu")
    assert question.slot == "timing" and "bao lâu" in question.text


def test_red_flag_screen_is_prioritized_with_risk_cues():
    _, question = plan("Bố tôi 72 tuổi tự nhiên bị đau đầu")
    assert question.slot == "red_flag_screen"
    assert question.strategy == "red_flag_priority"
    assert question.text.startswith("Người bệnh")  # relative, not "Bạn"


def test_never_reasks_known_information():
    state, question = plan(
        "Tôi bị đau bụng từ hôm qua.", "Bạn đau ở vị trí nào của bụng?", "vùng trên rốn, nóng rát",
    )
    assert question.slot not in {"timing", "location", "character"}
    assert question.slot in state.missing_information


def test_one_question_per_turn():
    _, question = plan("Tôi bị ho 2 ngày")
    assert question.text.count("?") == 1


def test_stops_when_core_information_is_complete():
    state, question = plan(
        "Tôi đau nửa đầu bên trái, buồn nôn và sợ ánh sáng.", "Bắt đầu từ khi nào?",
        "Đã kéo dài 2 ngày, mức 7/10, không yếu liệt.",
    )
    assert state.conversation_status == "READY_FOR_ASSESSMENT"
    assert not question.should_ask and question.strategy == "complete"


def test_question_budget_stops_endless_asking():
    texts = ["Tôi mệt"]
    for _ in range(6):
        texts += ["Bạn có thể kể thêm không?", "Tôi không rõ"]
    state, question = plan(*texts)
    assert state.questions_asked == 6
    assert state.conversation_status == "READY_FOR_ASSESSMENT"
    assert not question.should_ask


def test_emergency_stops_questioning():
    _, question = plan("Tôi đau đầu dữ dội đột ngột và nói ngọng")
    assert not question.should_ask and question.strategy == "emergency_stop"


def test_optional_budget_allows_followup():
    messages = [{"role": "user", "content": "Tôi ho có đờm 3 ngày, sổ mũi, không khó thở, không đau ngực"}]
    state = extract_dialogue_state(messages)
    assert state.conversation_status == "READY_FOR_ASSESSMENT"
    assert not select_next_medical_question(messages, state).should_ask
    followup = select_next_medical_question(messages, state, optional_budget=1)
    assert followup.should_ask and followup.strategy == "optional_followup"


def test_information_gain_is_zero_for_single_candidate_and_positive_for_split():
    abdominal = candidates_for("abdominal", set())
    gain, answers = categorical_information_gain(abdominal, set(), "location")
    assert gain > 0 and "loc:ho_chau_phai" in answers
    assert categorical_information_gain(abdominal[:1], set(), "location")[0] == 0
    assert binary_information_gain(abdominal, set(), "sym:tieu_chay") > 0


def test_knowledge_base_has_no_probability_like_weights_and_known_profiles():
    profiles = {"headache", "abdominal", "respiratory", "fever", "urinary", "skin", "musculoskeletal", "dizziness", "general"}
    for condition in CONDITIONS:
        assert set(condition.profiles) <= profiles
        assert all(0 < weight <= 2 for weight in condition.supports.values())


def test_hypotheses_refused_until_ready_and_without_percentages():
    state, _ = plan("Tôi bị đau bụng từ hôm qua.")
    assessment = generate_hypotheses(state)
    assert not assessment.eligible and assessment.candidate_conditions == []

    state, _ = plan(
        "Tôi đau bụng từ sáng nay, lúc đầu quanh rốn rồi chuyển xuống bụng dưới bên phải, đau tăng dần 7/10, hơi sốt, buồn nôn",
        "Bạn có nôn ra máu hoặc bụng cứng không?", "Không",
    )
    assessment = generate_hypotheses(state)
    assert assessment.eligible
    names = [item.name for item in assessment.candidate_conditions]
    assert names[0] == "Viêm ruột thừa (cần loại trừ)"
    assert assessment.candidate_conditions[0].care_level == "urgent"
    assert "hôm nay" in assessment.next_action
    dumped = assessment.model_dump_json()
    assert "%" not in dumped and "xác suất" not in dumped.replace("không có xác suất", "")
    for candidate in assessment.candidate_conditions:
        assert all(item.endswith("(bạn cung cấp)") for item in candidate.supporting_evidence)


def test_hypotheses_abstain_when_evidence_is_weak():
    state, _ = plan("Tôi mệt 2 ngày, mức độ nhẹ, không có triệu chứng gì khác")
    assessment = generate_hypotheses(state)
    assert assessment.eligible
    assert assessment.candidate_conditions == []
    assert "chưa đủ" in assessment.uncertainty


def test_denied_key_symptom_excludes_condition():
    state, _ = plan("Tôi đau bụng dưới 2 ngày, mức nhẹ, không tiểu buốt, không sốt, không nôn ra máu")
    names = [c.name for c in candidates_for(state.profile, set(state.features))]
    assert "Viêm bàng quang (nhiễm khuẩn tiết niệu dưới)" not in names


@pytest.mark.parametrize(("reply", "problem"), [
    ("Bạn có thể bị viêm dạ dày. Bạn đau ở đâu?", "premature_diagnosis"),
    ("Bạn nên uống paracetamol 500 mg. Bạn đau ở đâu?", "medication_dose"),
    ("Tôi hiểu.", "no_question"),
    ("Bạn ăn gì chưa?", "off_target"),
])
def test_generated_question_validation(reply, problem):
    assert problem in validate_generated_question(reply, "location")


def test_valid_generated_question_is_accepted():
    assert validate_generated_question("Bạn đau ở vị trí nào của bụng?", "location") == []
