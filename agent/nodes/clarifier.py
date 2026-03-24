"""Clarifier Agent node stub."""

from __future__ import annotations

from typing import Any

from agent.core import model_gateway as gateways
from agent.core import schemas


# TODO: inject real gateway via dependency container
_gateway: gateways.ModelGateway | None = None


def set_gateway(gateway: gateways.ModelGateway) -> None:
    """Used by the orchestrator/bootstrap code to supply a concrete gateway."""

    global _gateway
    _gateway = gateway


async def clarifier_node(state: schemas.OrchestratorState) -> schemas.OrchestratorState:
    """Perform question clarification.

    TODO:
        - validate incoming ClarificationRequest
        - craft prompt via prompt_registry
        - call _gateway.run
        - parse response into ClarificationResult and update state
    """

    raise NotImplementedError("Clarifier node logic is pending implementation")
