from evals.closed_loop_dialogue import simulate, starter_cases, evaluate
from evals.benchmark_dialogue import PlannerGenerator, GuidedGenerator


def test_simulator_answers_only_from_profile_and_stops_when_unknown():
    report = simulate({"id": "unknown", "opening": "Tôi đau bụng", "answers": {}}, PlannerGenerator())
    assert report["n_questions"] == 1 and report["stopped"]
    assert not report["collected_core_information"]
    assert not report["assessment_eligible"] or report["candidate_count"] == 0


def test_emergency_stops_without_calling_model():
    class Never:
        def generate(self, _):
            raise AssertionError("Must not call model for emergency")
    result = simulate({"id": "em", "opening": "Tôi khó thở", "emergency": True}, Never())
    assert result["emergency_detected"] and result["n_questions"] == 0


def test_closed_loop_profiles_and_report_have_no_invented_clinical_labels():
    assert len(starter_cases()) >= 100
    report = evaluate(starter_cases()[:3], PlannerGenerator())
    assert report["expert_hypothesis_quality"] is None
    assert report["repeated_questions"] == 0


def test_guided_generator_keeps_raw_acceptance_distinct_from_template_success():
    class BadModel:
        name = "test-only"
        def generate(self, batch):
            return ["Nêu bệnh và hỏi quá nhiều? Bao lâu?" for _ in batch]
    generator = GuidedGenerator(BadModel())
    reply = generator.generate([[{"role": "user", "content": "Tôi đau bụng từ hôm qua"}]])[0]
    assert "vị trí" in reply
    record = next(iter(generator.records.values()))
    assert record["template_fallback"] and not record["model_accepted"]
