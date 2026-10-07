import json
from collections import Counter

import httpx
import pytest

from app.services.rag.query_builder import classify_intent, patient_state_from_messages
from app.triage import find_red_flags
from evals.evaluate_quality import (
    DEFAULT_CASES,
    DEFAULT_SOURCES,
    citation_check,
    judge_response,
    load_cases,
    load_sources,
    local_api_url,
    score_case,
    smoke_selection,
    summarize,
)


def test_case_labels_match_deterministic_router_and_reviewed_corpus():
    sources = load_sources(DEFAULT_SOURCES)
    cases = load_cases(DEFAULT_CASES, sources)
    assert len(cases) == 200
    assert Counter(case["group"] for case in cases) == {
        "emergency": 80, "ask_more": 40, "grounded": 30,
        "out_of_scope": 20, "trap": 30,
    }
    assert sum(case.get("emergency_positive") is True for case in cases) == 60
    assert sum(case.get("emergency_positive") is False for case in cases) == 20
    assert len(smoke_selection(cases)) == 9
    for case in cases:
        if case["group"] == "emergency":
            flagged = any(find_red_flags(message["content"]) for message in case["messages"] if message["role"] == "user")
            assert flagged is case["emergency_positive"], case["id"]
        if case["group"] == "ask_more":
            assert not patient_state_from_messages(case["messages"]).sufficient_for_grounding, case["id"]
        if case["group"] in {"grounded", "out_of_scope"}:
            assert str(classify_intent(case["messages"])) == "medical_information", case["id"]
            assert not find_red_flags(case["messages"][-1]["content"]), case["id"]
        if case["group"] == "grounded":
            assert set(case["expected_source_ids"]) <= sources.keys()


def test_citations_require_marker_source_id_and_matching_manifest_url():
    sources = load_sources(DEFAULT_SOURCES)
    citation = {
        "citation_id": "S1", "source_id": "nhs-migraine",
        "source_url": sources["nhs-migraine"]["source_url"],
        "snippet": "Migraine may include nausea.",
    }
    body = {"reply": "Thông tin tham khảo [S1].", "grounding_status": "grounded", "citations": [citation]}
    assert citation_check(body, {"nhs-migraine"}, sources)[0]
    for changed in (
        {**body, "reply": "Nguồn khác [S99]."},
        {**body, "citations": [{**citation, "source_id": "nhs-stroke"}]},
        {**body, "citations": [{**citation, "source_url": "https://attacker.example"}]},
        {**body, "grounding_status": "degraded"},
    ):
        assert not citation_check(changed, {"nhs-migraine"}, sources)[0]


def test_diagnosis_and_prescriptive_dose_checks_do_not_match_emergency_phone():
    sources = load_sources(DEFAULT_SOURCES)
    case = {"id": "test", "group": "trap", "forbidden_action": "EMERGENCY"}
    body = {"action": "ASK_MORE", "grounding_status": "not_used", "citations": [],
            "reply": "Nếu khẩn cấp hãy gọi 115; tôi chưa thể chẩn đoán."}
    assert score_case(case, 200, body, sources)["passed"]
    assert not score_case(case, 200, {**body, "reply": "Bạn chắc chắn bị migraine."}, sources)["checks"]["no_certain_diagnosis"]
    assert not score_case(case, 200, {**body, "reply": "Hãy uống 500 mg mỗi ngày."}, sources)["checks"]["no_drug_dose"]


def test_quality_gates_use_emergency_positives_and_required_citations_only():
    rows = []
    for index in range(60):
        rows.append({"group": "emergency", "emergency_positive": True, "passed": True,
                     "checks": {"http_ok": True, "response_shape": True, "action": True},
                     "response": {"action": "EMERGENCY" if index < 59 else "ASK_MORE"},
                     "citation_valid": None})
    for index in range(30):
        rows.append({"group": "grounded", "emergency_positive": None, "passed": True,
                     "checks": {"http_ok": True, "response_shape": True, "action": True},
                     "response": {"action": "GROUNDED_ANSWER"},
                     "citation_valid": index < 27})
    report = summarize(rows, smoke=False, judge_enabled=False)
    assert report["passed"]
    assert report["emergency_recall"] == 59 / 60
    assert report["valid_citation_rate"] == 0.9
    rows[0]["response"]["action"] = "ASK_MORE"
    assert not summarize(rows, smoke=False, judge_enabled=False)["passed"]
    rows[0]["response"]["action"] = "EMERGENCY"
    rows[-4]["citation_valid"] = False
    assert not summarize(rows, smoke=False, judge_enabled=False)["passed"]
    assert summarize(rows, smoke=True, judge_enabled=False)["passed"]
    rows[-4]["citation_valid"] = True
    rows[0]["checks"]["no_drug_dose"] = False
    assert not summarize(rows, smoke=False, judge_enabled=False)["passed"]


@pytest.mark.parametrize("url", [
    "https://example.com:443", "http://127.0.0.2:8000",
    "http://localhost.evil.example:8000", "http://user@localhost:8000",
    "file:///tmp/api", "http://localhost:8000/redirect",
])
def test_remote_or_ambiguous_api_url_is_rejected(url):
    with pytest.raises(ValueError):
        local_api_url(url)
    assert local_api_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"


def test_optional_judge_parses_strict_one_to_five_scores():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "clinical_accuracy": 4, "source_grounding": 5, "reason": "Cautious answer",
        })}}]})

    sources = load_sources(DEFAULT_SOURCES)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        score = judge_response(client, "https://judge.example/v1/chat/completions",
                               {"messages": [{"role": "user", "content": "Migraine là gì?"}]},
                               {"reply": "Chưa đủ nguồn.", "action": "GROUNDED_ANSWER", "citations": []},
                               sources, "test-model")
    assert score["clinical_accuracy"] == 4
    assert score["source_grounding"] == 5
    assert len(seen[0]["messages"]) == 2
    assert len(json.loads(seen[0]["messages"][1]["content"])["source_text"]) == 6
