"""
一个规则检测器,用于检测是否满足某些条件, 以触发相应的行为.
目的:
- 优先拦截明显违规的行为, 以保护系统安全.
- 给后面的pre_input_guard.py提供可调用的函数
- 输出尽量简单,稳定,可测试
"""

from __future__ import annotations

import re
from dataclasses import dataclass,field

@dataclass(slots=True)
class DetectionResult:
    detected: bool
    risk_type: str
    evidence: list[str] = field(default_factory=list)
    matched_patterns: list[str] = field(default_factory=list)

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions?",
    r"disregard\s+(all\s+)?previous\s+instructions?",
    r"forget\s+(all\s+)?previous\s+instructions?",
    r"bypass\s+safety",
    r"do\s+not\s+follow\s+the\s+above\s+rules",
]

SECRET_EXFILTRATION_PATTERNS = [
    r"reveal\s+(your\s+)?system\s+prompt",
    r"show\s+(your\s+)?hidden\s+prompt",
    r"print\s+(the\s+)?system\s+message",
    r"leak\s+(the\s+)?internal\s+instructions?",
    r"tell\s+me\s+your\s+policy",
]

ROLE_ESCALATION_PATTERNS = [
    r"act\s+as\s+(the\s+)?developer",
    r"pretend\s+to\s+be\s+(the\s+)?developer",
    r"you\s+are\s+now\s+(the\s+)?admin",
    r"act\s+as\s+(the\s+)?system",
    r"you\s+are\s+no\s+longer\s+(an\s+)?assistant",
]

INSTRUCTION_OVERRIDE_PATTERNS = [
    r"new\s+instructions?:",
    r"from\s+now\s+on[,:\s]",
    r"your\s+new\s+role\s+is",
    r"the\s+following\s+rules\s+override",
    r"ignore\s+the\s+system\s+message",
]

SUSPICIOUS_PATTERNS = [
    r"```(?:system|prompt|policy)?",
    r"<system>",
    r"</system>",
    r"base64",
    r"decode\s+this",
    r"execute\s+this",
]

def _find_matches(text: str,patterns: list[str]) -> list[str]:
    """
    Helper function to find all regex pattern matches in the given text.
    """
    if not text:
        return []
    
    normalized = text.lower()
    matched = []

    for pattern in patterns:
        if re.search(pattern,normalized,flags=re.IGNORECASE):
            matched.append(pattern)
    return matched

def detect_prompt_injection(text:str) -> DetectionResult:
    matches = _find_matches(text,PROMPT_INJECTION_PATTERNS)
    return DetectionResult(
        detected=bool(matches),
        risk_type="prompt_injection", 
        evidence=["Matched prompt injection pattern"] if matches else [],
        matched_patterns=matches
    )

def detect_secret_exfiltration(text:str) -> DetectionResult:
    matches = _find_matches(text,SECRET_EXFILTRATION_PATTERNS)
    return DetectionResult(
        detected=bool(matches),
        risk_type="secret_exfiltration",
        evidence=["Matched secret exfiltration pattern"] if matches else [],
        matched_patterns=matches
    )

def detect_role_escalation(text:str) -> DetectionResult:
    matches = _find_matches(text,ROLE_ESCALATION_PATTERNS)
    return DetectionResult(
        detected=bool(matches),
        risk_type="role_escalation",
        evidence=["Matched role escalation pattern"] if matches else [],
        matched_patterns=matches
    )

def detect_instruction_override(text:str) -> DetectionResult:
    matches = _find_matches(text,INSTRUCTION_OVERRIDE_PATTERNS)
    return DetectionResult(
        detected=bool(matches),
        risk_type="instruction_override",
        evidence=["Matched instruction override pattern"] if matches else [],
        matched_patterns=matches
    )

def detect_suspicious_content(text:str) -> DetectionResult:
    matches = _find_matches(text,SUSPICIOUS_PATTERNS)
    return DetectionResult(
        detected=bool(matches),
        risk_type="suspicious_content",
        evidence=["Matched suspicious content pattern"] if matches else [],
        matched_patterns=matches
    )

def run_all_detectors(text:str) -> list[DetectionResult]:
    """
    Run all detectors on the given text and return a list of DetectionResults.
    """
    detectors = [
        detect_prompt_injection,
        detect_secret_exfiltration,
        detect_role_escalation,
        detect_instruction_override,
        detect_suspicious_content,
    ]
    results = []
    for detector in detectors:
        result = detector(text)
        if result.detected:
            results.append(result)
    return results