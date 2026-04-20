from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from agent.schemas.clarifier import ClarifierOutput
from agent.schemas.draw import DrawCard, DrawOutput
from agent.schemas.safety import SafetyReviewOutput
from agent.schemas.synthesis import SynthesisOutput
from app.domain.enums import SpreadType, WorkflowStatus
from app.schemas.workflow.common import WorkflowSchema
from app.schemas.workflow.trace_event import TraceEventPayload


class ClarificationTurnState(WorkflowSchema):
    turn_index: int
    question_text: str
    answer_text: str | None = None


class TarotWorkflowState(WorkflowSchema):
    session_id: str
    reading_id: str
    status: WorkflowStatus
    locale: str
    spread_type: SpreadType
    raw_question: str
    client_request_id: str | None = None
    metadata: dict[str, Any] | None = None
    effective_question: str | None = None
    input_safety_status: str | None = None
    input_required_action: str | None = None
    input_risk_level: str | None = None
    input_detected_risks: list[str] = Field(default_factory=list)
    input_removed_segments: list[str] = Field(default_factory=list)
    input_preserved_intent: str | None = None
    input_sanitized: bool = False
    normalized_question: str | None = None
    clarification_output: ClarifierOutput | None = None
    clarification_turns: list[ClarificationTurnState] = Field(default_factory=list)
    cards: list[DrawCard] = Field(default_factory=list)
    draw_output: DrawOutput | None = None
    synthesis_output: SynthesisOutput | None = None
    safety_output: SafetyReviewOutput | None = None
    trace_events: list[TraceEventPayload] = Field(default_factory=list)
    created_at: datetime
    completed_at: datetime | None = None
