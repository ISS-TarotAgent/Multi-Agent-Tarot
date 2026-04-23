"""
Pre-input guard for validating and sanitizing user input before processing.
"""

from __future__ import annotations
from agent.core.schemas import (
    RequiredAction,
    RiskLevel,
    SafetyDecision,
    TrustTaggedContent,
)
from agent.security.detectors import run_all_detectors, DetectionResult

HIGH_RISK_TYPES = {
    "prompt_injection",
    "secret_exfiltration",
    "role_escalation",
}

MEDIUM_RISK_TYPES = {
    "instruction_override",
    "suspicious_patterns",
}


def _aggregate_detection_results(
    detection_results: list[DetectionResult],
) -> SafetyDecision:
    """
    Aggregates detection results into a single safety decision.
    """
    # 没有检测到任何风险，允许继续
    if not detection_results:
        return SafetyDecision(
            risk_level=RiskLevel.LOW,
            allow_continue=True,
            required_action=RequiredAction.CONTINUE,
            detected_risks=[],
            evidence=[],
            notes_for_orchestrator="No risks detected.",
        )

    # 汇总检测到的风险类型和证据
    detected_risks = [result.risk_type for result in detection_results]
    evidence = []

    for result in detection_results:
        evidence.extend(result.evidence)
        evidence.extend(result.matched_patterns)

    if any(result.risk_type in HIGH_RISK_TYPES for result in detection_results):
        return SafetyDecision(
            risk_level=RiskLevel.HIGH,
            allow_continue=False,
            required_action=RequiredAction.BLOCK,
            detected_risks=detected_risks,
            evidence=evidence,
            notes_for_orchestrator="High risk content detected. Blocking input.",
        )

    if any(result.risk_type in MEDIUM_RISK_TYPES for result in detection_results):
        return SafetyDecision(
            risk_level=RiskLevel.MEDIUM,
            allow_continue=False,
            required_action=RequiredAction.REWRITE,
            detected_risks=detected_risks,
            evidence=evidence,
            notes_for_orchestrator="Medium risk content detected. Asking for clarification.",
        )

    return SafetyDecision(
        risk_level=RiskLevel.MEDIUM,
        allow_continue=False,
        required_action=RequiredAction.REWRITE,
        detected_risks=detected_risks,
        evidence=evidence,
        notes_for_orchestrator="Unclassified suspicious input detected. Prefer sanitization.",
    )


def inspect_user_input(tagged_input: TrustTaggedContent) -> SafetyDecision:
    """
    Run the first-pass security checks on raw usre input.

    Expected input:
    - tagged_input.source should normally be USER
    - tagged_input.trust_level should normally be UNTRUSTED
    """
    detection_results = run_all_detectors(tagged_input.content)
    safety_decision = _aggregate_detection_results(detection_results)
    return safety_decision


# 提供节点,供编排器在接收到用户输入后调用
def pre_input_guard_node(user_text: str) -> SafetyDecision:
    from agent.core.schemas import ContentSource, TrustTaggedContent
    from agent.core.trust import tag_content

    tagged = tag_content(user_text, source=ContentSource.USER)
    return inspect_user_input(tagged)
