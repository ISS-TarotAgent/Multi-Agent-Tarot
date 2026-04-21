from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domain.enums import CardOrientation, CardPosition, SpreadType


class DrawInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    locale: str
    spread_type: SpreadType


class DrawCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position: CardPosition
    card_code: str
    card_name: str
    orientation: CardOrientation
    interpretation: str
    reflection_question: str | None = None
    caution_note: str | None = None
    keywords: list[str] = []
    seed: str | None = None
    meaning: str | None = None


class DrawOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cards: list[DrawCard] = Field(default_factory=list)
