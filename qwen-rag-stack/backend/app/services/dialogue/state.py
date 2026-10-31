"""Dialogue State Tracking for multi-turn Vietnamese symptom consultations.

The state is rebuilt from the full conversation on every request, so it never
drifts from what the user actually wrote. Only user turns provide values;
assistant turns are read solely to interpret short answers ("Không ạ") to the
question they asked. Fields that the user has not reported stay ``None`` or
empty — nothing is inferred or auto-filled. AI hypotheses live in a separate
assessment object (see ``hypotheses.py``).
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.triage import _affirmed, find_red_flags, is_information_question

from .features import duration_bucket, extract_text_features, max_temperature
from .lexicon import (
    AFFIRMATIVE_ANSWER,
    AGE_PATTERN,
    ALLERGY_NONE,
    ALLERGY_TERMS,
    CHARACTER_PATTERNS,
    DURATION_PATTERNS,
    HISTORY_NONE,
    HISTORY_TERMS,
    LOCATION_PATTERNS,
    MEDICATION_NONE,
    MEDICATION_TERMS,
    NEGATIVE_ANSWER,
    PREGNANCY_PATTERN,
    PROGRESSION_PATTERNS,
    SEVERITY_PATTERNS,
    SLOT_LABELS,
    SYMPTOM_BY_KEY,
    SYMPTOMS,
    TRIGGER_PATTERNS,
    find_term,
    fold_aligned,
    question_topics,
)
from .profiles import PROFILE_BY_NAME, profile_for, required_slots

ConversationStatus = Literal[
    "COLLECTING", "READY_FOR_ASSESSMENT", "EMERGENCY", "OUT_OF_SCOPE", "INFORMATION_REQUEST"
]
MAX_PLANNER_QUESTIONS = 6
SCALAR_SLOTS = ("location", "severity", "character", "progression", "triggers")
LIST_SLOTS = ("relevant_history", "medications", "allergies")
NONE_VALUE = "không có (người dùng xác nhận)"
UNSPECIFIED_RED_FLAG = "người dùng xác nhận có dấu hiệu nguy hiểm được hỏi"


class SlotValue(BaseModel):
    value: str
    source: Literal["user_reported", "user_answer"] = "user_reported"
    turn: int


class SymptomMention(BaseModel):
    key: str
    label: str
    present: bool
    turn: int
    evidence: str


class DialogueState(BaseModel):
    provenance: Literal["user_reported_only"] = "user_reported_only"
    subject: Literal["self", "other"] = "self"
    chief_complaint: str | None = None
    chief_complaint_key: str | None = None
    chief_complaint_text: str | None = None
    profile: str = "general"
    symptoms: list[SymptomMention] = Field(default_factory=list)
    negated_symptoms: list[SymptomMention] = Field(default_factory=list)
    onset: SlotValue | None = None
    duration: SlotValue | None = None
    location: SlotValue | None = None
    severity: SlotValue | None = None
    character: SlotValue | None = None
    progression: SlotValue | None = None
    triggers: SlotValue | None = None
    associated_symptoms: list[str] = Field(default_factory=list)
    relevant_history: list[SlotValue] = Field(default_factory=list)
    medications: list[SlotValue] = Field(default_factory=list)
    allergies: list[SlotValue] = Field(default_factory=list)
    age: SlotValue | None = None
    pregnancy: bool | None = None
    max_temperature_c: float | None = None
    answered_slots: list[str] = Field(default_factory=list)
    asked_slots: dict[str, int] = Field(default_factory=dict)
    questions_asked: int = 0
    features: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    optional_missing: list[str] = Field(default_factory=list)
    emergency_flags: list[str] = Field(default_factory=list)
    urgent_flags: list[str] = Field(default_factory=list)
    user_requests_assessment: bool = False
    unable_to_continue: bool = False
    conversation_status: ConversationStatus = "COLLECTING"

    @property
    def missing_information_labels(self) -> list[str]:
        return [SLOT_LABELS.get(slot, slot) for slot in self.missing_information]

    @property
    def present_symptom_keys(self) -> list[str]:
        return [item.key for item in self.symptoms]

    def slot_filled(self, slot: str) -> bool:
        if slot == "timing":
            return self.onset is not None or self.duration is not None
        if slot in SCALAR_SLOTS:
            return getattr(self, slot) is not None or slot in self.answered_slots
        if slot in LIST_SLOTS:
            return bool(getattr(self, slot)) or slot in self.answered_slots
        if slot == "associated_symptoms":
            others = [item for item in self.symptoms + self.negated_symptoms if item.key != self.chief_complaint_key]
            return bool(others) or slot in self.answered_slots
        if slot == "red_flag_screen":
            return slot in self.answered_slots or self._red_flags_mentioned()
        if slot == "age":
            return self.age is not None
        if slot == "chief_complaint":
            return self.chief_complaint is not None
        return False

    def _red_flags_mentioned(self) -> bool:
        profile = PROFILE_BY_NAME[self.profile]
        flags = set(profile.emergency_flags + profile.urgent_flags)
        return any(item.key in flags for item in self.symptoms + self.negated_symptoms)

    def concise_summary(self) -> str:
        fields = [
            ("Triệu chứng chính", self.chief_complaint),
            ("Khởi phát", self.onset.value if self.onset else None),
            ("Thời gian", self.duration.value if self.duration else None),
            ("Vị trí", self.location.value if self.location else None),
            ("Mức độ", self.severity.value if self.severity else None),
            ("Tính chất", self.character.value if self.character else None),
            ("Triệu chứng kèm", ", ".join(self.associated_symptoms) or None),
            ("Không có", ", ".join(item.label for item in self.negated_symptoms) or None),
            ("Tiền sử", ", ".join(item.value for item in self.relevant_history) or None),
            ("Thuốc", ", ".join(item.value for item in self.medications) or None),
            ("Tuổi", self.age.value if self.age else None),
        ]
        return "; ".join(f"{label}: {value}" for label, value in fields if value)


def _span(text: str, match: re.Match[str]) -> str:
    return text[match.start() : match.end()].strip(" ,.;")


def _affirmed_matches(text: str, patterns: tuple[str, ...]) -> list[re.Match[str]]:
    folded = fold_aligned(text)
    results = []
    for pattern in patterns:
        for match in re.finditer(rf"(?<!\w)(?:{pattern})(?!\w)", folded):
            if _affirmed(match.group(0), folded[: match.start()], folded[match.end() :]):
                results.append(match)
    return sorted(results, key=lambda item: item.start())


def _any_match(text: str, patterns: tuple[str, ...]) -> bool:
    folded = fold_aligned(text)
    return any(re.search(rf"(?<!\w)(?:{pattern})(?!\w)", folded) for pattern in patterns)


def _subject(first_user: str) -> Literal["self", "other"]:
    folded = fold_aligned(first_user)
    if re.search(
        r"\b(?:me|bo|ba|ong|vo|chong|con|chau|em|anh|chi|ban) (?:toi|minh|cua toi|nha toi|em)\b"
        r"|^(?:be|chau|con|em be) (?:nha )?\w+",
        folded,
    ):
        return "other"
    return "self"


def _timing(text: str, turn: int) -> tuple[SlotValue | None, SlotValue | None]:
    masked = re.sub(AGE_PATTERN, lambda m: " " * len(m.group(0)), fold_aligned(text))
    onset = duration = None
    for pattern in DURATION_PATTERNS:
        for match in re.finditer(rf"(?<!\w)(?:{pattern})(?!\w)", masked):
            value = SlotValue(value=_span(text, match), turn=turn)
            if re.search(r"\d|mot |hai |ba |bon |vai |may |lau", match.group(0)):
                duration = duration or value
            else:
                onset = onset or value
    return onset, duration


def _first_value(text: str, patterns: tuple[str, ...], turn: int) -> SlotValue | None:
    matches = _affirmed_matches(text, patterns)
    return SlotValue(value=_span(text, matches[0]), turn=turn) if matches else None


def _statements(text: str) -> str:
    """Drop the patient's own questions ("Có phải tôi bị bệnh tim không?").

    Sentences are blanked rather than removed so spans stay aligned.
    """
    folded = fold_aligned(text)
    chars = list(text)
    for match in re.finditer(r"[^.!?\n]*(?:\?|co phai|co the la|lieu co)[^.!?\n]*[.!?]?", folded):
        chars[match.start() : match.end()] = " " * (match.end() - match.start())
    return "".join(chars)


def _list_values(text: str, terms: tuple[str, ...], none: tuple[str, ...], turn: int) -> list[SlotValue]:
    if _any_match(text, none):
        return [SlotValue(value=NONE_VALUE, turn=turn)]
    reported = _statements(text)
    return [SlotValue(value=_span(text, match), turn=turn) for match in _affirmed_matches(reported, terms)]


def _requests_assessment(text: str) -> bool:
    return bool(re.search(
        r"(?:toi|em|minh|con|chau|bac) (?:bi|mac) (?:benh )?gi|bi (?:benh )?gi|co sao khong|co nguy hiem khong"
        r"|nen lam gi|bi lam sao|co phai (?:la|bi|toi bi|em bi)|chan doan|ket luan",
        fold_aligned(text),
    ))


def extract_dialogue_state(
    messages: list[dict[str, str]], *, max_questions: int = MAX_PLANNER_QUESTIONS
) -> DialogueState:
    """Rebuild the consultation state from the full message history."""
    state = DialogueState()
    user_turns = [(index, item["content"]) for index, item in enumerate(messages) if item.get("role") == "user"]
    if not user_turns:
        return state
    first_user_index = user_turns[0][0]
    state.subject = _subject(user_turns[0][1])

    mentions: dict[str, SymptomMention] = {}
    features: set[str] = set()
    order: list[str] = []
    for turn, text in user_turns:
        if is_information_question(text):
            continue
        for term in SYMPTOMS:
            for match in find_term(text, term):
                current = mentions.get(term.key)
                if current is None:
                    order.append(term.key)
                    mentions[term.key] = SymptomMention(
                        key=term.key, label=term.label, present=match.affirmed, turn=turn, evidence=match.text
                    )
                elif match.affirmed and not current.present:
                    mentions[term.key] = current.model_copy(update={"present": True, "evidence": match.text, "turn": turn})
        if state.chief_complaint is None:
            affirmed = sorted(
                (match for term in SYMPTOMS for match in find_term(text, term, require_affirmed=True)),
                key=lambda item: item.start,
            )
            if affirmed:
                key = next(term.key for term in SYMPTOMS if term.label == affirmed[0].label)
                state.chief_complaint, state.chief_complaint_key = affirmed[0].label, key
                state.chief_complaint_text = text
        onset, duration = _timing(text, turn)
        state.onset = state.onset or onset
        state.duration = state.duration or duration
        for slot, patterns in (
            ("location", LOCATION_PATTERNS), ("severity", SEVERITY_PATTERNS), ("character", CHARACTER_PATTERNS),
            ("progression", PROGRESSION_PATTERNS), ("triggers", TRIGGER_PATTERNS),
        ):
            value = _first_value(text, patterns, turn)
            if value is not None:
                setattr(state, slot, value)
        state.relevant_history += _list_values(text, HISTORY_TERMS, HISTORY_NONE, turn)
        state.medications += _list_values(text, MEDICATION_TERMS, MEDICATION_NONE, turn)
        state.allergies += _list_values(text, ALLERGY_TERMS, ALLERGY_NONE, turn)
        age = re.search(AGE_PATTERN, fold_aligned(text))
        if age:
            state.age = SlotValue(value=_span(text, age), turn=turn)
        if _affirmed_matches(text, (PREGNANCY_PATTERN,)):
            state.pregnancy = True
        temperature = max_temperature(text)
        if temperature is not None:
            state.max_temperature_c = max(temperature, state.max_temperature_c or 0)
        if re.search(r"khong (?:co |con |thay )?(?:trieu chung|bieu hien|dau hieu) (?:gi|nao) khac", fold_aligned(text)):
            state.answered_slots.append("associated_symptoms")
        features |= extract_text_features(text)
        state.emergency_flags += find_red_flags(text)

    ordered = [mentions[key] for key in order]
    state.symptoms = [item for item in ordered if item.present]
    state.negated_symptoms = [item for item in ordered if not item.present]
    if state.chief_complaint is None and state.symptoms:
        first = state.symptoms[0]
        state.chief_complaint, state.chief_complaint_key = first.label, first.key
    state.associated_symptoms = [item.label for item in state.symptoms if item.key != state.chief_complaint_key]
    profile = profile_for([item.key for item in state.symptoms])
    state.profile = profile.name

    # Interpret answers to the immediately preceding assistant question.
    asked: dict[str, int] = {}
    for index, item in enumerate(messages):
        if item.get("role") != "assistant" or index < first_user_index:
            continue
        topics = question_topics(item["content"])
        if "?" in item["content"]:
            state.questions_asked += 1
        for slot in topics.slots:
            asked[slot] = asked.get(slot, 0) + 1
        following = messages[index + 1] if index + 1 < len(messages) else None
        if not following or following.get("role") != "user" or not topics.slots:
            continue
        _apply_answer(state, topics.slots, following["content"], index + 1)
    state.asked_slots = asked

    for item in state.symptoms:
        features.add(f"sym:{item.key}")
    for item in state.negated_symptoms:
        features.add(f"neg:{item.key}")
    if state.max_temperature_c is not None and state.max_temperature_c >= 39:
        features.add("sym:sot_cao")
    bucket = duration_bucket(state.duration.value if state.duration else state.onset.value if state.onset else None)
    if bucket:
        features.add(bucket)
    state.features = sorted(features)

    present = {item.key for item in state.symptoms}
    for key in profile.emergency_flags:
        if key in present and SYMPTOM_BY_KEY[key].label not in state.emergency_flags:
            state.emergency_flags.append(SYMPTOM_BY_KEY[key].label)
    state.urgent_flags = [SYMPTOM_BY_KEY[key].label for key in profile.urgent_flags if key in present]
    state.emergency_flags = list(dict.fromkeys(state.emergency_flags))
    state.user_requests_assessment = _requests_assessment(user_turns[-1][1])
    state.unable_to_continue = bool(re.search(
        r"\b(?:khong biet|khong ro|khong nho|khong the (?:tra loi|cung cap)|khong muon (?:tra loi|tiep tuc)|dung hoi|dung lai)\b",
        fold_aligned(user_turns[-1][1]),
    ))

    if state.chief_complaint is None:
        state.missing_information = ["chief_complaint"]
    else:
        core = required_slots(profile, present)
        state.missing_information = [slot for slot in core if not state.slot_filled(slot)]
        state.optional_missing = [slot for slot in profile.optional_slots if not state.slot_filled(slot)]

    if state.emergency_flags:
        state.conversation_status = "EMERGENCY"
    elif state.unable_to_continue or state.questions_asked >= max_questions:
        state.conversation_status = "READY_FOR_ASSESSMENT"
    elif state.chief_complaint is None:
        state.conversation_status = "COLLECTING"
    elif not state.missing_information or state.questions_asked >= max_questions:
        state.conversation_status = "READY_FOR_ASSESSMENT"
    elif state.user_requests_assessment and state.slot_filled("timing"):
        core = required_slots(profile, present)
        if len(core) - len(state.missing_information) >= math.ceil(len(core) / 2):
            state.conversation_status = "READY_FOR_ASSESSMENT"
    return state


def _apply_answer(state: DialogueState, slots: set[str], answer: str, turn: int) -> None:
    folded = fold_aligned(answer).strip()
    if re.search(r"\b(?:khong biet|khong ro|khong nho|khong the tra loi)\b", folded):
        return
    words = len(folded.split())
    negative = bool(NEGATIVE_ANSWER.match(folded)) and words <= 15
    affirmative = bool(AFFIRMATIVE_ANSWER.match(folded))
    if "red_flag_screen" in slots:
        if affirmative and not negative and not find_red_flags(answer):
            # "Có ạ" to a red-flag question without naming which sign: escalate.
            state.emergency_flags.append(UNSPECIFIED_RED_FLAG)
        state.answered_slots.append("red_flag_screen")
    for slot in slots & {"associated_symptoms", *LIST_SLOTS}:
        if negative:
            state.answered_slots.append(slot)
            if slot in LIST_SLOTS and not getattr(state, slot):
                getattr(state, slot).append(SlotValue(value=NONE_VALUE, source="user_answer", turn=turn))
        elif slot in LIST_SLOTS and not getattr(state, slot) and words <= 25:
            getattr(state, slot).append(SlotValue(value=answer.strip()[:160], source="user_answer", turn=turn))
    scalar = [slot for slot in slots if slot in SCALAR_SLOTS or slot in {"timing", "age"}]
    if len(scalar) == 1 and not negative and words <= 15:
        slot = scalar[0]
        value = SlotValue(value=answer.strip()[:160], source="user_answer", turn=turn)
        if slot == "timing" and state.onset is None and state.duration is None:
            state.onset = value
        elif slot == "age" and state.age is None:
            state.age = value
        elif slot in SCALAR_SLOTS and getattr(state, slot) is None:
            setattr(state, slot, value)
    elif negative:
        for slot in scalar:
            if slot in SCALAR_SLOTS:
                state.answered_slots.append(slot)
    state.answered_slots = list(dict.fromkeys(state.answered_slots))
