"""基于 LLM 的 Agent 实现，涵盖澄清（Clarifier）、抽牌（Draw）、综合解读（Synthesis）和安全检查（Safety）四个节点。"""

from __future__ import annotations

import json
import re

from agent.core.model_gateway import ModelGateway
from agent.core.prompt_registry import load_prompt
from agent.schemas.clarifier import (
    ClarificationPrompt,
    ClarifierFinalizeInput,
    ClarifierFinalizeOutput,
    ClarifierInput,
    ClarifierOutput,
)
from agent.schemas.draw import DrawCard, DrawInput, DrawOutput
from agent.schemas.safety import LLMSafetyCheckInput, LLMSafetyCheckOutput
from agent.schemas.synthesis import SynthesisInput, SynthesisOutput
from backend.app.domain.enums import CardOrientation, CardPosition

# LLM 调用失败时的最大重试次数
_MAX_RETRIES = 3

# 三张牌阵的位置标签，顺序对应过去、现在、未来
_POSITIONS = ["PAST", "PRESENT", "FUTURE"]

# 每个位置的语义说明，作为 LLM 提示的一部分，帮助模型生成与位置相符的解读
_POSITION_MEANINGS = {
    "PAST": "The background, past influences, and what has shaped the current situation.",
    "PRESENT": "The current core tension, energy, or challenge being navigated right now.",
    "FUTURE": "The direction that can open up, and what can be worked toward from here.",
}

# 用于剥离 LLM 输出中可能包含的 ```json ... ``` Markdown 代码围栏，提取纯 JSON 文本
_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _parse_json(raw: str) -> dict:
    """ 去除 Markdown 代码围栏后解析 JSON 字符串。"""
    match = _FENCE_RE.search(raw)
    text = match.group(1) if match else raw
    return json.loads(text.strip())


class LLMClarifierAgent:
    """问题澄清 Agent，负责识别用户意图并在必要时生成追问。

    工作流分为两个阶段：
    - run()：分析原始问题，判断是否需要澄清，并生成澄清追问列表。
    - finalize()：根据用户对追问的回答，将信息整合为结构化的重构问题。
    """

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway
        # 加载两阶段各自的提示模板
        self._init_prompt_template = load_prompt("clarifier_init")
        self._finalize_prompt_template = load_prompt("clarifier_finalize")

    def run(self, payload: ClarifierInput) -> ClarifierOutput:
        """阶段一：分析原始问题，识别意图标签，生成澄清追问（最多 3 条）。

        temperature=0.2 保证输出稳定，response_format 强制返回 JSON 对象。
        若 intent_tag 不在预设范围内，回退为 "growth"（通用成长类）。
        """
        prompt = self._init_prompt_template.replace("{raw_question}", payload.raw_question)
        last_exc: Exception | None = None
        for _ in range(_MAX_RETRIES):
            try:
                response = self._gateway.run(
                    prompt,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    generation_name="clarifier_init",
                )
                data = _parse_json(response.content)

                # 校验意图标签，不合法时降级为通用类别
                intent_tag = data.get("intent_tag", "growth")
                if intent_tag not in ("career", "relationship", "study", "emotion", "growth"):
                    intent_tag = "growth"

                # 最多取前 3 条澄清追问
                raw_prompts: list[dict] = data.get("clarification_prompts", [])
                clarification_prompts = [ClarificationPrompt(**p) for p in raw_prompts[:3]]

                return ClarifierOutput(
                    normalized_question=data.get("normalized_question") or payload.raw_question,
                    clarification_required=len(clarification_prompts) > 0,
                    clarifier_question=clarification_prompts[0].question if clarification_prompts else None,
                    intent_tag=intent_tag,
                    clarification_prompts=clarification_prompts,
                )
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"ClarifierAgent.run failed after {_MAX_RETRIES} attempts") from last_exc

    def finalize(self, payload: ClarifierFinalizeInput) -> ClarifierFinalizeOutput:
        """阶段二：将用户对追问的回答整合为结构化的重构问题。

        输出包含重构后的问题文本、主题、时间范围、意图和约束条件，
        供后续抽牌节点使用。temperature=0.3 略高于阶段一，允许适度的措辞变化。
        """
        answers_json = json.dumps(payload.clarification_answers, ensure_ascii=False)
        # 将模板中的占位符替换为实际值，保留 JSON 编码以防止注入
        prompt = (
            self._finalize_prompt_template.replace(
                '"{original_question}"', json.dumps(payload.normalized_question, ensure_ascii=False)
            )
            .replace('"{intent_tag}"', json.dumps(payload.intent_tag, ensure_ascii=False))
            .replace("{clarification_answers}", answers_json)
        )
        last_exc: Exception | None = None
        for _ in range(_MAX_RETRIES):
            try:
                response = self._gateway.run(
                    prompt,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                    generation_name="clarifier_finalize",
                )
                data = _parse_json(response.content)
                return ClarifierFinalizeOutput(
                    reframed_question=data["reframed_question"],
                    topic=data.get("topic", ""),
                    time_horizon=data.get("time_horizon", "未指定"),
                    intent=data.get("intent", ""),
                    constraints=data.get("constraints", []),
                )
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"ClarifierAgent.finalize failed after {_MAX_RETRIES} attempts") from last_exc


