"""Pre-input security node used by the LangGraph workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Protocol

from agent.nodes.safety_guard import build_safe_fallback_response
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


class PreInputSecurityAgent(Protocol):
    def check(self, payload: Any) -> Any: ...


def _run_llm_security(agent: Any, raw_question: str, locale: str) -> dict:
    """Call LLM security agent and normalise to the pipeline dict format."""
    from agent.schemas.safety import LLMInputSecurityCheckInput  # noqa: PLC0415

    result = agent.check(LLMInputSecurityCheckInput(content=raw_question, locale=locale or "zh-CN"))
    detected_risks = [result.risk_type] if result.risk_type and result.risk_type != "safe" else []
    sanitized_payload = None
    if result.action == "rewrite" and result.sanitized_content:
        sanitized_payload = {
            "sanitized_user_query": result.sanitized_content,
            "removed_segments": [],
            "preserved_intent": None,
        }
    return {
        "status": result.action,
        "security_decision": {
            "risk_level": result.risk_level,
            "required_action": result.action.upper(),
            "detected_risks": detected_risks,
        },
        "sanitized_payload": sanitized_payload,
        "final_response": None,
        "fallback_type": None,
    }


def execute_pre_input_security_step(
    *,
    state: TarotWorkflowState,
    observer: WorkflowObserver,
    trace_event_factory: TraceEventFactory,
    trace_logger: TraceLogger,
    protective_fallback_factory,
    trace_reading_id: str | None = None,
    pre_input_security_agent: Any | None = None,
) -> TarotWorkflowState:
    reading_id = trace_reading_id or state.reading_id

    with observer.observe_step(
        step_name="pre_input_security",
        as_type="chain",
        input_payload={"raw_question": state.raw_question},
        metadata={"session_id": state.session_id, "reading_id": reading_id},
    ) as observation:
        started = perf_counter()

        if pre_input_security_agent is not None:
            try:
                security_result = _run_llm_security(
                    pre_input_security_agent, state.raw_question, state.locale or "zh-CN"
                )
            except Exception:
                from agent.workflows.security_orchestrator import run_pre_input_security_pipeline  # noqa: PLC0415

                security_result = run_pre_input_security_pipeline(state.raw_question)
        else:
            from agent.workflows.security_orchestrator import run_pre_input_security_pipeline  # noqa: PLC0415

            security_result = run_pre_input_security_pipeline(state.raw_question)
        decision = security_result["security_decision"]
        state.input_safety_status = security_result["status"]
        state.input_required_action = decision["required_action"]
        state.input_risk_level = decision["risk_level"]
        state.input_detected_risks = list(decision["detected_risks"])

        if security_result["status"] == "continue":
            state.effective_question = state.raw_question
            state.input_sanitized = False
            state.trace_events.append(
                trace_event_factory(
                    step_name="pre_input_security",
                    event_status=TraceEventStatus.SUCCEEDED,
                    attempt_no=1,
                    started=started,
                    payload={
                        "status": "continue",
                        "risk_level": decision["risk_level"],
                        "required_action": decision["required_action"],
                    },
                )
            )
            observation.success(
                output={
                    "status": "continue",
                    "risk_level": decision["risk_level"],
                }
            )
            trace_logger(state=state, reading_id=trace_reading_id, only_latest=True)
            return state

        if security_result["status"] == "rewrite":
            sanitized_payload = security_result["sanitized_payload"] or {}
            sanitized_question = sanitized_payload.get("sanitized_user_query") or state.raw_question
            state.effective_question = sanitized_question
            state.input_sanitized = True
            state.input_removed_segments = list(sanitized_payload.get("removed_segments") or [])
            state.input_preserved_intent = sanitized_payload.get("preserved_intent")
            state.trace_events.append(
                trace_event_factory(
                    step_name="pre_input_security",
                    event_status=TraceEventStatus.FALLBACK,
                    attempt_no=1,
                    started=started,
                    error_code="INPUT_SANITIZED",
                    payload={
                        "status": "rewrite",
                        "risk_level": decision["risk_level"],
                        "required_action": decision["required_action"],
                        "removed_segment_count": len(state.input_removed_segments),
                    },
                )
            )
            observation.failure(
                error_code="INPUT_SANITIZED",
                message="Input was sanitized before entering the workflow.",
                metadata={
                    "risk_level": decision["risk_level"],
                    "removed_segment_count": len(state.input_removed_segments),
                },
            )
            trace_logger(state=state, reading_id=trace_reading_id, only_latest=True)
            return state

        fallback = build_safe_fallback_response()
        final_response = security_result.get("final_response") or fallback.message
        state.effective_question = None
        state.status = WorkflowStatus.SAFE_FALLBACK_RETURNED
        state.completed_at = datetime.now(UTC)
        state.safety_output = protective_fallback_factory(
            review_notes=f"Input blocked by pre-input security: {final_response}"
        )
        state.trace_events.append(
            trace_event_factory(
                step_name="pre_input_security",
                event_status=TraceEventStatus.FALLBACK,
                attempt_no=1,
                started=started,
                error_code="INPUT_BLOCKED",
                payload={
                    "status": "block",
                    "risk_level": decision["risk_level"],
                    "required_action": decision["required_action"],
                    "fallback_type": security_result.get("fallback_type"),
                },
            )
        )
        observation.failure(
            error_code="INPUT_BLOCKED",
            message="Input was blocked before entering the clarifier.",
            metadata={
                "risk_level": decision["risk_level"],
                "fallback_type": security_result.get("fallback_type"),
            },
        )
        trace_logger(state=state, reading_id=trace_reading_id, only_latest=True)
        return state
