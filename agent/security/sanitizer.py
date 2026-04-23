"""
Sanitization functions for cleaning and validating user input.
"""
# 实现一个基本的清洗函数，去除敏感词汇和潜在的攻击性内容

import re

from agent.core.schemas import SanitizedPayload
from agent.security.detectors import (
    INSTRUCTION_OVERRIDE_PATTERNS,
    PROMPT_INJECTION_PATTERNS,
    ROLE_ESCALATION_PATTERNS,
    SECRET_EXFILTRATION_PATTERNS,
    SUSPICIOUS_PATTERNS,
)

REMOVAL_PATTERNS = (
    PROMPT_INJECTION_PATTERNS
    + INSTRUCTION_OVERRIDE_PATTERNS
    + ROLE_ESCALATION_PATTERNS
    + SECRET_EXFILTRATION_PATTERNS
    + SUSPICIOUS_PATTERNS
)


def _remove_pattern_matches(text: str, patterns: list[str]) -> tuple[str, list[str]]:
    """
    Remove all matched suspicious segments from text and return:
    - cleaned text
    - list of removed regex patterns
    """
    if not text:
        return "", []

    cleaned = text
    removed_patterns: list[str] = []

    for pattern in patterns:
        if re.search(pattern, cleaned, flags=re.IGNORECASE):
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
            removed_patterns.append(pattern)

    return cleaned, removed_patterns


def _normalize_text(text: str) -> str:
    """
    Normalize whitespace and punctuation leftovers after sanitization.
    """
    if not text:
        return ""

    text = re.sub(r"\s+", "", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip("\n\t,.;:")


def _extract_preserved_intent(cleaned_text: str) -> str:
    """
    Try to preserve the user's legitimate tarot-related intent.
    If nothing useful remains, return an empty string.
    """
    if not cleaned_text:
        return ""

    lowered = cleaned_text.lower()

    # TODO: 重新思考Tarot相关关键词的设计，确保覆盖用户可能的表达方式
    tarot_keywords = [
        "tarot",
        "占卜",
        "塔罗",
        "牌阵",
        "解读",
        "占卜师",
        "牌面",
        "牌意",
    ]

    if any(keyword in lowered for keyword in tarot_keywords):
        return cleaned_text.strip()

    return ""


def sanitize_user_input(text: str) -> SanitizedPayload:
    """
    Sanitize user input by removing suspicious segments while trying to preserve intent.
    Returns a SanitizedPayload with cleaned query, removed segments, and preserved intent.
    """
    cleaned_text, removed_patterns = _remove_pattern_matches(text, list(REMOVAL_PATTERNS))
    normalized_text = _normalize_text(cleaned_text)
    preserved_intent = _extract_preserved_intent(normalized_text)

    sanitized_query = preserved_intent or normalized_text

    return SanitizedPayload(
        sanitized_user_query=sanitized_query,
        sanitized_context="",
        removed_segments=removed_patterns,
        preserved_intent=preserved_intent,
        metadata={
            "sanitizer_version": "rule_based_v1",
            "original_length": len(text or ""),
            "cleaned_length": len(sanitized_query or ""),
        },
    )
