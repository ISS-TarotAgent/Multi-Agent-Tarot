from __future__ import annotations

from datetime import UTC, datetime
from collections.abc import Callable
from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from agent.agents.clarifier import ClarifierAgent
from agent.agents.draw_interpreter import DrawInterpreterAgent
from agent.agents.safety_guard import SafetyGuardAgent
from agent.agents.synthesis import SynthesisAgent
from agent.workflows.tarot_reflection_runner import TarotWorkflowRunner, _TRACE_READING_ID_KEY
from app.domain.enums import SafetyAction, SpreadType, TraceEventStatus, WorkflowStatus
from app.infrastructure.observability import NoOpWorkflowObserver
from app.schemas.workflow.tarot_workflow_state import TarotWorkflowState

class WorkflowGraphState(TypedDict):
    workflow_state: TarotWorkflowState

PersistenceHandler = Callable[[TarotWorkflowState], None]

class TarotReflectionWorkflow:
    """Runs the tarot workflow through LangGraph while preserving existing contracts."""

    def __init__(
        self,
        clarifier_agent: ClarifierAgent | None = None,
        draw_agent: DrawInterpreterAgent | None = None,
        synthesis_agent: SynthesisAgent | None = None,
        safety_guard_agent: SafetyGuardAgent | None = None,
        observer: NoOpWorkflowObserver | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
    ) -> None:
        clarifier = clarifier_agent or ClarifierAgent()
        draw = draw_agent or DrawInterpreterAgent()
        synthesis = synthesis_agent or SynthesisAgent()
        safety_guard = safety_guard_agent or SafetyGuardAgent()
        observer_instance = observer or NoOpWorkflowObserver()
        self._runner = TarotWorkflowRunner(
            clarifier_agent=clarifier,
            draw_agent=draw,
            synthesis_agent=synthesis,
            safety_guard_agent=safety_guard,
            observer=observer_instance,
        )
        self._observer = observer_instance
        self._checkpointer = checkpointer
        self._active_persistence_handler: PersistenceHandler | None = None
        self._question_graph = self._compile_question_graph()
        self._execution_graph = self._compile_execution_graph()

    def evaluate_question(
        self,
        *,
        session_id: str,
        reading_id: str,
        raw_question: str,
        locale: str,
        spread_type: SpreadType,
        client_request_id: str | None = None,
        metadata: dict[str, object] | None = None,
        include_bootstrap_trace: bool = False,
        trace_reading_id: str | None = None,
        persistence_handler: PersistenceHandler | None = None,
    ) -> TarotWorkflowState:
        state = self._bootstrap_state(
            session_id=session_id,
            reading_id=reading_id,
            raw_question=raw_question,
            locale=locale,
            spread_type=spread_type,
            client_request_id=client_request_id,
            metadata=metadata,
            include_bootstrap_trace=include_bootstrap_trace,
            trace_reading_id=trace_reading_id,
        )
        return self._invoke_graph(
            self._question_graph,
            state,
            phase="question",
            persistence_handler=persistence_handler,
        )

    def run(
        self,
        *,
        session_id: str,
        reading_id: str,
        raw_question: str,
        locale: str,
        spread_type: SpreadType,
        client_request_id: str | None = None,
        metadata: dict[str, object] | None = None,
        persistence_handler: PersistenceHandler | None = None,
    ) -> TarotWorkflowState:
        state = self.evaluate_question(
            session_id=session_id,
            reading_id=reading_id,
            raw_question=raw_question,
            locale=locale,
            spread_type=spread_type,
            client_request_id=client_request_id,
            metadata=metadata,
            include_bootstrap_trace=True,
            trace_reading_id=reading_id,
        )
        return self.continue_from_ready_state(state, persistence_handler=persistence_handler)

    def continue_from_ready_state(
        self,
        state: TarotWorkflowState,
        persistence_handler: PersistenceHandler | None = None,
    ) -> TarotWorkflowState:
        state.status = WorkflowStatus.READY_FOR_DRAW
        if state.normalized_question is None:
            state.normalized_question = state.raw_question
        return self._invoke_graph(
            self._execution_graph,
            state,
            phase="execution",
            persistence_handler=persistence_handler,
        )

    def _compile_question_graph(self):
        builder = StateGraph(WorkflowGraphState)
        builder.add_node("clarifier", self._clarifier_node)
        builder.add_node("persistence", self._persistence_node)
        builder.add_edge(START, "clarifier")
        builder.add_conditional_edges("clarifier", self._route_after_clarifier, self._question_routes())
        builder.add_edge("persistence", END)
        return self._compile(builder)

    def _compile_execution_graph(self):
        builder = StateGraph(WorkflowGraphState)
        builder.add_node("draw_interpreter", self._draw_interpreter_node)
        builder.add_node("synthesis", self._synthesis_node)
        builder.add_node("safety_guard", self._safety_guard_node)
        builder.add_node("persistence", self._persistence_node)
        builder.add_edge(START, "draw_interpreter")
        builder.add_conditional_edges("draw_interpreter", self._route_after_draw, self._draw_routes())
        builder.add_conditional_edges("synthesis", self._route_after_synthesis, self._synthesis_routes())
        builder.add_edge("safety_guard", "persistence")
        builder.add_edge("persistence", END)
        return self._compile(builder)

    def _compile(self, builder: StateGraph):
        return builder.compile() if self._checkpointer is None else builder.compile(checkpointer=self._checkpointer)

    def _invoke_graph(
        self,
        graph,
        state: TarotWorkflowState,
        *,
        phase: str,
        persistence_handler: PersistenceHandler | None,
    ) -> TarotWorkflowState:
        previous_handler = self._active_persistence_handler
        self._active_persistence_handler = persistence_handler
        try:
            payload = {"workflow_state": state}
            config = self._graph_config(state, phase=phase)
            result = graph.invoke(payload, config) if config is not None else graph.invoke(payload)
            return result["workflow_state"]
        finally:
            self._active_persistence_handler = previous_handler

    def _graph_config(self, state: TarotWorkflowState, *, phase: str) -> dict[str, object] | None:
        if self._checkpointer is None:
            return None
        return {"configurable": {"thread_id": f"{phase}:{state.session_id}:{state.reading_id}"}}

    def _bootstrap_state(
        self,
        *,
        session_id: str,
        reading_id: str,
        raw_question: str,
        locale: str,
        spread_type: SpreadType,
        client_request_id: str | None,
        metadata: dict[str, object] | None,
        include_bootstrap_trace: bool,
        trace_reading_id: str | None,
    ) -> TarotWorkflowState:
        state_metadata = dict(metadata or {})
        state_metadata[_TRACE_READING_ID_KEY] = trace_reading_id
        state = TarotWorkflowState(
            session_id=session_id,
            reading_id=reading_id,
            status=WorkflowStatus.QUESTION_RECEIVED,
            locale=locale,
            spread_type=spread_type,
            raw_question=raw_question,
            client_request_id=client_request_id,
            metadata=state_metadata,
            created_at=datetime.now(UTC),
        )
        if include_bootstrap_trace:
            self._runner.append_trace(state, step_name="session_bootstrap", event_status=TraceEventStatus.SUCCEEDED, attempt_no=1, payload={"locale": locale, "spread_type": spread_type.value})
        return state

    def _clarifier_node(self, graph_state: WorkflowGraphState) -> WorkflowGraphState:
        state = graph_state["workflow_state"]
        clarifier_output = self._runner.run_clarifier(state)
        state.clarification_output = clarifier_output
        state.normalized_question = clarifier_output.normalized_question
        state.status = (
            WorkflowStatus.CLARIFYING if clarifier_output.clarification_required else WorkflowStatus.READY_FOR_DRAW
        )
        return {"workflow_state": state}

    def _draw_interpreter_node(self, graph_state: WorkflowGraphState) -> WorkflowGraphState:
        state = graph_state["workflow_state"]
        draw_output = self._runner.run_draw(state)
        if draw_output is None:
            return {"workflow_state": self._runner.finalize_fallback_state(state, "Draw agent failed after retry.")}
        state.draw_output = draw_output
        state.cards = draw_output.cards
        state.status = WorkflowStatus.DRAW_COMPLETED
        return {"workflow_state": state}

    def _synthesis_node(self, graph_state: WorkflowGraphState) -> WorkflowGraphState:
        state = graph_state["workflow_state"]
        synthesis_output = self._runner.run_synthesis(state)
        if synthesis_output is None:
            return {"workflow_state": self._runner.finalize_fallback_state(state, "Synthesis agent failed after retry.")}
        state.synthesis_output = synthesis_output
        state.status = WorkflowStatus.SYNTHESIS_COMPLETED
        return {"workflow_state": state}

    def _safety_guard_node(self, graph_state: WorkflowGraphState) -> WorkflowGraphState:
        state = graph_state["workflow_state"]
        if state.synthesis_output is None:
            return {"workflow_state": self._runner.finalize_fallback_state(state, "Missing synthesis output.")}
        state.safety_output = self._runner.run_safety_guard(state, state.synthesis_output)
        state.status = (
            WorkflowStatus.SAFE_FALLBACK_RETURNED
            if state.safety_output.action_taken is SafetyAction.BLOCK_AND_FALLBACK
            else WorkflowStatus.COMPLETED
        )
        state.completed_at = datetime.now(UTC)
        return {"workflow_state": state}

    def _persistence_node(self, graph_state: WorkflowGraphState) -> WorkflowGraphState:
        state = graph_state["workflow_state"]
        if self._active_persistence_handler is None:
            return {"workflow_state": state}
        with self._observer.observe_step(step_name="persistence", as_type="tool", input_payload={"workflow_status": state.status.value}) as persistence_step:
            self._active_persistence_handler(state)
            persistence_step.success(output={"status": state.status.value, "trace_event_count": len(state.trace_events)})
        return {"workflow_state": state}

    @staticmethod
    def _route_after_clarifier(graph_state: WorkflowGraphState) -> Literal["continue_clarify", "continue_execute"]:
        return "continue_clarify" if graph_state["workflow_state"].status is WorkflowStatus.CLARIFYING else "continue_execute"

    @staticmethod
    def _route_after_draw(graph_state: WorkflowGraphState) -> Literal["continue_execute", "fallback"]:
        return "fallback" if graph_state["workflow_state"].status is WorkflowStatus.SAFE_FALLBACK_RETURNED else "continue_execute"

    @staticmethod
    def _route_after_synthesis(graph_state: WorkflowGraphState) -> Literal["continue_execute", "fallback"]:
        return "fallback" if graph_state["workflow_state"].status is WorkflowStatus.SAFE_FALLBACK_RETURNED else "continue_execute"

    @staticmethod
    def _question_routes() -> dict[str, str]:
        return {"continue_clarify": "persistence", "continue_execute": "persistence"}

    @staticmethod
    def _draw_routes() -> dict[str, str]:
        return {"continue_execute": "synthesis", "fallback": "persistence"}

    @staticmethod
    def _synthesis_routes() -> dict[str, str]:
        return {"continue_execute": "safety_guard", "fallback": "persistence"}
