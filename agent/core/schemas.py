"""Typed data contracts shared across agents.

Each Agent node should import the relevant schema objects instead of defining
ad-hoc dictionaries. Concrete fields intentionally left as TODOs for the feature
owners who will supply final business logic.
"""

from __future__ import annotations

from pydantic import BaseModel
from dataclasses import dataclass,field
from enum import Enum
from typing import Any

# Safety-related enums and data classes
"""判断内容风险级别的枚举类型，包含低、中、高和关键四个级别"""
class RiskLevel(str,Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

"""判断内容需要采取的行动的枚举类型，包含继续、重写、剥离上下文、询问澄清和阻止五个选项"""
class RequiredAction(str,Enum):
    CONTINUE = "continue"
    REWRITE = "rewrite"
    STRIP_CONTEXT = "strip_context"
    ASK_CLARIFICATION = "ask_clarification"
    BLOCK = "block"

"""判断内容信任级别的枚举类型，包含可信、不可信和已清洗三个级别"""
class TrustLevel(str,Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    SANITIZED = "sanitized"

"""内容来源的枚举类型，包含用户、代理、系统、工具和检索器五个选项"""
class ContentSource(str,Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    TOOL = "tool"
    RETRIEVER = "retriever"

"""定义了一个数据类，用于表示带有信任标签的内容，包括内容本身、来源、信任级别和相关的元数据"""
@dataclass(slots=True)
class TrustTaggedContent:
    content: str
    source: ContentSource
    trust_level: TrustLevel
    metadata: dict[str, Any] = field(default_factory=dict)

"""定义了一个数据类，用于表示安全决策的结果，包括风险级别、是否允许继续、需要采取的行动、检测到的风险列表、证据列表以及给编排器的备注信息"""
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

"""定义了一个数据类，用于表示经过清洗的用户查询和上下文信息，包括清洗后的用户查询、清洗后的上下文、被移除的内容片段列表、保留的意图以及相关的元数据"""
@dataclass(slots=True)
class SanitizedPayload:
    sanitized_user_query: str = ""
    sanitized_context: str = ""
    removed_segments: list[str] = field(default_factory=list)
    preserved_intent: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

# Other shared schemas for the Tarot Agent workflow (placeholders for now)
class ClarificationRequest(BaseModel):
    """Incoming payload for the Clarifier Agent.

    TODO:
        - add raw user question
        - add optional conversation/session identifiers
        - add guardrails metadata (language, tone, etc.)
    """

    pass


class ClarificationResult(BaseModel):
    """Structured output from the Clarifier Agent.

    TODO:
        - add canonical question statement
        - add intent taxonomy tags / confidence score
        - add downstream instructions (e.g., spread preference)
    """

    pass


class CardInterpretation(BaseModel):
    """Represents a single Tarot card draw and explanation.

    TODO:
        - add card id/name/upright-or-reversed flag
        - add key themes and tie-back narrative
        - add any subjective risk notes
    """

    pass


class SynthesisInput(BaseModel):
    """Bundle of clarified intent plus all per-card interpretations.

    TODO:
        - reference ClarificationResult
        - include list[CardInterpretation]
        - add contextual knobs (tone, depth, cultural guardrails)
    """

    pass


class SynthesisOutput(BaseModel):
    """Composite insights and action plan suggested to the user.

    TODO:
        - add structured reflection sections (insight, actions, questions)
        - add trace references back to card ids
        - capture uncertainty markers for Safety review
    """

    pass


class SafetyReport(BaseModel):
    """Findings from the Safety Guard Agent.

    TODO:
        - flag high-risk statements
        - attach mitigation instructions or rewritten text
        - store reviewer notes for observability/traceability
    """

    pass


class OrchestratorState(BaseModel):
    """State container passed between LangGraph nodes.

    TODO:
        - aggregate fields above into a single workflow state
        - include trace/log identifiers for Langfuse or JSON logging
        - carry retry counters and escalation flags
    """

    pass
