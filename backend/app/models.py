from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TriageRequest(BaseModel):
    symptom: str = Field(min_length=2, max_length=2_000)
    duration: str | None = Field(default=None, max_length=200)

    @field_validator("symptom", "duration")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
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
