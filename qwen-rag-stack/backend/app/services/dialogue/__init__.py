"""Deterministic medical-dialogue components: state tracking, question
selection, hypothesis generation and domain guardrails.

Every component here is rule-based and model-independent so it can be unit
tested, evaluated, and kept working when the language model is unavailable.
None of it is a certified diagnostic tool.
"""

from .guardrails import ScopeDecision, check_scope
from .hypotheses import Assessment, CandidateCondition, generate_hypotheses
from .planner import NextQuestion, select_next_medical_question
from .state import DialogueState, extract_dialogue_state

__all__ = [
    "Assessment",
    "CandidateCondition",
    "DialogueState",
    "NextQuestion",
    "ScopeDecision",
    "check_scope",
    "extract_dialogue_state",
    "generate_hypotheses",
    "select_next_medical_question",
]
