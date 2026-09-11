from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .services.rag.config import Citation


class TriageRequest(BaseModel):
    symptom: str = Field(min_length=2, max_length=2_000)
    duration: str | None = Field(default=None, max_length=200)

    @field_validator("symptom", "duration", mode="before")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        return " ".join(value.split())


class Possibility(BaseModel):
    name: str
    note: str


class TriageResponse(BaseModel):
    urgency: Literal["emergency", "routine"]
    reply: str
    disclaimer: str
    matched_red_flags: list[str] = Field(default_factory=list)
    possibilities: list[Possibility] = Field(default_factory=list)
    next_step: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8_000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content cannot be blank")
        return normalized


class ConsultationRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=64)

    @field_validator("messages")
    @classmethod
    def validate_conversation(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        if messages[-1].role != "user":
            raise ValueError("conversation must end with a user message")
        if sum(len(message.content) for message in messages) > 32_000:
            raise ValueError("conversation exceeds the 32000 character limit")
        return messages


class ConsultationResponse(BaseModel):
    reply: str
    provider: str
    action: Literal["ASK_MORE", "FINALIZE", "GROUNDED_ANSWER", "EMERGENCY"] = "FINALIZE"
    grounding_status: Literal["grounded", "degraded", "not_used"] = "not_used"
    citations: list[Citation] = Field(default_factory=list)
    patient_state: dict[str, object] = Field(default_factory=dict)
    disclaimer: str = ""


class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2_000)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query", mode="before")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        return " ".join(value.split())


class RAGSearchResult(BaseModel):
    chunk_id: str
    snippet: str
    score: float
    source_id: str | None = None
    title: str | None = None
    organization: str | None = None
    source_url: str | None = None
    publication_date: str | None = None
    section: str | None = None
    page: int | None = None


class RAGSearchResponse(BaseModel):
    query: str
    results: list[RAGSearchResult]


class ReadyResponse(BaseModel):
    api: bool
    model: bool
    rag: bool
