from app.services.dialogue import extract_dialogue_state
from app.services.dialogue.lexicon import fold_aligned, question_topics


def user(text):
    return {"role": "user", "content": text}


def assistant(text):
    return {"role": "assistant", "content": text}


def test_fold_preserves_length_for_span_mapping():
    text = "Tôi đau bụng dữ dội ĐÃ 2 ngày"
    assert len(fold_aligned(text)) == len(text)
    assert fold_aligned(text) == "toi dau bung du doi da 2 ngay"


def test_extracts_core_slots_from_one_message():
    state = extract_dialogue_state([user("Tôi bị đau bụng từ hôm qua, đau vùng trên rốn kiểu nóng rát, khoảng 6/10")])
    assert state.chief_complaint == "đau bụng"
    assert state.profile == "abdominal"
    assert state.onset.value == "từ hôm qua"
    assert state.location.value == "vùng trên rốn"
    assert state.character.value == "nóng rát"
    assert state.severity.value == "6/10"
    assert {"loc:thuong_vi", "char:nong_rat", "sym:dau_bung", "dur:acute"} <= set(state.features)
    assert all(slot.source == "user_reported" for slot in (state.onset, state.location, state.severity))


def test_unaccented_input_and_negation():
    state = extract_dialogue_state([user("toi dau dau 3 ngay nay, khong sot, khong buon non")])
    assert state.chief_complaint == "đau đầu"
    assert state.duration.value == "3 ngay nay"
    assert {item.key for item in state.negated_symptoms} == {"sot", "buon_non"}
    assert state.associated_symptoms == []
    assert "neg:sot" in state.features


def test_missing_fields_stay_empty_and_are_listed():
    state = extract_dialogue_state([user("Tôi đau đầu")])
    assert state.onset is None and state.duration is None and state.location is None
    assert state.medications == [] and state.allergies == []
    assert state.missing_information[0] == "timing"
    assert state.conversation_status == "COLLECTING"


def test_state_persists_across_turns_and_short_answers_fill_asked_slot():
    messages = [
        user("Tôi bị đau bụng từ hôm qua."),
        assistant("Bạn đau ở vị trí nào của bụng?"),
        user("bên phải phía dưới"),
        assistant("Nếu 0 là không đau và 10 là đau nhất, bạn đau mấy điểm?"),
        user("khoảng 5"),
        assistant("Bạn có kèm buồn nôn, sốt hay tiêu chảy không?"),
        user("Không ạ"),
    ]
    state = extract_dialogue_state(messages)
    assert state.onset.value == "từ hôm qua"  # first turn value kept
    assert state.location.value
    assert state.severity.value == "khoảng 5" and state.severity.source == "user_answer"
    assert "associated_symptoms" in state.answered_slots
    assert state.questions_asked == 3
    assert "location" not in state.missing_information
    assert "severity" not in state.missing_information


def test_negative_answer_to_red_flag_question_completes_screen():
    messages = [
        user("Tôi đau đầu 2 ngày, đau cả đầu, 4/10, kèm sổ mũi"),
        assistant("Bạn có đau đầu dữ dội đột ngột, yếu liệt hay nói khó không?"),
        user("Không có"),
    ]
    state = extract_dialogue_state(messages)
    assert "red_flag_screen" in state.answered_slots
    assert state.conversation_status == "READY_FOR_ASSESSMENT"


def test_unspecified_yes_to_red_flag_question_escalates():
    messages = [
        user("Tôi đau bụng"),
        assistant("Bạn có nôn ra máu hoặc đi ngoài phân đen không?"),
        user("Có ạ"),
    ]
    state = extract_dialogue_state(messages)
    assert state.emergency_flags
    assert state.conversation_status == "EMERGENCY"


def test_relative_is_tracked_as_other_subject():
    state = extract_dialogue_state([user("Mẹ tôi 70 tuổi bị sốt 39 độ từ sáng nay")])
    assert state.subject == "other"
    assert state.age.value == "70 tuổi"
    assert state.max_temperature_c == 39.0
    assert "sym:sot_cao" in state.features
    assert state.duration is None  # age is not a symptom duration


def test_none_answers_for_history_medication_allergy():
    state = extract_dialogue_state([
        user("Tôi ho 3 ngày, không có bệnh nền, chưa uống thuốc gì, không dị ứng thuốc nào")
    ])
    assert [item.value for item in state.relevant_history] == ["không có (người dùng xác nhận)"]
    assert [item.value for item in state.medications] == ["không có (người dùng xác nhận)"]
    assert [item.value for item in state.allergies] == ["không có (người dùng xác nhận)"]


def test_ambiguous_words_without_context_are_not_symptoms():
    # "họ" (they) is not "ho" (cough); "đau hông" is not "đau họng".
    state = extract_dialogue_state([user("Họ nói tôi bị đau hông bên phải")])
    keys = {item.key for item in state.symptoms}
    assert "ho" not in keys and "dau_hong" not in keys
    assert "dau_hong_lung" in keys


def test_profile_emergency_symptom_not_in_triage_is_escalated():
    state = extract_dialogue_state([user("Tôi đau bụng, đi ngoài phân đen từ sáng")])
    assert "đi ngoài ra máu" in state.emergency_flags
    assert state.conversation_status == "EMERGENCY"


def test_question_topics_detect_slots():
    topics = question_topics("Cơn đau bắt đầu từ khi nào? Bạn có dị ứng thuốc gì không?")
    assert topics.slots == {"timing", "allergies"}
    assert question_topics("Tôi hiểu rồi.").slots == set()
