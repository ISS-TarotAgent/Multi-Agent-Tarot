"""Typed data contracts shared across agents.

Each Agent node should import the relevant schema objects instead of defining
ad-hoc dictionaries. Concrete fields intentionally left as TODOs for the feature
owners who will supply final business logic.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Clarifier Agent -- Phase 1 (clarify_init)
# ---------------------------------------------------------------------------

IntentTag = Literal["career", "relationship", "study", "emotion", "growth"]


class ClarificationPrompt(BaseModel):
    """A single clarifying question presented to the user."""

    id: str
    question: str
    helper_text: str
    placeholder: str


class ClarificationRequest(BaseModel):
    """Incoming payload for Phase 1 of the Clarifier Agent."""

    session_id: str
    raw_question: str


class ClarificationResult(BaseModel):
    """Structured output from Phase 1 of the Clarifier Agent.

    Maps to the frontend ``SessionDraft`` type (camelCase conversion is handled
    at the API layer via ``model_config`` / ``alias_generator``).
    """

    session_id: str
    original_question: str
    normalized_question: str
    intent_tag: IntentTag
    clarification_prompts: list[ClarificationPrompt]


# ---------------------------------------------------------------------------
# Clarifier Agent -- Phase 2 (clarify_finalize)
# ---------------------------------------------------------------------------


class ClarificationFinalizeRequest(BaseModel):
    """Incoming payload for Phase 2 of the Clarifier Agent."""

    session_id: str
    original_question: str
    intent_tag: IntentTag
    clarification_answers: dict[str, str]


class ClarificationFinalizeResult(BaseModel):
    """Structured output from Phase 2 of the Clarifier Agent.

    ``reframed_question`` is the single enriched question passed downstream to
    the DrawAndInterpret node.  The remaining fields provide semantic context
    that the Synthesis and Safety agents may consume.
    """

    reframed_question: str
    topic: str
    time_horizon: str
    intent: str
    constraints: list[str]


class CardInterpretation(BaseModel):
    """Represents a single Tarot card draw and explanation.

    TODO:
        - add card id/name/upright-or-reversed flag
        - add key themes and tie-back narrative
        - add any subjective risk notes
    """

    pass


class SynthesisInput(BaseModel):
    """Bundle of clarified intent plus all per-card interpretations.

    TODO:
        - reference ClarificationResult
        - include list[CardInterpretation]
        - add contextual knobs (tone, depth, cultural guardrails)
    """

    pass


class SynthesisOutput(BaseModel):
    """Composite insights and action plan suggested to the user.

    TODO:
        - add structured reflection sections (insight, actions, questions)
        - add trace references back to card ids
        - capture uncertainty markers for Safety review
    """

    pass


class SafetyReport(BaseModel):
    """Findings from the Safety Guard Agent.

    TODO:
        - flag high-risk statements
        - attach mitigation instructions or rewritten text
        - store reviewer notes for observability/traceability
    """

    pass


class OrchestratorState(BaseModel):
    """State container passed between LangGraph nodes.

    Fields are populated incrementally as the workflow progresses through each
    node.  Optional fields are ``None`` until the responsible node runs.
    """

    # ---- session identity ----
    session_id: str = ""

    # ---- Phase 1 clarification outputs ----
    raw_question: str = ""
    clarification_result: ClarificationResult | None = None

    # ---- Phase 2 finalization inputs / outputs ----
    clarification_answers: dict[str, str] = {}
    finalize_result: ClarificationFinalizeResult | None = None

    # ---- downstream draw & interpret ----
    final_question: str = ""
    card_interpretations: list[CardInterpretation] = []

    # ---- synthesis & safety ----
    synthesis_output: SynthesisOutput | None = None
    safety_report: SafetyReport | None = None
