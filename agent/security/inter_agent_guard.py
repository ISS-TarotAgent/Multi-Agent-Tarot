"""
Inter-agent output guard.

Validates LLM-generated content before it is passed between agents,
defending against indirect prompt injection where a compromised upstream
LLM embeds malicious instructions into its output.

Architecture note (docs/04-System-Architecture.md):
    "safety 不应该只是在最后做输出检查，还是在每次 Agent 之间进行信息传递时进行"
"""

from __future__ import annotations

import logging
from typing import Any

from agent.core.schemas import ContentSource, SafetyDecision
from agent.core.trust import tag_content
from agent.security.pre_input_guard import inspect_user_input

logger = logging.getLogger(__name__)

# Agent outputs that trigger blocking are rare; log them at WARNING level
# so they surface in traces without creating noise in normal operation.


def validate_agent_output(agent_name: str, output_text: str) -> SafetyDecision:
    """
    Check LLM agent output for injected instructions before passing downstream.

    Agent outputs are tagged as UNTRUSTED AGENT content. The same detector
    suite used for user input is applied here — injection patterns embedded
    by a misbehaving or adversarially-influenced LLM are structurally
    identical to those attempted directly by users.

    Args:
        agent_name: Name of the originating agent (used for logging/metadata).
        output_text: The raw text content produced by the agent.

    Returns:
        SafetyDecision indicating whether content is safe to pass downstream.
    """
    tagged = tag_content(
        content=output_text,
        source=ContentSource.AGENT,
        metadata={"agent": agent_name, "stage": "inter_agent"},
    )
    decision = inspect_user_input(tagged)

    if not decision.allow_continue:
        logger.warning(
            "[inter_agent_guard] Suspicious output from agent=%s "
            "risk=%s action=%s risks=%s",
            agent_name,
            decision.risk_level.value,
            decision.required_action.value,
            decision.detected_risks,
        )
    else:
        logger.debug(
            "[inter_agent_guard] Agent output cleared agent=%s risk=%s",
            agent_name,
            decision.risk_level.value,
        )

    return decision


def is_safe_to_pass(decision: SafetyDecision) -> bool:
    """Return True only when the agent output is cleared to pass downstream."""
    return decision.allow_continue


def inter_agent_guard(agent_name: str, output_text: str) -> dict[str, Any]:
    """
    Node-callable wrapper: validate agent output and return a structured result.

    Never raises — always returns a dict so the caller (orchestrator or node)
    can decide how to handle a flagged output without crashing the workflow.

    Args:
        agent_name: Name of the originating agent.
        output_text: Raw text content from the agent.

    Returns:
        Dict with keys:
            safe_to_continue (bool): Whether to proceed to the next agent.
            risk_level (str): Detected risk level.
            required_action (str): Recommended action.
            detected_risks (list[str]): Risk type identifiers.
            evidence (list[str]): Matching evidence snippets.
            notes (str): Human-readable notes for the orchestrator.
    """
    decision = validate_agent_output(agent_name, output_text)

    return {
        "agent_name": agent_name,
        "safe_to_continue": is_safe_to_pass(decision),
        "risk_level": decision.risk_level.value,
        "required_action": decision.required_action.value,
        "detected_risks": decision.detected_risks,
        "evidence": decision.evidence,
        "notes": decision.notes_for_orchestrator,
    }
