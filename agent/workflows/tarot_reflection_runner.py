from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from agent.agents.clarifier import ClarifierAgent
from agent.agents.draw_interpreter import DrawInterpreterAgent
from agent.agents.safety_guard import SafetyGuardAgent
from agent.agents.synthesis import SynthesisAgent
from agent.schemas.clarifier import ClarifierInput, ClarifierOutput
from agent.schemas.draw import DrawInput, DrawOutput
from agent.schemas.safety import SafetyReviewInput, SafetyReviewOutput
from agent.schemas.synthesis import SynthesisInput, SynthesisOutput
from app.domain.enums import RiskLevel, SafetyAction, TraceEventStatus, WorkflowStatus
from app.infrastructure.logging.workflow_events import log_trace_event
from app.infrastructure.observability import NoOpWorkflowObserver
from app.schemas.workflow.tarot_workflow_state import TarotWorkflowState
from app.schemas.workflow.trace_event import TraceEventPayload

_TRACE_READING_ID_KEY = "__trace_reading_id__"

class TarotWorkflowRunner:
    """Executes workflow steps while preserving trace and fallback contracts."""

    def __init__(
        self,
        *,
        clarifier_agent: ClarifierAgent,
        draw_agent: DrawInterpreterAgent,
        synthesis_agent: SynthesisAgent,
        safety_guard_agent: SafetyGuardAgent,
        observer: NoOpWorkflowObserver,
    ) -> None:
        self._clarifier_agent = clarifier_agent
        self._draw_agent = draw_agent
        self._synthesis_agent = synthesis_agent
        self._safety_guard_agent = safety_guard_agent
        self._observer = observer

    def run_clarifier(self, state: TarotWorkflowState) -> ClarifierOutput:
        with self._observer.observe_step(
            step_name="clarifier",
            as_type="agent",
            input_payload={"raw_question": state.raw_question, "locale": state.locale},
            metadata={"attempt_no": 1},
        ) as observation:
            started_at = perf_counter()
            try:
                output = self._clarifier_agent.run(ClarifierInput(raw_question=state.raw_question, locale=state.locale))
            except Exception:
                latency_ms = self._duration_ms(started_at)
                fallback_output = ClarifierOutput(
                    normalized_question=state.raw_question,
                    clarification_required=False,
                    clarifier_question=None,
                    confidence=0.0,
                )
                observation.failure(
                    error_code="CLARIFIER_FALLBACK_TO_RAW",
                    message="Clarifier agent failed and fell back to the raw question.",
                    metadata={"latency_ms": latency_ms},
                )
                self.append_trace(
                    state,
                    step_name="clarifier",
                    event_status=TraceEventStatus.FALLBACK,
                    attempt_no=1,
                    latency_ms=latency_ms,
                    error_code="CLARIFIER_FALLBACK_TO_RAW",
                    payload={"clarification_required": False, "reason": "clarifier_failed"},
                )
                return fallback_output

            latency_ms = self._duration_ms(started_at)
            observation.success(
                output={"clarification_required": output.clarification_required, "confidence": output.confidence},
                metadata={"latency_ms": latency_ms},
            )
            self.append_trace(
                state,
                step_name="clarifier",
                event_status=TraceEventStatus.SUCCEEDED,
                attempt_no=1,
                latency_ms=latency_ms,
                payload={"clarification_required": output.clarification_required, "confidence": output.confidence},
            )
            return output

    def run_draw(self, state: TarotWorkflowState) -> DrawOutput | None:
        return self._run_step_with_retry(
            state=state,
            step_name="draw_interpreter",
            attempts=2,
            runner=lambda: self._draw_agent.run(
                DrawInput(
                    normalized_question=state.normalized_question or state.raw_question,
                    spread_type=state.spread_type,
                    locale=state.locale,
                )
            ),
        )

    def run_synthesis(self, state: TarotWorkflowState) -> SynthesisOutput | None:
        return self._run_step_with_retry(
            state=state,
            step_name="synthesis",
            attempts=2,
            runner=lambda: self._synthesis_agent.run(
                SynthesisInput(
                    normalized_question=state.normalized_question or state.raw_question,
                    cards=state.cards,
                )
            ),
        )

    def run_safety_guard(self, state: TarotWorkflowState, synthesis_output: SynthesisOutput) -> SafetyReviewOutput:
        self.append_trace(
            state,
            step_name="safety_guard",
            event_status=TraceEventStatus.STARTED,
            attempt_no=1,
            payload={"input_source": "synthesis_output"},
        )
        with self._observer.observe_step(
            step_name="safety_guard",
            as_type="guardrail",
            input_payload={
                "normalized_question": state.normalized_question or state.raw_question,
                "risk_source": "synthesis_output",
            },
            metadata={"attempt_no": 1},
        ) as observation:
            started_at = perf_counter()
            output = self._safety_guard_agent.run(
                SafetyReviewInput(
                    summary=synthesis_output.summary,
                    action_advice=synthesis_output.action_advice,
                    reflection_question=synthesis_output.reflection_question,
                    normalized_question=state.normalized_question or state.raw_question,
                )
            )
            latency_ms = self._duration_ms(started_at)
            observation.success(
                output={"risk_level": output.risk_level.value, "action_taken": output.action_taken.value},
                metadata={"latency_ms": latency_ms},
            )
            self.append_trace(
                state,
                step_name="safety_guard",
                event_status=TraceEventStatus.SUCCEEDED,
                attempt_no=1,
                latency_ms=latency_ms,
                payload={"risk_level": output.risk_level.value, "action_taken": output.action_taken.value},
            )
            return output

    def finalize_fallback_state(self, state: TarotWorkflowState, reason: str) -> TarotWorkflowState:
        state.safety_output = SafetyReviewOutput(
            risk_level=RiskLevel.MEDIUM,
            action_taken=SafetyAction.BLOCK_AND_FALLBACK,
            safe_summary="这次解读过程中有部分步骤未能稳定完成，因此我先返回一个更稳妥的保护性结果。",
            safe_action_advice="先把问题缩小到一个你最近最想确认的现实主题，再重新发起一次解读会更有帮助。",
            safe_reflection_question="如果只能先厘清一件事，你最希望先看清的是哪一个现实选择？",
            review_notes=reason,
        )
        state.status = WorkflowStatus.SAFE_FALLBACK_RETURNED
        state.completed_at = datetime.now(UTC)
        return state

    def append_trace(
        self,
        state: TarotWorkflowState,
        *,
        step_name: str,
        event_status: TraceEventStatus,
        attempt_no: int,
        payload: dict[str, object],
        latency_ms: int | None = None,
        error_code: str | None = None,
    ) -> None:
        event = TraceEventPayload(
            event_id=str(uuid4()),
            step_name=step_name,
            event_status=event_status,
            attempt_no=attempt_no,
            latency_ms=latency_ms,
            error_code=error_code,
            payload=payload,
            created_at=datetime.now(UTC),
        )
        state.trace_events.append(event)
        log_trace_event(session_id=state.session_id, reading_id=self._trace_reading_id(state), event=event)

    def _run_step_with_retry(
        self,
        *,
        state: TarotWorkflowState,
        step_name: str,
        attempts: int,
        runner,
    ) -> DrawOutput | SynthesisOutput | None:
        for attempt_no in range(1, attempts + 1):
            self.append_trace(
                state,
                step_name=step_name,
                event_status=TraceEventStatus.STARTED,
                attempt_no=attempt_no,
                payload={"attempt_no": attempt_no},
            )
            with self._observer.observe_step(
                step_name=step_name,
                as_type="agent",
                input_payload={"attempt_no": attempt_no},
                metadata={"attempt_no": attempt_no},
            ) as observation:
                started_at = perf_counter()
                try:
                    output = runner()
                    payload_summary = self._summarize_output(output)
                except (ValidationError, ValueError, KeyError, TypeError, AttributeError) as exc:
                    latency_ms = self._duration_ms(started_at)
                    observation.failure(
                        error_code="SCHEMA_VALIDATION_FAILED",
                        message=str(exc),
                        metadata={"latency_ms": latency_ms, "attempt_no": attempt_no},
                    )
                    self.append_trace(
                        state,
                        step_name=step_name,
                        event_status=TraceEventStatus.FAILED,
                        attempt_no=attempt_no,
                        latency_ms=latency_ms,
                        error_code="SCHEMA_VALIDATION_FAILED",
                        payload={"message": str(exc)},
                    )
                    continue
                except Exception as exc:
                    latency_ms = self._duration_ms(started_at)
                    observation.failure(
                        error_code="STEP_EXECUTION_FAILED",
                        message=str(exc),
                        metadata={"latency_ms": latency_ms, "attempt_no": attempt_no},
                    )
                    self.append_trace(
                        state,
                        step_name=step_name,
                        event_status=TraceEventStatus.FAILED,
                        attempt_no=attempt_no,
                        latency_ms=latency_ms,
                        error_code="STEP_EXECUTION_FAILED",
                        payload={"message": str(exc)},
                    )
                    continue

                latency_ms = self._duration_ms(started_at)
                observation.success(output=payload_summary, metadata={"latency_ms": latency_ms, "attempt_no": attempt_no})
                self.append_trace(
                    state,
                    step_name=step_name,
                    event_status=TraceEventStatus.SUCCEEDED,
                    attempt_no=attempt_no,
                    latency_ms=latency_ms,
                    payload=payload_summary,
                )
                return output

        self.append_trace(
            state,
            step_name=step_name,
            event_status=TraceEventStatus.FALLBACK,
            attempt_no=attempts,
            error_code="STEP_FALLBACK_TRIGGERED",
            payload={"reason": f"{step_name}_failed_after_retry"},
        )
        return None

    @staticmethod
    def _trace_reading_id(state: TarotWorkflowState) -> str | None:
        if not state.metadata:
            return state.reading_id
        return state.metadata.get(_TRACE_READING_ID_KEY, state.reading_id)

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((perf_counter() - started_at) * 1000)

    @staticmethod
    def _summarize_output(output: DrawOutput | SynthesisOutput) -> dict[str, Any]:
        if isinstance(output, DrawOutput):
            return {
                "card_codes": [card.card_code for card in output.cards],
                "positions": [card.position.value for card in output.cards],
            }
        if not isinstance(output, SynthesisOutput):
            raise ValueError("workflow step returned an unexpected output type.")
        return {"summary_length": len(output.summary), "action_advice_length": len(output.action_advice)}
