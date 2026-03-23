"""Draw & Interpret Agent node stub."""

from __future__ import annotations

from agent.core import schemas


async def draw_and_interpret_node(state: schemas.OrchestratorState) -> schemas.OrchestratorState:
    """Handle card selection and per-card narrative.

    TODO:
        - ensure ClarificationResult present
        - fetch card deck config + prompt template
        - call ModelGateway with structured instructions
        - parse response into list[CardInterpretation]
        - attach interpretations to orchestration state
    """

    raise NotImplementedError("Draw & Interpret node logic is pending implementation")
