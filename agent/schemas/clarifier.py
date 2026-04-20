from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ClarifierInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_question: str
    locale: str


class ClarifierOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_question: str
    clarification_required: bool
    clarifier_question: str | None = None
