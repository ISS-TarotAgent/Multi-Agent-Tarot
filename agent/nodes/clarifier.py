"""Clarifier node implementation used by the LangGraph workflow."""

from __future__ import annotations

from time import perf_counter
from typing import Any, Protocol

from agent.schemas.clarifier import (
    ClarificationPrompt,
    ClarifierFinalizeInput,
    ClarifierFinalizeOutput,
    ClarifierInput,
    ClarifierOutput,
)
from backend.app.domain.enums import TraceEventStatus, WorkflowStatus
from backend.app.schemas.workflow import TarotWorkflowState, TraceEventPayload

# 定义了一个LLMClarifierAgent类，负责处理澄清阶段的逻辑，包括生成澄清问题和根据用户回答生成重构问题。该类使用ModelGateway与LLM进行交互，并加载相应的提示模板。
class ClarifierAgent(Protocol):
    def run(self, payload: ClarifierInput) -> ClarifierOutput: ...
    def finalize(self, payload: ClarifierFinalizeInput) -> ClarifierFinalizeOutput: ...

# 定义了几个协议类（Protocol），用于抽象化地描述观察者模式中的不同角色，包括ObservationHandle、WorkflowObserver、TraceEventFactory和TraceLogger。这些协议定义了在澄清阶段执行过程中可能涉及的观察和日志记录接口。
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


# execute_clarifier_step函数是澄清阶段的核心执行函数，负责根据当前的工作流状态和输入.
# 调用ClarifierAgent的run和finalize方法，并使用观察者和日志记录器记录整个过程中的事件和结果。
# 该函数还包含错误处理逻辑，在澄清过程中发生异常时提供回退机制，确保工作流能够继续进行。
def execute_clarifier_step(
    *,
    state: TarotWorkflowState,
    clarifier_agent: ClarifierAgent,
    observer: WorkflowObserver,
    trace_event_factory: TraceEventFactory,
    trace_logger: TraceLogger,
    trace_reading_id: str | None = None,
) -> TarotWorkflowState:
    # 从工作流状态中提取用户的有效问题文本（如果之前已经经过安全过滤和处理，则使用effective_question，否则使用raw_question），并构造ClarifierInput对象作为输入。
    question_text = state.effective_question or state.raw_question
    payload = ClarifierInput(raw_question=question_text, locale=state.locale)
    reading_id = trace_reading_id or state.reading_id

    # 判断当前是否是从澄清阶段恢复（resuming），即之前已经生成了澄清提示并等待用户回答的情况。
    # 这将影响后续的处理逻辑，决定是直接进入finalize阶段还是先执行run阶段生成澄清提示。
    is_resuming = (
        state.status is WorkflowStatus.CLARIFYING
        and bool(state.clarification_answers)
    )

    with observer.observe_step(
        step_name="clarifier",
        as_type="chain",
        input_payload={"raw_question": question_text, "resuming": is_resuming},
        metadata={"session_id": state.session_id, "reading_id": reading_id},
    ) as observation:
        started = perf_counter()
        try:
            # 如果是恢复状态，直接进入finalize阶段，使用用户提供的澄清答案生成重构问题，并更新工作流状态为READY_FOR_DRAW。
            if is_resuming:
                # Phase 2 only: Phase 1 results are already in state
                finalize_out = clarifier_agent.finalize(
                    ClarifierFinalizeInput(
                        normalized_question=state.normalized_question or question_text,
                        intent_tag=state.intent_tag or "growth",
                        locale=state.locale,
                        clarification_answers=state.clarification_answers,
                    )
                )
                state.normalized_question = finalize_out.reframed_question
                state.status = WorkflowStatus.READY_FOR_DRAW
                state.trace_events.append(
                    trace_event_factory(
                        step_name="clarifier",
                        event_status=TraceEventStatus.SUCCEEDED,
                        attempt_no=1,
                        started=started,
                        payload={
                            "phase": "finalize",
                            "intent_tag": state.intent_tag,
                            "reframed_question": finalize_out.reframed_question[:80],
                        },
                    )
                )
                observation.success(
                    output={
                        "status": state.status.value,
                        "phase": "finalize",
                        "reframed_question": finalize_out.reframed_question[:80],
                    }
                )

            # 如果不是恢复状态，先执行run阶段，生成澄清提示和意图标签，并根据是否需要澄清进入不同的处理分支。如果需要澄清，则更新状态为CLARIFYING并等待用户回答；如果不需要澄清，则直接进入finalize阶段生成重构问题。
            else:
                # Phase 1: intent classification + clarification prompts
                clarification = clarifier_agent.run(payload)
                state.clarification_output = clarification
                state.normalized_question = clarification.normalized_question
                state.intent_tag = clarification.intent_tag

                if clarification.clarification_required and not state.skip_clarification:
                    # Session API: store prompts and pause for user answers.
                    # Skipped when skip_clarification=True (frontend max-turns enforcement).
                    state.clarification_prompts = [
                        p.model_dump() for p in clarification.clarification_prompts
                    ]
                    state.status = WorkflowStatus.CLARIFYING
                    state.trace_events.append(
                        trace_event_factory(
                            step_name="clarifier",
                            event_status=TraceEventStatus.SUCCEEDED,
                            attempt_no=1,
                            started=started,
                            payload={
                                "phase": "init",
                                "intent_tag": clarification.intent_tag,
                                "prompts_count": len(clarification.clarification_prompts),
                            },
                        )
                    )
                    observation.success(
                        output={"status": state.status.value, "phase": "init"}
                    )
                else:
                    # One-shot API: chain Phase 2 immediately with empty answers
                    finalize_started = perf_counter()
                    finalize_out = clarifier_agent.finalize(
                        ClarifierFinalizeInput(
                            normalized_question=clarification.normalized_question,
                            intent_tag=clarification.intent_tag,
                            locale=state.locale,
                            clarification_answers={},
                        )
                    )
                    state.normalized_question = finalize_out.reframed_question
                    state.status = WorkflowStatus.READY_FOR_DRAW
                    state.trace_events.append(
                        trace_event_factory(
                            step_name="clarifier",
                            event_status=TraceEventStatus.SUCCEEDED,
                            attempt_no=1,
                            started=started,
                            payload={
                                "phase": "init+finalize",
                                "intent_tag": clarification.intent_tag,
                                "reframed_question": finalize_out.reframed_question[:80],
                                "finalize_latency_ms": round(
                                    (perf_counter() - finalize_started) * 1000
                                ),
                            },
                        )
                    )
                    observation.success(
                        output={
                            "status": state.status.value,
                            "phase": "init+finalize",
                            "reframed_question": finalize_out.reframed_question[:80],
                        }
                    )

        except Exception as exc:
            fallback = ClarifierOutput(
                normalized_question=question_text,
                clarification_required=False,
            )
            metadata_payload = {
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "fallback_normalized_question": question_text,
            }
            state.trace_events.append(
                trace_event_factory(
                    step_name="clarifier",
                    event_status=TraceEventStatus.FALLBACK,
                    attempt_no=1,
                    started=started,
                    error_code="CLARIFIER_FALLBACK_TO_RAW",
                    payload=metadata_payload,
                )
            )
            state.clarification_output = fallback
            state.normalized_question = question_text
            state.status = WorkflowStatus.READY_FOR_DRAW
            observation.failure(
                error_code="CLARIFIER_FALLBACK_TO_RAW",
                message="Clarifier failed; used the raw question as fallback.",
                metadata=metadata_payload,
            )

    trace_logger(state=state, reading_id=trace_reading_id, only_latest=False)
    return state