class LLMDrawAgent:
    """抽牌与解读 Agent，负责随机抽取三张塔罗牌并逐一调用 LLM 生成解读。

    每张牌的解读独立发起一次 LLM 调用，包含位置语义、牌名、正逆位和牌义，
    输出结构化的解读文本、反思问题、注意事项和关键词。
    """

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway
        # 系统提示负责定义塔罗解读风格和输出格式
        self._system_prompt = load_prompt("draw_interpret_system_prompt")

    def run(self, payload: DrawInput) -> DrawOutput:
        """从牌组中随机抽取 3 张牌（含正逆位），并逐一通过 LLM 生成解读。

        draw_cards 返回牌面列表和随机种子，种子记录在每张牌上以便复现。
        temperature=0.7 保留适度的创意空间，使解读有变化但不失准确性。
        """
        # 延迟导入避免循环依赖
        from agent.core.tarot_deck import draw_cards

        drawn, seed = draw_cards(3, allow_reversed=True)
        cards: list[DrawCard] = []

        for pos, c in zip(_POSITIONS, drawn):
            # 将本张牌的上下文序列化为 JSON，作为用户消息传入 LLM
            card_input = json.dumps(
                {
                    "question": payload.question,
                    "position_label": pos,
                    "position_meaning": _POSITION_MEANINGS[pos],
                    "card_name": c["card_name"],
                    "card_code": c["card_code"],
                    "orientation": c["orientation"],
                    "meaning": c["meaning"],
                },
                ensure_ascii=False,
            )

            last_exc: Exception | None = None
            for _ in range(_MAX_RETRIES):
                try:
                    response = self._gateway.run(
                        card_input,
                        system_prompt=self._system_prompt,
                        temperature=0.7,
                        response_format={"type": "json_object"},
                        generation_name=f"draw_interpret_{pos.lower()}",
                    )
                    data = _parse_json(response.content)
                    cards.append(
                        DrawCard(
                            position=CardPosition(pos),
                            card_code=c["card_code"],
                            card_name=c["card_name"],
                            orientation=CardOrientation(c["orientation"]),
                            interpretation=data["interpretation"],
                            reflection_question=data.get("reflection_question"),
                            caution_note=data.get("caution_note"),
                            keywords=data.get("keywords", []),
                            meaning=c["meaning"],
                            seed=seed,
                        )
                    )
                    break
                except Exception as exc:
                    last_exc = exc
            else:
                # 三次重试均失败时向上抛出，由上层节点触发 fallback
                raise RuntimeError(f"DrawAgent failed on {pos} card after {_MAX_RETRIES} attempts") from last_exc

        return DrawOutput(cards=cards)


class LLMSynthesisAgent:
    """综合解读 Agent，将三张牌的独立解读整合为连贯的整体叙事。

    输入为三张牌的解读文本列表，输出包含总结、行动建议和反思问题，
    形成完整的塔罗阅读结论供安全检查节点使用。
    """

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway
        self._system_prompt = load_prompt("synthesis_system_prompt")

    def run(self, payload: SynthesisInput) -> SynthesisOutput:
        """将多张牌的解读整合为结构化的综合结论。

        temperature=0.7 与抽牌阶段保持一致，允许适度的叙事创意。
        """
        # 将多张牌解读拼接为带项目符号的文本块
        interpretations_text = "\n".join(f"- {interp}" for interp in payload.card_interpretations)
        user_prompt = (
            f"locale: {payload.locale}\n"
            f"question: {payload.normalized_question}\n"
            f"card_interpretations:\n{interpretations_text}"
        )
        last_exc: Exception | None = None
        for _ in range(_MAX_RETRIES):
            try:
                response = self._gateway.run(
                    user_prompt,
                    system_prompt=self._system_prompt,
                    temperature=0.7,
                    response_format={"type": "json_object"},
                    generation_name="synthesis",
                )
                data = _parse_json(response.content)
                return SynthesisOutput(
                    summary=data["summary"],
                    action_advice=data["action_advice"],
                    reflection_question=data["reflection_question"],
                )
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"SynthesisAgent failed after {_MAX_RETRIES} attempts") from last_exc


class LLMSafetyAgent:
    """基于 LLM 的语义安全评估 Agent，作为规则关键词扫描的第二道检查。

    仅在规则层未命中高风险关键词时调用，对中风险或语义模糊的内容进行
    上下文感知的深度评估。高风险关键词始终由规则层直接拦截，不经过此 Agent。

    返回风险等级（HIGH / MEDIUM / LOW）和推理说明，供安全守卫节点决策。
    """

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway
        self._system_prompt = load_prompt("security/safety_guard_system_prompt")

    def evaluate(self, payload: LLMSafetyCheckInput) -> LLMSafetyCheckOutput:
        """对综合解读文本进行语义安全评估。

        temperature=0.0 确保评估结果确定性最高，避免随机性影响安全判断。
        若返回的 risk_level 不在合法范围内，保守地降级为 MEDIUM。
        """
        # 将待评估内容序列化为 JSON，连同已命中的关键词一起提交给 LLM
        user_prompt = json.dumps(
            {
                "question": payload.question,
                "synthesis_text": payload.synthesis_text,
                "keyword_hits": payload.keyword_hits,
            },
            ensure_ascii=False,
        )
        last_exc: Exception | None = None
        for _ in range(_MAX_RETRIES):
            try:
                response = self._gateway.run(
                    user_prompt,
                    system_prompt=self._system_prompt,
                    temperature=0.0,
                    response_format={"type": "json_object"},
                    generation_name="safety_guard_llm",
                )
                data = _parse_json(response.content)
                # 校验返回的风险等级，非法值保守处理为 MEDIUM
                risk_level = data.get("risk_level", "MEDIUM").upper()
                if risk_level not in ("HIGH", "MEDIUM", "LOW"):
                    risk_level = "MEDIUM"
                return LLMSafetyCheckOutput(
                    risk_level=risk_level,
                    reasoning=data.get("reasoning", ""),
                )
            except Exception as exc:
                last_exc = exc
        raise RuntimeError(f"LLMSafetyAgent failed after {_MAX_RETRIES} attempts") from last_exc
