"""Synthesis Agent node: combine card interpretations into structured reflection."""

from __future__ import annotations

import asyncio
import json
import logging
import re

from pydantic import ValidationError

from agent.core import model_gateway as gateways
from agent.schemas import synthesis as synthesis_schemas
from agent.core.prompt_registry import load_prompt

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gateway injection
# ---------------------------------------------------------------------------

_gateway: gateways.ModelGateway | None = None


def set_gateway(gateway: gateways.ModelGateway) -> None:
    """Used by the orchestrator/bootstrap code to supply a concrete gateway."""
    global _gateway
    _gateway = gateway


def _get_gateway() -> gateways.ModelGateway:
    if _gateway is None:
        raise RuntimeError(
            "ModelGateway has not been set. Call synthesis.set_gateway() before invoking nodes."
        )
    return _gateway


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

_MAX_ATTEMPTS = 3
_RETRY_DELAY_SECONDS = 1.0


async def _run_with_retry(prompt: str) -> str:
    """Call the gateway with up to _MAX_ATTEMPTS attempts, raising on final failure."""
    gateway = _get_gateway()
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            return gateway.run(prompt)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("Gateway call failed (attempt %d/%d): %s", attempt, _MAX_ATTEMPTS, exc)
            if attempt < _MAX_ATTEMPTS:
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# JSON extraction helper
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> str:
    """Strip markdown fences and whitespace around a JSON payload."""
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


# ---------------------------------------------------------------------------
# Fallback output
# ---------------------------------------------------------------------------

def _create_fallback_output() -> synthesis_schemas.SynthesisOutput:
    """Return a safe fallback when synthesis fails."""
    return synthesis_schemas.SynthesisOutput(
        summary="Please take time to reflect on the three cards and how they speak to your question.",
        action_advice="Consider what resonates most with you and how you might apply these insights.",
        reflection_question="What patterns or themes do these three cards reveal to you?"
    )


# ---------------------------------------------------------------------------
# Synthesis node
# ---------------------------------------------------------------------------

async def synthesis_node(synthesis_input: synthesis_schemas.SynthesisInput) -> synthesis_schemas.SynthesisOutput:
    """Combine card interpretations into a structured reflection.
    
    Takes the normalized question, card interpretations (as strings), and locale,
    and produces a cohesive summary, action advice, and reflection question.
    """
    
    logger.info(
        "[synthesis] Processing with %d cards, locale=%r",
        len(synthesis_input.card_interpretations), synthesis_input.locale
    )
    
    try:
        # ---- Load prompt template ----
        system_prompt = load_prompt("synthesis_system_prompt")
        
        # ---- Construct user message ----
        user_message = _build_user_message(synthesis_input)
        full_prompt = f"{system_prompt}\n\n{user_message}"
        
        logger.debug("[synthesis] Full prompt length=%d", len(full_prompt))
        
        # ---- Call ModelGateway ----
        raw_response = await _run_with_retry(full_prompt)
        logger.debug(
            "[synthesis] Raw response (first 300 chars): %s",
            raw_response[:300]
        )
        
        # ---- Parse response ----
        output = _parse_synthesis_response(raw_response)
        
        logger.info("[synthesis] Successfully synthesized output.")
        return output
        
    except (json.JSONDecodeError, ValidationError, ValueError) as e:
        logger.error("[synthesis] Failed to parse/validate response: %s", e)
        return _create_fallback_output()
    except Exception as e:  # noqa: BLE001
        logger.error("[synthesis] Unexpected error: %s", e, exc_info=True)
        return _create_fallback_output()


def _build_user_message(synthesis_input: synthesis_schemas.SynthesisInput) -> str:
    """Construct the user message from SynthesisInput."""
    
    lines = []
    lines.append("# User's Question")
    lines.append(f"\n{synthesis_input.normalized_question}")
    
    lines.append("\n\n# Card Interpretations")
    lines.append("\n")
    
    for i, interpretation in enumerate(synthesis_input.card_interpretations, 1):
        lines.append(f"## Card {i}\n")
        lines.append(f"{interpretation}\n")
    
    lines.append(f"\n# Requested Language\n")
    lines.append(f"Respond in: {synthesis_input.locale}")
    
    return "\n".join(lines)


def _parse_synthesis_response(raw_response: str) -> synthesis_schemas.SynthesisOutput:
    """Parse the LLM's JSON response into a SynthesisOutput."""
    
    # Strip markdown fences if present
    json_str = _extract_json(raw_response)
    
    # Parse JSON
    data = json.loads(json_str)
    
    # Validate and construct output
    output = synthesis_schemas.SynthesisOutput(
        summary=data.get("summary", ""),
        action_advice=data.get("action_advice", ""),
        reflection_question=data.get("reflection_question", "")
    )
    
    return output
