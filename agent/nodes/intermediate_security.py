"""Intermediate security node for agent-to-agent content transfer."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Protocol

from agent.nodes.safety_guard import build_safe_fallback_response
from agent.schemas.safety import SafetyReviewOutput
from backend.app.domain.enums import TraceEventStatus, WorkflowStatus
from backend.app.schemas.workflow import TarotWorkflowState, TraceEventPayload


class TraceEventFactory(Protocol):
    def __call__(
        self,
        *,
        step_name: str,
        event_status: TraceEventStatus,
        attempt_no: int,
        payload: dict[str, Any],
        started: float | None,
        error_code: str | None = None,
    ) -> TraceEventPayload: ...


class TraceLogger(Protocol):
    def __call__(
        self,
        *,
        state: TarotWorkflowState,
        reading_id: str | None,
        only_latest: bool = False,
    ) -> None: ...


class ObservationHandle(Protocol):
    def success(
        self,
        *,
        output: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None: ...

    def failure(
        self,
        *,
        error_code: str | None,
        message: str,
        metadata: dict[str, object] | None = None,
    ) -> None: ...


class WorkflowObserver(Protocol):
    def observe_step(
        self,
        *,
        step_name: str,
        as_type: str,
        input_payload: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ): ...


class ProtectiveFallbackFactory(Protocol):
    def __call__(self, *, review_notes: str) -> SafetyReviewOutput: ...


def _run_rule_based_intermediate(joined_content: str) -> tuple[bool, dict]:
    """Fallback rule-based check using pre-input guard on agent content."""
    from agent.core.schemas import ContentSource  # noqa: PLC0415
    from agent.core.trust import tag_content  # noqa: PLC0415
    from agent.security.pre_input_guard import inspect_user_input  # noqa: PLC0415

    tagged = tag_content(joined_content, source=ContentSource.AGENT, metadata={"stage": "draw_to_synthesis"})
    decision = inspect_user_input(tagged)
    payload = {
        "risk_level": decision.risk_level.value,
        "required_action": decision.required_action.value,
        "detected_risks": decision.detected_risks,
    }
    return decision.allow_continue, payload


def execute_intermediate_security_step(
    *,
    state: TarotWorkflowState,
    observer: WorkflowObserver,
    trace_event_factory: TraceEventFactory,
    trace_logger: TraceLogger,
    protective_fallback_factory: ProtectiveFallbackFactory,
    intermediate_security_agent: Any | None = None,
) -> TarotWorkflowState:
    card_interpretations = [card.interpretation for card in state.cards if card.interpretation]
    joined_content = "\n".join(card_interpretations)

    with observer.observe_step(
        step_name="intermediate_security",
        as_type="chain",
        input_payload={"card_count": len(state.cards)},
        metadata={"session_id": state.session_id, "reading_id": state.reading_id},
    ) as observation:
        started = perf_counter()

        if intermediate_security_agent is not None:
            try:
                from agent.schemas.safety import LLMInputSecurityCheckInput  # noqa: PLC0415

                llm_result = intermediate_security_agent.check(
                    LLMInputSecurityCheckInput(
                        content=joined_content,
                        locale=state.locale or "zh-CN",
                    ),
                    card_interpretations=card_interpretations,
                    question=state.raw_question or "",
                )
                allow_continue = llm_result.action == "continue"
                detected_risks = (
                    [llm_result.risk_type] if llm_result.risk_type and llm_result.risk_type != "safe" else []
                )
                payload = {
                    "risk_level": llm_result.risk_level,
                    "required_action": llm_result.action.upper(),
                    "detected_risks": detected_risks,
                    "method": "llm",
                }
                fallback_type = f"llm_{llm_result.risk_type}"
            except Exception:
                allow_continue, payload = _run_rule_based_intermediate(joined_content)
                fallback_type = "rule_fallback"
                payload["method"] = "rules"
        else:
            allow_continue, payload = _run_rule_based_intermediate(joined_content)
            fallback_type = "rules"
            payload["method"] = "rules"

        if allow_continue:
            state.trace_events.append(
                trace_event_factory(
                    step_name="intermediate_security",
                    event_status=TraceEventStatus.SUCCEEDED,
                    attempt_no=1,
                    started=started,
                    payload=payload,
                )
            )
            observation.success(output=payload)
            trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
            return state

        state.trace_events.append(
            trace_event_factory(
                step_name="intermediate_security",
                event_status=TraceEventStatus.FALLBACK,
                attempt_no=1,
                started=started,
                error_code="INTERMEDIATE_CONTENT_BLOCKED",
                payload={**payload, "fallback_type": fallback_type},
            )
        )
        state.status = WorkflowStatus.SAFE_FALLBACK_RETURNED
        state.completed_at = datetime.now(UTC)
        state.safety_output = protective_fallback_factory(
            review_notes=f"Intermediate content safety check blocked handoff from draw to synthesis: {fallback_type}"
        )
        observation.failure(
            error_code="INTERMEDIATE_CONTENT_BLOCKED",
            message="Intermediate agent content was blocked before synthesis.",
            metadata={**payload, "fallback_type": fallback_type},
        )
        trace_logger(state=state, reading_id=state.reading_id, only_latest=True)
        return state
