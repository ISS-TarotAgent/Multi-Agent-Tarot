"""Security-domain types shared across agent/security/ and agent/nodes/.

For business I/O schemas (Clarifier, Draw, Synthesis, Safety), see agent/schemas/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.app.domain.enums import RiskLevel  # single source of truth


class RequiredAction(str, Enum):
    CONTINUE = "continue"
    REWRITE = "rewrite"
    STRIP_CONTEXT = "strip_context"
    ASK_CLARIFICATION = "ask_clarification"
    BLOCK = "block"


class TrustLevel(str, Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    SANITIZED = "sanitized"


class ContentSource(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    TOOL = "tool"
    RETRIEVER = "retriever"


@dataclass(slots=True)
class TrustTaggedContent:
    content: str
    source: ContentSource
    trust_level: TrustLevel
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SafetyDecision:
    risk_level: RiskLevel
    allow_continue: bool
    required_action: RequiredAction
    detected_risks: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    notes_for_orchestrator: str = ""

    def is_blocking(self) -> bool:
        return self.required_action == RequiredAction.BLOCK or not self.allow_continue


@dataclass(slots=True)
class SanitizedPayload:
    sanitized_user_query: str = ""
    sanitized_context: str = ""
    removed_segments: list[str] = field(default_factory=list)
    preserved_intent: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
