"""
Security Orchestrator for handling safety checks and fallback responses.
"""

from __future__ import annotations

from typing import Any

from agent.core.schemas import ContentSource,RequiredAction
from agent.core.trust import tag_content
from agent.nodes.safety_guard import safe_fallback_node
from agent.security.pre_input_guard import inspect_user_input
from agent.security.sanitizer import sanitize_user_input

def run_pre_input_security_pipeline(user_text:str) -> dict[str,Any]:
    """
    Minimal security pipeline for raw user input.
    
    Flow:
    1. Tag input as untrusted user content
    2. Run pre-input inspection
    3. Continue/Rewrite/Block
    """

    tagged_input = tag_content(
        content=user_text,
        source=ContentSource.USER,
        metadata={"stage": "pre_input"}
    )

    decision = inspect_user_input(tagged_input)

    if decision.required_action == RequiredAction.CONTINUE:
        return {
            "status":"continue",
            "security_decision":{
                "risk_level": decision.risk_level.value,
                "allow_continue": decision.allow_continue,
                "required_action": decision.required_action.value,
                "detected_risks": decision.detected_risks,
                "evidence": decision.evidence,
                "notes_for_orchestrator": decision.notes_for_orchestrator,
            },
            "sanitized_payload":None,
            "final_response":None,
        }
    
    if decision.required_action == RequiredAction.REWRITE: 
        sanitized = sanitize_user_input(user_text)
        return {
            "status":"rewrite",
            "security_decision":{
                "risk_level": decision.risk_level.value,
                "allow_continue": decision.allow_continue,
                "required_action": decision.required_action.value,
                "detected_risks": decision.detected_risks,
                "evidence": decision.evidence,
                "notes_for_orchestrator": decision.notes_for_orchestrator,
            },
            "sanitized_payload":{
                "sanitized_user_query": sanitized.sanitized_user_query,
                "sanitized_context": sanitized.sanitized_context,
                "removed_segments": sanitized.removed_segments,
                "preserved_intent": sanitized.preserved_intent,
                "metadata": sanitized.metadata,
            },
            "final_response":None,
        }
    
    fallback_result = safe_fallback_node(decision)
    return {
        "status":"block",
        "security_decision":{
            "risk_level": decision.risk_level.value,
            "allow_continue": decision.allow_continue,
            "required_action": decision.required_action.value,
            "detected_risks": decision.detected_risks,
            "evidence": decision.evidence,
            "notes_for_orchestrator": decision.notes_for_orchestrator,
        },
        "sanitized_payload":None,
        "final_response":fallback_result["final_response"],
        "fallback_type":fallback_result["fallback_type"],
        "should_ask_rephrase":fallback_result["should_ask_rephrase"],
        "metadata":fallback_result["metadata"],
    }