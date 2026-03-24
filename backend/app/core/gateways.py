"""Backend-facing adapters for the shared ModelGateway abstractions."""

from __future__ import annotations

from agent.core import model_gateway

_gateway: model_gateway.ModelGateway | None = None


def get_model_gateway() -> model_gateway.ModelGateway:
    """Return the singleton gateway instance.

    TODO:
        - instantiate OpenAIModelGateway using config Settings
        - support future providers via registry
        - add lifecycle hooks for FastAPI startup/shutdown
    """

    if _gateway is None:  # pragma: no cover - will be replaced in implementation
        raise NotImplementedError("Model gateway not initialized")
    return _gateway
