"""Synthesis Agent node stub."""

from __future__ import annotations

from agent.core import schemas


async def synthesis_node(state: schemas.OrchestratorState) -> schemas.OrchestratorState:
    """Combine all prior insights into a structured reflection.

    TODO:
        - validate ClarificationResult + CardInterpretation list
        - assemble SynthesisInput dataclass
        - call ModelGateway with synthesis prompt
        - populate SynthesisOutput and update state
    """

    raise NotImplementedError("Synthesis node logic is pending implementation")
