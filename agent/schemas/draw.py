from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from agent.schemas.common import AgentSchema
from app.domain.enums import CardOrientation, CardPosition, SpreadType


class DrawInput(AgentSchema):
    normalized_question: str
    spread_type: SpreadType = SpreadType.THREE_CARD_REFLECTION
    locale: str = "zh-CN"

    @field_validator("normalized_question")
    @classmethod
    def validate_normalized_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("normalized_question must not be empty.")
        return normalized


class DrawCard(AgentSchema):
    position: CardPosition
    card_code: str
    card_name: str
    orientation: CardOrientation
    interpretation: str


class DrawOutput(AgentSchema):
    cards: list[DrawCard] = Field(min_length=3, max_length=3)
    draw_summary: str

    @model_validator(mode="after")
    def validate_positions(self) -> "DrawOutput":
        positions = {card.position for card in self.cards}
        if len(positions) != 3:
            raise ValueError("draw output must contain exactly one card for each position.")
        return self
