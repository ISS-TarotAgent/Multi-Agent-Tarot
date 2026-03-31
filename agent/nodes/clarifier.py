"""Clarifier Agent nodes: Phase 1 (init) and Phase 2 (finalize)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from agent.core import model_gateway as gateways
from agent.core import schemas
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
            "ModelGateway has not been set. Call clarifier.set_gateway() before invoking nodes."
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
    # Remove ```json ... ``` or ``` ... ``` wrappers produced by some models
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


# ---------------------------------------------------------------------------
# Default fallback datasets（写死的备用问题，保底）
# ---------------------------------------------------------------------------

_DEFAULT_PROMPTS_BY_INTENT: dict[str, list[dict[str, str]]] = {
    "career": [
        {
            "id": "q1",
            "question": "你目前在职场上面临的主要挑战是什么？",
            "helper_text": "了解当前处境有助于塔罗牌更准确地指引职业方向。",
            "placeholder": "例如：是否要接受一个新的工作机会",
        },
        {
            "id": "q2",
            "question": "你希望这次塔罗解读聚焦于哪个时间范围？",
            "helper_text": "时间范围帮助塔罗牌定位能量走向。",
            "placeholder": "例如：未来三个月内",
        },
    ],
    "relationship": [
        {
            "id": "q1",
            "question": "这段关系目前处于什么阶段（刚认识、稳定交往、面临转折等）？",
            "helper_text": "关系阶段影响塔罗牌对双方能量状态的解读。",
            "placeholder": "例如：我们在一起两年，最近出现摩擦",
        },
        {
            "id": "q2",
            "question": "你最希望通过塔罗解读了解哪方面（对方态度、关系走向、自身角色等）？",
            "helper_text": "明确焦点让解读更有针对性。",
            "placeholder": "例如：想了解对方是否有同样的感情",
        },
    ],
    "study": [
        {
            "id": "q1",
            "question": "你面临的学习或考试目标是什么？",
            "helper_text": "具体目标帮助塔罗牌聚焦于你的学习能量。",
            "placeholder": "例如：准备六月的研究生入学考试",
        },
        {
            "id": "q2",
            "question": "你目前在学习上遇到的最大障碍是什么？",
            "helper_text": "了解障碍有助于解读如何突破瓶颈。",
            "placeholder": "例如：效率低下，容易分心",
        },
    ],
    "emotion": [
        {
            "id": "q1",
            "question": "你目前的情绪状态可以用哪几个词来描述？",
            "helper_text": "情绪关键词帮助塔罗牌感知你当下的内在能量。",
            "placeholder": "例如：焦虑、迷茫、有些疲惫",
        },
        {
            "id": "q2",
            "question": "这种情绪状态持续了多久？",
            "helper_text": "时间维度帮助判断这是短期波动还是需要更深层探索的模式。",
            "placeholder": "例如：大约一个月了",
        },
    ],
    "growth": [
        {
            "id": "q1",
            "question": "你目前最想探索的人生议题是什么？",
            "helper_text": "了解你关注的核心方向，有助于塔罗牌更准确地回应你的内心。",
            "placeholder": "例如：我想了解自己接下来的发展方向",
        },
        {
            "id": "q2",
            "question": "你希望这次解读帮助你达成什么？",
            "helper_text": "明确期望让塔罗牌的指引更有实际意义。",
            "placeholder": "例如：找到前进的动力和方向",
        },
    ],
}

_FALLBACK_INIT_RESULT_TEMPLATE = {
    "normalized_question": "",
    "intent_tag": "growth",
    "clarification_prompts": [
        {
            "id": "q1",
            "question": "你目前最想探索的人生议题是什么？",
            "helper_text": "了解你关注的核心方向，有助于塔罗牌更准确地回应你的内心。",
            "placeholder": "例如：我想了解自己接下来的发展方向",
        }
    ],
}

_FALLBACK_FINALIZE_RESULT = schemas.ClarificationFinalizeResult(
    reframed_question="在当前人生阶段，我内心最需要探索和理解的是什么？",
    topic="自我探索与方向感知",
    time_horizon="未指定",
    intent="寻求对当下状态的内在洞察",
    constraints=[],
)


# ---------------------------------------------------------------------------
# Phase 1: clarifier_init_node
# ---------------------------------------------------------------------------

async def clarifier_init_node(state: schemas.OrchestratorState) -> schemas.OrchestratorState:
    """Phase 1 – identify intent and generate clarification prompts.

    Loads the ``clarifier_init`` prompt template, calls the LLM, parses the
    JSON response into a ``ClarificationResult``, and writes the result back
    into the shared ``OrchestratorState``.

    Falls back to per-intent default questions when the LLM call fails or
    returns malformed JSON.
    """
    raw_question = state.raw_question.strip()
    session_id = state.session_id

    logger.info("[clarifier_init] session=%s raw_question=%r", session_id, raw_question[:80])

    try:
        prompt_template = load_prompt("clarifier_init")
        prompt = prompt_template.replace("{raw_question}", raw_question)

        raw_response = await _run_with_retry(prompt)
        json_str = _extract_json(raw_response)
        parsed = json.loads(json_str)

        # Validate and build the result
        intent_tag: schemas.IntentTag = parsed.get("intent_tag", "growth")
        if intent_tag not in ("career", "relationship", "study", "emotion", "growth"):
            logger.warning(
                "[clarifier_init] Invalid intent_tag %r, defaulting to 'growth'", intent_tag
            )
            intent_tag = "growth"

        normalized_question: str = parsed.get("normalized_question") or raw_question

        raw_prompts: list[dict[str, Any]] = parsed.get("clarification_prompts", [])
        if not raw_prompts:
            raw_prompts = _DEFAULT_PROMPTS_BY_INTENT.get(intent_tag, _DEFAULT_PROMPTS_BY_INTENT["growth"])

        clarification_prompts = [schemas.ClarificationPrompt(**p) for p in raw_prompts[:3]]

        result = schemas.ClarificationResult(
            session_id=session_id,
            original_question=raw_question,
            normalized_question=normalized_question,
            intent_tag=intent_tag,
            clarification_prompts=clarification_prompts,
        )

        logger.info(
            "[clarifier_init] success intent=%s prompts=%d",
            intent_tag,
            len(clarification_prompts),
        )

    except (json.JSONDecodeError, KeyError, ValidationError) as exc:
        logger.warning("[clarifier_init] Parse/validation error, falling back: %s", exc)
        result = _build_fallback_init_result(session_id, raw_question)

    except Exception as exc:  # noqa: BLE001
        logger.error("[clarifier_init] LLM call failed after retries, falling back: %s", exc)
        result = _build_fallback_init_result(session_id, raw_question)

    return state.model_copy(update={"clarification_result": result})


def _build_fallback_init_result(
    session_id: str, raw_question: str
) -> schemas.ClarificationResult:
    """Construct a safe fallback ClarificationResult when LLM is unavailable."""
    fallback_prompts = [
        schemas.ClarificationPrompt(**p)
        for p in _FALLBACK_INIT_RESULT_TEMPLATE["clarification_prompts"]  # type: ignore[arg-type]
    ]
    return schemas.ClarificationResult(
        session_id=session_id,
        original_question=raw_question,
        normalized_question=raw_question,
        intent_tag="growth",
        clarification_prompts=fallback_prompts,
    )


# ---------------------------------------------------------------------------
# Phase 2: clarifier_finalize_node
# ---------------------------------------------------------------------------

async def clarifier_finalize_node(state: schemas.OrchestratorState) -> schemas.OrchestratorState:
    """Phase 2 – synthesise clarification answers into a reframed question.

    Reads the ``clarification_result`` and ``clarification_answers`` from
    state, calls the LLM via the ``clarifier_finalize`` prompt, and writes the
    ``ClarificationFinalizeResult`` plus ``final_question`` back into state.

    Falls back to the original (normalized) question when the LLM fails.
    """
    session_id = state.session_id
    clarification_result = state.clarification_result
    clarification_answers = state.clarification_answers or {}

    if clarification_result is None:
        logger.error(
            "[clarifier_finalize] clarification_result is None in state for session=%s; "
            "cannot finalize without Phase 1 output.",
            session_id,
        )
        return state.model_copy(
            update={
                "finalize_result": _FALLBACK_FINALIZE_RESULT,
                "final_question": _FALLBACK_FINALIZE_RESULT.reframed_question,
            }
        )

    original_question = clarification_result.normalized_question or clarification_result.original_question
    intent_tag = clarification_result.intent_tag

    logger.info(
        "[clarifier_finalize] session=%s intent=%s answers=%d",
        session_id,
        intent_tag,
        len(clarification_answers),
    )

    try:
        prompt_template = load_prompt("clarifier_finalize")

        answers_json = json.dumps(clarification_answers, ensure_ascii=False)
        prompt = (
            prompt_template
            .replace('"{original_question}"', json.dumps(original_question, ensure_ascii=False))
            .replace('"{intent_tag}"', json.dumps(intent_tag, ensure_ascii=False))
            .replace("{clarification_answers}", answers_json)
        )

        raw_response = await _run_with_retry(prompt)
        json_str = _extract_json(raw_response)
        parsed = json.loads(json_str)

        finalize_result = schemas.ClarificationFinalizeResult.model_validate(parsed)

        logger.info(
            "[clarifier_finalize] success reframed=%r", finalize_result.reframed_question[:60]
        )

    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("[clarifier_finalize] Parse/validation error, falling back: %s", exc)
        finalize_result = _build_fallback_finalize_result(original_question)

    except Exception as exc:  # noqa: BLE001
        logger.error("[clarifier_finalize] LLM call failed after retries, falling back: %s", exc)
        finalize_result = _build_fallback_finalize_result(original_question)

    return state.model_copy(
        update={
            "finalize_result": finalize_result,
            "final_question": finalize_result.reframed_question,
        }
    )


def _build_fallback_finalize_result(original_question: str) -> schemas.ClarificationFinalizeResult:
    """Return a graceful fallback when Phase 2 LLM call cannot be completed."""
    if original_question.strip():
        return schemas.ClarificationFinalizeResult(
            reframed_question=original_question,
            topic="用户探索议题",
            time_horizon="未指定",
            intent="寻求对当下状态的内在洞察",
            constraints=[],
        )
    return _FALLBACK_FINALIZE_RESULT
