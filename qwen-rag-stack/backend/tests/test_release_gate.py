"""Tests for release decisions. Does not require GPU, API keys or patient data."""
import copy
import json
from pathlib import Path

import pytest

from evals.release_gate import audit_release

EVIDENCE = Path(__file__).resolve().parents[2] / "docs" / "PLANNER_E5_RESULTS_20261031.json"


def load():
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


def test_pilot_adapter_is_not_promoted():
    report = audit_release(load())
    assert report["research_demo_recommendation"] == "NO_GO"
    assert report["medical_deployment_allowed"] is False
    assert report["clinical_approval"] == "NOT_EVALUATED"
    assert report["model_acceptance"]["candidate"] < report["model_acceptance"]["baseline"]
    assert any("acceptance regressed" in msg for msg in report["issues"])


def test_missing_evidence_fails_closed():
    with pytest.raises(ValueError, match="No paired"):
        audit_release({})


def test_unknown_experiment_fails_closed():
    with pytest.raises(ValueError, match="exactly one"):
        audit_release(load(), candidate="UNKNOWN")


def test_require_sufficient_sample_count():
    report = audit_release(load(), min_cases=1000)
    assert report["research_demo_recommendation"] == "NO_GO"
    assert any("Insufficient" in text for text in report["issues"])


def test_behavior_failure_prevents_promotion_even_when_acceptance_improves():
    evidence = load()
    comparison = evidence["guided_comparison"]
    base = next(v for k, v in comparison["metrics"].items() if k.endswith("_E5A"))
    candidate = next(v for k, v in comparison["metrics"].items() if k.endswith("_E5C"))
    candidate["question_generation"]["model_accepted"]["mean"] = base["question_generation"]["model_accepted"]["mean"]
    candidate["question_generation"]["template_fallback"]["mean"] = base["question_generation"]["template_fallback"]["mean"]
    candidate["behavior"]["emergency"]["passed"] = candidate["behavior"]["emergency"]["n"] - 1
    result = audit_release(evidence)
    assert result["research_demo_recommendation"] == "NO_GO"
    assert any("emergency failed" in msg for msg in result["issues"])
