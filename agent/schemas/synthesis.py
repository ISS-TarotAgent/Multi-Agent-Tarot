from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SynthesisInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_question: str
    card_interpretations: list[str]
    locale: str


class SynthesisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    action_advice: str
    reflection_question: str
