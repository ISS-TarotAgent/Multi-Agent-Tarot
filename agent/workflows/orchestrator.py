"""LangGraph workflow assembly for the Tarot experience."""

from __future__ import annotations

from typing import Any

# LangGraph import left optional until dependency is added.
try:  # pragma: no cover - optional dependency during scaffolding
    from langgraph.graph import StateGraph
except ImportError:  # pragma: no cover
    StateGraph = Any  # type: ignore

from agent.core import schemas
from agent.nodes import clarifier, draw_and_interpret, safety_guard, synthesis


def build_tarot_workflow() -> StateGraph:
    """Construct the main LangGraph workflow.

    TODO:
        - replace `StateGraph = Any` with actual LangGraph import when available
        - register nodes in execution order (clarify -> draw -> synthesize -> safety)
        - add conditional branches for re-clarification retries
        - surface Langfuse/JSON log hooks
    """

    raise NotImplementedError("Workflow assembly pending LangGraph dependency")
