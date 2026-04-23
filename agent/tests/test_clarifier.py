"""Unit tests for Clarifier Agent nodes (Phase 1 & Phase 2).

All tests mock ModelGateway.run() -- no real LLM calls are made.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent.core import schemas
from agent.core.model_gateway import ModelGateway
from agent.nodes import clarifier

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_VALID_INIT_RESPONSE = json.dumps(
    {
        "intent_tag": "career",
        "normalized_question": "我在职场中遇到了困难，应该如何应对？",
        "clarification_prompts": [
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
    },
    ensure_ascii=False,
)

_VALID_FINALIZE_RESPONSE = json.dumps(
    {
        "reframed_question": "在职业发展的十字路口，我如何找到与内心价值对齐的方向？",
        "topic": "职业发展与决策",
        "time_horizon": "未来三个月",
        "intent": "寻求职业发展方向的内在洞察",
        "constraints": ["关注实际行动步骤"],
    },
    ensure_ascii=False,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gateway(return_value: str | None = None, side_effect: Any = None) -> ModelGateway:
    gw = MagicMock(spec=ModelGateway)
    if side_effect is not None:
        gw.run.side_effect = side_effect
    else:
        gw.run.return_value = return_value
    return gw


def _make_state(
    session_id: str = "test-session",
    raw_question: str = "我最近工作不顺，该怎么办？",
    clarification_result: schemas.ClarificationResult | None = None,
    clarification_answers: dict[str, str] | None = None,
) -> schemas.OrchestratorState:
    return schemas.OrchestratorState(
        session_id=session_id,
        raw_question=raw_question,
        clarification_result=clarification_result,
        clarification_answers=clarification_answers or {},
    )


def _make_clarification_result(
    intent_tag: schemas.IntentTag = "career",
    original_question: str = "我最近工作不顺，该怎么办？",
    normalized_question: str = "我在职场中遇到了困难，应该如何应对？",
) -> schemas.ClarificationResult:
    return schemas.ClarificationResult(
        session_id="test-session",
        original_question=original_question,
        normalized_question=normalized_question,
        intent_tag=intent_tag,
        clarification_prompts=[
            schemas.ClarificationPrompt(
                id="q1",
                question="主要挑战是什么？",
                helper_text="帮助文字",
                placeholder="示例",
            )
        ],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_gateway():
    """Reset the module-level gateway singleton before each test."""
    clarifier.set_gateway(None)  # type: ignore[arg-type]
    yield
    clarifier.set_gateway(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Phase 1 tests: clarifier_init_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clarifier_init_normal():
    """Valid LLM response produces a well-formed ClarificationResult."""
    clarifier.set_gateway(_make_gateway(return_value=_VALID_INIT_RESPONSE))
    state = _make_state()

    with patch("asyncio.sleep"):
        result_state = await clarifier.clarifier_init_node(state)

    result = result_state.clarification_result
    assert result is not None
    assert result.intent_tag == "career"
    assert result.session_id == "test-session"
    assert result.original_question == "我最近工作不顺，该怎么办？"
    assert result.normalized_question == "我在职场中遇到了困难，应该如何应对？"
    assert len(result.clarification_prompts) == 2
    assert result.clarification_prompts[0].id == "q1"


@pytest.mark.asyncio
async def test_clarifier_init_bad_json():
    """Malformed LLM response falls back to default prompts with intent 'growth'."""
    clarifier.set_gateway(_make_gateway(return_value="this is not json at all!"))
    state = _make_state()

    with patch("asyncio.sleep"):
        result_state = await clarifier.clarifier_init_node(state)

    result = result_state.clarification_result
    assert result is not None
    assert result.intent_tag == "growth"
    assert len(result.clarification_prompts) >= 1
    assert result.original_question == state.raw_question


@pytest.mark.asyncio
async def test_clarifier_init_invalid_intent_tag_defaults_to_growth():
    """LLM returns an unrecognised intent_tag; node silently coerces it to 'growth'."""
    response = json.dumps(
        {
            "intent_tag": "unknown_category",
            "normalized_question": "some question",
            "clarification_prompts": [
                {
                    "id": "q1",
                    "question": "test?",
                    "helper_text": "help",
                    "placeholder": "ph",
                }
            ],
        }
    )
    clarifier.set_gateway(_make_gateway(return_value=response))
    state = _make_state()

    with patch("asyncio.sleep"):
        result_state = await clarifier.clarifier_init_node(state)

    result = result_state.clarification_result
    assert result is not None
    assert result.intent_tag == "growth"


@pytest.mark.asyncio
async def test_clarifier_init_gateway_failure_retries_then_falls_back():
    """Gateway always raises; node retries 3 times then falls back to defaults."""
    gw = _make_gateway(side_effect=RuntimeError("LLM service unavailable"))
    clarifier.set_gateway(gw)
    state = _make_state()

    with patch("asyncio.sleep") as mock_sleep:
        result_state = await clarifier.clarifier_init_node(state)

    assert gw.run.call_count == 3
    assert mock_sleep.call_count == 2  # sleep between attempts, not after the last

    result = result_state.clarification_result
    assert result is not None
    assert result.intent_tag == "growth"
    assert len(result.clarification_prompts) >= 1


@pytest.mark.asyncio
async def test_clarifier_init_prompts_capped_at_three():
    """LLM returning more than 3 prompts: only the first 3 are kept."""
    many_prompts = [
        {"id": f"q{i}", "question": f"question {i}", "helper_text": "h", "placeholder": "p"} for i in range(1, 6)
    ]
    response = json.dumps(
        {
            "intent_tag": "study",
            "normalized_question": "学习问题",
            "clarification_prompts": many_prompts,
        }
    )
    clarifier.set_gateway(_make_gateway(return_value=response))
    state = _make_state(raw_question="我学习效率很低怎么办？")

    with patch("asyncio.sleep"):
        result_state = await clarifier.clarifier_init_node(state)

    result = result_state.clarification_result
    assert result is not None
    assert len(result.clarification_prompts) == 3


@pytest.mark.asyncio
async def test_clarifier_init_markdown_wrapped_json():
    """LLM wraps JSON in markdown fences; node should strip them and parse correctly."""
    wrapped = f"```json\n{_VALID_INIT_RESPONSE}\n```"
    clarifier.set_gateway(_make_gateway(return_value=wrapped))
    state = _make_state()

    with patch("asyncio.sleep"):
        result_state = await clarifier.clarifier_init_node(state)

    result = result_state.clarification_result
    assert result is not None
    assert result.intent_tag == "career"


# ---------------------------------------------------------------------------
# Phase 2 tests: clarifier_finalize_node
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clarifier_finalize_normal():
    """Valid LLM response produces a well-formed ClarificationFinalizeResult."""
    clarifier.set_gateway(_make_gateway(return_value=_VALID_FINALIZE_RESPONSE))
    state = _make_state(
        clarification_result=_make_clarification_result(),
        clarification_answers={"q1": "我最近被同事排挤，感到很委屈"},
    )

    with patch("asyncio.sleep"):
        result_state = await clarifier.clarifier_finalize_node(state)

    assert result_state.finalize_result is not None
    assert result_state.final_question == "在职业发展的十字路口，我如何找到与内心价值对齐的方向？"
    assert result_state.finalize_result.topic == "职业发展与决策"
    assert result_state.finalize_result.time_horizon == "未来三个月"
    assert len(result_state.finalize_result.constraints) == 1


@pytest.mark.asyncio
async def test_clarifier_finalize_empty_answers():
    """Empty clarification_answers: LLM still runs and a result is stored."""
    clarifier.set_gateway(_make_gateway(return_value=_VALID_FINALIZE_RESPONSE))
    state = _make_state(
        clarification_result=_make_clarification_result(intent_tag="relationship"),
        clarification_answers={},
    )

    with patch("asyncio.sleep"):
        result_state = await clarifier.clarifier_finalize_node(state)

    assert result_state.finalize_result is not None
    assert result_state.final_question != ""


@pytest.mark.asyncio
async def test_clarifier_finalize_no_clarification_result():
    """When Phase 1 result is absent, Phase 2 uses global fallback without calling LLM."""
    gw = _make_gateway(return_value=_VALID_FINALIZE_RESPONSE)
    clarifier.set_gateway(gw)
    state = _make_state(clarification_result=None)

    with patch("asyncio.sleep"):
        result_state = await clarifier.clarifier_finalize_node(state)

    gw.run.assert_not_called()
    assert result_state.finalize_result is not None
    assert result_state.final_question != ""


@pytest.mark.asyncio
async def test_clarifier_finalize_bad_json():
    """Malformed LLM response in Phase 2: falls back to the normalized question."""
    clarifier.set_gateway(_make_gateway(return_value="not valid json"))
    state = _make_state(
        clarification_result=_make_clarification_result(normalized_question="我面临选择时应如何决策？"),
        clarification_answers={"q1": "关于职业选择"},
    )

    with patch("asyncio.sleep"):
        result_state = await clarifier.clarifier_finalize_node(state)

    assert result_state.finalize_result is not None
    assert result_state.final_question == "我面临选择时应如何决策？"


@pytest.mark.asyncio
async def test_clarifier_finalize_gateway_failure_retries_then_falls_back():
    """Gateway always raises during Phase 2; retries 3 times then falls back."""
    gw = _make_gateway(side_effect=ConnectionError("API unreachable"))
    clarifier.set_gateway(gw)
    state = _make_state(
        clarification_result=_make_clarification_result(normalized_question="我如何在个人成长中取得进步？"),
        clarification_answers={"q1": "我想提升领导力"},
    )

    with patch("asyncio.sleep") as mock_sleep:
        result_state = await clarifier.clarifier_finalize_node(state)

    assert gw.run.call_count == 3
    assert mock_sleep.call_count == 2
    assert result_state.finalize_result is not None
    assert result_state.final_question == "我如何在个人成长中取得进步？"


# ---------------------------------------------------------------------------
# Schema / intent_tag validation tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("intent_tag", ["career", "relationship", "study", "emotion", "growth"])
def test_intent_tag_all_valid_values_accepted(intent_tag: str):
    """Every legal IntentTag value is accepted by ClarificationResult."""
    result = schemas.ClarificationResult(
        session_id="s1",
        original_question="q",
        normalized_question="q",
        intent_tag=intent_tag,  # type: ignore[arg-type]
        clarification_prompts=[],
    )
    assert result.intent_tag == intent_tag


def test_intent_tag_invalid_value_raises():
    """An unrecognised intent_tag raises Pydantic ValidationError at the schema level."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        schemas.ClarificationResult(
            session_id="s1",
            original_question="q",
            normalized_question="q",
            intent_tag="invalid",  # type: ignore[arg-type]
            clarification_prompts=[],
        )
