"""Typed data contracts shared across agents.

Each Agent node should import the relevant schema objects instead of defining
ad-hoc dictionaries. Concrete fields intentionally left as TODOs for the feature
owners who will supply final business logic.
"""

from __future__ import annotations

from pydantic import BaseModel


class ClarificationRequest(BaseModel):
    """Incoming payload for the Clarifier Agent.

    TODO:
        - add raw user question
        - add optional conversation/session identifiers
        - add guardrails metadata (language, tone, etc.)
    """

    pass


class ClarificationResult(BaseModel):
    """Structured output from the Clarifier Agent.

    TODO:
        - add canonical question statement
        - add intent taxonomy tags / confidence score
        - add downstream instructions (e.g., spread preference)
    """

    pass


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

    TODO:
        - aggregate fields above into a single workflow state
        - include trace/log identifiers for Langfuse or JSON logging
        - carry retry counters and escalation flags
    """

    pass
