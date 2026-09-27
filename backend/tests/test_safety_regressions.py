import asyncio
import json
from pathlib import Path

import pytest

from app.triage import find_red_flags
from app.services.consultation import ConsultationOrchestrator
from app.services.rag.query_builder import patient_state_from_messages

CASES = json.loads((Path(__file__).parents[1] / "evals/safety_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_safety_regressions(case):
    assert bool(find_red_flags(case["text"])) == case["emergency"]
    assert bool(find_red_flags(case["text"].upper())) == case["emergency"]


def test_emergency_works_even_when_both_model_and_rag_are_unavailable():
    response = asyncio.run(ConsultationOrchestrator(None, None, "unavailable").respond([
        {"role": "user", "content": "Tôi không sốt"},
        {"role": "assistant", "content": "Bạn có triệu chứng khác không?"},
        {"role": "user", "content": "Khó thở"},
    ]))
    assert response.action == "EMERGENCY"
    assert response.provider == "safety-router"
    assert not response.citations


def test_age_does_not_count_as_symptom_duration():
    state = patient_state_from_messages([{"role": "user", "content": "Bé 2 tháng tuổi bị ho"}])
    assert state.age == "2 tháng tuổi"
    assert state.duration is None
    assert not state.sufficient_for_grounding


def test_unaccented_duration_and_negated_associated_symptoms():
    state = patient_state_from_messages([{"role": "user", "content": "Toi dau dau 2 ngay, khong sot, khong kho tho"}])
    assert state.duration == "2 ngay"
    assert state.associated_symptoms == []


def test_nausea_is_not_vomiting():
    state = patient_state_from_messages([{"role": "user", "content": "Tôi buồn nôn"}])
    assert state.associated_symptoms == ["buồn nôn"]
    state = patient_state_from_messages([{"role": "user", "content": "Tôi buồn nôn và đã nôn"}])
    assert state.associated_symptoms == ["buồn nôn", "nôn"]
