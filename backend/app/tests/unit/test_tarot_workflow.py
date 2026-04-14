from __future__ import annotations

from agent.workflows import TarotReflectionWorkflow
from app.schemas.workflow.tarot_workflow_state import TarotWorkflowState
from app.domain.enums import SafetyAction, SpreadType, TraceEventStatus, WorkflowStatus
from langgraph.checkpoint.memory import InMemorySaver


class BrokenDrawAgent:
    def run(self, payload):  # noqa: ANN001
        raise ValueError("draw output is invalid")


class RecordingPersistenceHandler:
    def __init__(self) -> None:
        self.calls: list[tuple[WorkflowStatus, int]] = []

    def __call__(self, state: TarotWorkflowState) -> None:
        self.calls.append((state.status, len(state.trace_events)))


def test_workflow_returns_safe_fallback_when_draw_keeps_failing() -> None:
    workflow = TarotReflectionWorkflow(draw_agent=BrokenDrawAgent())

    state = workflow.run(
        session_id="7b3273ef-260d-49eb-b1af-f1c1b862d420",
        reading_id="2fcb387d-b34e-4c61-beb1-88d67f1d9744",
        raw_question="我应该如何处理当前的工作压力？",
        locale="zh-CN",
        spread_type=SpreadType.THREE_CARD_REFLECTION,
    )

    assert state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED
    assert state.safety_output is not None
    assert state.safety_output.action_taken is SafetyAction.BLOCK_AND_FALLBACK
    failed_events = [event for event in state.trace_events if event.event_status is TraceEventStatus.FAILED]
    assert len(failed_events) == 2
    assert all(event.error_code == "SCHEMA_VALIDATION_FAILED" for event in failed_events)
    assert any(
        event.step_name == "draw_interpreter" and event.event_status is TraceEventStatus.FALLBACK
        for event in state.trace_events
    )
    assert any(
        event.step_name == "draw_interpreter" and event.error_code == "STEP_FALLBACK_TRIGGERED"
        for event in state.trace_events
    )


def test_evaluate_question_stops_on_clarifying_branch_and_only_records_clarifier_trace() -> None:
    workflow = TarotReflectionWorkflow()

    state = workflow.evaluate_question(
        session_id="7b3273ef-260d-49eb-b1af-f1c1b862d420",
        reading_id="2fcb387d-b34e-4c61-beb1-88d67f1d9744",
        raw_question="我该怎么办？",
        locale="zh-CN",
        spread_type=SpreadType.THREE_CARD_REFLECTION,
    )

    assert state.status is WorkflowStatus.CLARIFYING
    assert state.clarification_output is not None
    assert state.clarification_output.clarification_required is True
    assert state.cards == []
    assert state.synthesis_output is None
    assert state.safety_output is None
    assert [(event.step_name, event.event_status) for event in state.trace_events] == [
        ("clarifier", TraceEventStatus.SUCCEEDED),
    ]


def test_continue_from_ready_state_accepts_optional_langgraph_checkpointer() -> None:
    checkpointer = InMemorySaver()
    workflow = TarotReflectionWorkflow(checkpointer=checkpointer)
    state = TarotWorkflowState(
        session_id="7b3273ef-260d-49eb-b1af-f1c1b862d420",
        reading_id="2fcb387d-b34e-4c61-beb1-88d67f1d9744",
        status=WorkflowStatus.READY_FOR_DRAW,
        locale="zh-CN",
        spread_type=SpreadType.THREE_CARD_REFLECTION,
        raw_question="最近在工作选择上很犹豫，我应该继续坚持当前方向吗？",
        normalized_question="最近在工作选择上很犹豫，我应该继续坚持当前方向吗？",
        created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    final_state = workflow.continue_from_ready_state(state)

    assert final_state.status is WorkflowStatus.COMPLETED
    assert final_state.completed_at is not None
    checkpoints = list(
        checkpointer.list(
            {"configurable": {"thread_id": f"execution:{state.session_id}:{state.reading_id}"}}
        )
    )
    assert checkpoints


def test_run_invokes_persistence_handler_from_langgraph_persistence_node() -> None:
    workflow = TarotReflectionWorkflow()
    persistence_handler = RecordingPersistenceHandler()

    state = workflow.run(
        session_id="7b3273ef-260d-49eb-b1af-f1c1b862d420",
        reading_id="2fcb387d-b34e-4c61-beb1-88d67f1d9744",
        raw_question="最近在工作选择上很犹豫，我应该继续坚持当前方向吗？",
        locale="zh-CN",
        spread_type=SpreadType.THREE_CARD_REFLECTION,
        persistence_handler=persistence_handler,
    )

    assert state.status is WorkflowStatus.COMPLETED
    assert persistence_handler.calls == [(WorkflowStatus.COMPLETED, len(state.trace_events))]
