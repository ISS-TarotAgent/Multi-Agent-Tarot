from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

# 预定义的意图标签，用于对用户问题进行分类和标记。可以根据实际需求调整标签内容。
# 暂定为职业、关系、学业、情感和成长五大类，覆盖常见的塔罗咨询主题。
IntentTag = Literal["career", "relationship", "study", "emotion", "growth"]


# 澄清器相关的数据模型定义，包括输入输出结构和澄清提示的格式。这些模型用于在澄清阶段传递数据和结果。
class ClarificationPrompt(BaseModel):
    # 严格禁止额外字段，确保数据结构的清晰和一致性。
    model_config = ConfigDict(extra="forbid")

    # 每个澄清提示包含一个唯一标识符、要提问的问题文本、辅助说明和输入占位符。这些信息用于生成针对用户问题的澄清问题。
    id: str
    question: str
    helper_text: str
    placeholder: str


# 澄清器的输入模型，包含用户的原始问题和语言环境等基本信息。
class ClarifierInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 用户输入的原始问题文本，以及用户的语言环境（locale），这些信息将用于生成澄清问题和后续处理。
    raw_question: str
    locale: str


# 澄清器的输出模型，包含规范化后的问题文本、是否需要澄清、澄清问题的内容、意图标签以及生成的澄清提示列表。
class ClarifierOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_question: str
    clarification_required: bool
    clarifier_question: str | None = None
    intent_tag: IntentTag = "growth"
    clarification_prompts: list[ClarificationPrompt] = []


# 澄清器第二阶段的输入模型，包含规范化后的问题文本、意图标签、语言环境和用户对澄清提示的回答。这些信息将用于生成最终的重构问题。
class ClarifierFinalizeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_question: str
    intent_tag: IntentTag
    locale: str
    clarification_answers: dict[str, str]


# 澄清器第二阶段的输出模型，包含重构后的问题文本、主题、时间范围、意图和相关约束条件。这些信息将用于后续的牌阵解读和综合分析。
class ClarifierFinalizeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reframed_question: str
    topic: str
    time_horizon: str
    intent: str
    constraints: list[str] = []
