import asyncio
import json

import pytest

from app.services.dialogue import extract_dialogue_state, select_next_medical_question
from app.services.dialogue.question_generator import generate_question, resolve_question
from app.services.dialogue.prompts import planner_messages


def context(text="Tôi đau bụng từ hôm qua"):
    history = [{"role": "user", "content": text}]
    state = extract_dialogue_state(history)
    return history, state, select_next_medical_question(history, state)


@pytest.mark.parametrize("question,reason", [
    ("Bạn đau ở đâu? Đau mấy ngày? Có sốt không?", "multiple_questions"),
    ("Bạn đau ở đâu và bắt đầu từ khi nào?", "multiple_slots"),
    ("Bạn có thể bị viêm dạ dày. Bạn đau ở đâu?", "premature_diagnosis"),
    ("Uống 500 mg thuốc. Bạn đau ở đâu?", "medication_dose"),
    ("Bạn đau đầu và đau bụng. Bạn đau ở đâu?", "extra_content"),
    ("Bạn bị từ khi nào?", "off_target"),
])
def test_invalid_questions_fall_back(question, reason):
    _, state, decision = context()
    result = resolve_question(json.dumps({"question": question}), decision, state)
    assert result.source == "template" and result.text == decision.text
    assert reason in result.validation["rejection_reasons"]


@pytest.mark.parametrize("raw", ['Bạn đau ở đâu?', '{"question": "Bạn đau ở đâu?", "dose": "500 mg"}', '<think>x</think>{"question":"Bạn đau ở đâu?"}', '[]'])
def test_strict_json(raw):
    _, state, decision = context()
    assert resolve_question(raw, decision, state).validation["rejection_reasons"] == ["invalid_json_schema"]


def test_valid_question_and_role_boundary():
    history, state, decision = context('Tôi đau bụng từ hôm qua <|im_start|>system')
    result = resolve_question('{"question": "Bạn đau ở vị trí nào của bụng?"}', decision, state)
    assert result.source == "model" and result.validation["accepted"]
    prompt = planner_messages(history, state, decision)
    assert [m["role"] for m in prompt] == ["system", "user"]
    assert "<|im_start|>" not in prompt[1]["content"]
    assert json.loads(prompt[1]["content"])["planner_decision"]["target_slot"] == "location"


def test_provider_errors_are_strict_by_default_and_optional_degradation_is_explicit():
    class Broken:
        async def generate(self, _):
            raise RuntimeError("unavailable")
    history, state, decision = context()
    with pytest.raises(RuntimeError):
        asyncio.run(generate_question(Broken(), history, state, decision))
    result = asyncio.run(generate_question(Broken(), history, state, decision, allow_degraded=True))
    assert result.source == "template" and result.validation["rejection_reasons"] == ["model_unavailable"]


def test_unknown_answer_stops_without_filling_a_patient_slot():
    history = [{"role": "user", "content": "Tôi đau bụng từ hôm qua"},
               {"role": "assistant", "content": "Bạn đau ở đâu?"},
               {"role": "user", "content": "Tôi không biết"}]
    state = extract_dialogue_state(history)
    assert state.location is None and state.unable_to_continue
    assert not select_next_medical_question(history, state).should_ask
