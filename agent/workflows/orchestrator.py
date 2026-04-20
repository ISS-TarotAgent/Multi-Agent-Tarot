"""LangGraph-backed workflow assembly for the Tarot experience."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Iterator, Protocol,TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from langgraph.graph import StateGraph

_StateGraph: Any

try:
    from langgraph.graph import END, START
    from langgraph.graph import StateGraph as _StateGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover
    END = "__end__"
    START = "__start__"
    _StateGraph = None  # type: ignore[assignment]
    LANGGRAPH_AVAILABLE = False

from agent.nodes import (
    execute_clarifier_step,
    execute_draw_step,
    execute_intermediate_security_step,
    execute_pre_input_security_step,
)
from agent.schemas.clarifier import ClarifierInput, ClarifierOutput
from agent.schemas.draw import DrawCard, DrawInput, DrawOutput
from agent.schemas.safety import SafetyReviewInput, SafetyReviewOutput
from agent.schemas.synthesis import SynthesisInput, SynthesisOutput
from backend.app.domain.enums import (
    CardOrientation,
    CardPosition,
    RiskLevel,
    SafetyAction,
    SpreadType,
    TraceEventStatus,
    WorkflowStatus,
)
from backend.app.schemas.workflow import TarotWorkflowState, TraceEventPayload

logger = logging.getLogger("app.workflow")


class ClarifierAgent(Protocol):
    def run(self, payload: ClarifierInput) -> ClarifierOutput: ...


class DrawAgent(Protocol):
    def run(self, payload: DrawInput) -> DrawOutput: ...


class SynthesisAgent(Protocol):
    def run(self, payload: SynthesisInput) -> SynthesisOutput: ...


class SafetyGuardAgent(Protocol):
    def run(self, payload: SafetyReviewInput) -> SafetyReviewOutput: ...


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
    ) -> Iterator[ObservationHandle]: ...


class _NoOpObservationHandle:
    def success(
        self,
        *,
        output: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        return None

    def failure(
        self,
        *,
        error_code: str | None,
        message: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        return None


class _NoOpWorkflowObserver:
    @contextmanager
    def observe_step(
        self,
        *,
        step_name: str,
        as_type: str,
        input_payload: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Iterator[_NoOpObservationHandle]:
        yield _NoOpObservationHandle()


@dataclass(slots=True)
class _GraphRuntime:
    workflow: "TarotReflectionWorkflow"


class _DefaultClarifierAgent:
    def run(self, payload: ClarifierInput) -> ClarifierOutput:
        normalized_question = payload.raw_question.strip()
        clarification_required = _requires_clarification(normalized_question)
        clarifier_question = (
            "你最想聚焦的是感情、事业、学业还是关系？"
            if clarification_required
            else None
        )
        return ClarifierOutput(
            normalized_question=normalized_question,
            clarification_required=clarification_required,
            clarifier_question=clarifier_question,
        )


class _DefaultDrawAgent:
    _CARD_BLUEPRINTS: tuple[tuple[CardPosition, str, str, CardOrientation], ...] = (
        (CardPosition.PAST, "the-hermit", "The Hermit", CardOrientation.UPRIGHT),
        (CardPosition.PRESENT, "two-of-swords", "Two of Swords", CardOrientation.UPRIGHT),
        (CardPosition.FUTURE, "the-star", "The Star", CardOrientation.UPRIGHT),
    )

    def run(self, payload: DrawInput) -> DrawOutput:
        cards = [
            DrawCard(
                position=position,
                card_code=card_code,
                card_name=card_name,
                orientation=orientation,
                interpretation=f"{card_name} points to {self._theme_for(position, payload.question)}.",
            )
            for position, card_code, card_name, orientation in self._CARD_BLUEPRINTS
        ]
        return DrawOutput(cards=cards)

    @staticmethod
    def _theme_for(position: CardPosition, question: str) -> str:
        if position is CardPosition.PAST:
            return f"past influences still shaping the question: {question[:48]}"
        if position is CardPosition.PRESENT:
            return "a present tension that calls for patience and clearer boundaries"
        return "a future opening that becomes visible after steady reflection"


class _DefaultSynthesisAgent:
    def run(self, payload: SynthesisInput) -> SynthesisOutput:
        return SynthesisOutput(
            summary=(
                f"Your reading centers on {payload.normalized_question}. "
                "The cards suggest a gradual shift from uncertainty toward clarity."
            ),
            action_advice="Slow the decision down, note what is in your control, and act on the next small step.",
            reflection_question="What would feel like a steady, honest next step this week?",
        )


class _DefaultSafetyGuardAgent:
    def run(self, payload: SafetyReviewInput) -> SafetyReviewOutput:
        return SafetyReviewOutput(
            risk_level=RiskLevel.LOW,
            action_taken=SafetyAction.PASSTHROUGH,
            review_notes="Passed default safety review.",
            safe_summary=payload.summary,
            safe_action_advice=payload.action_advice,
            safe_reflection_question=payload.reflection_question,
        )


class TarotReflectionWorkflow:
    """High-level workflow entry point used by the backend services."""

    def __init__(
        self,
        *,
        clarifier_agent: ClarifierAgent | None = None,
        draw_agent: DrawAgent | None = None,
        synthesis_agent: SynthesisAgent | None = None,
        safety_guard_agent: SafetyGuardAgent | None = None,
        observer: WorkflowObserver | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        self._clarifier_agent = clarifier_agent or _DefaultClarifierAgent()
        self._draw_agent = draw_agent or _DefaultDrawAgent()
        self._synthesis_agent = synthesis_agent or _DefaultSynthesisAgent()
        self._safety_guard_agent = safety_guard_agent or _DefaultSafetyGuardAgent()
        self._observer = observer or _NoOpWorkflowObserver()
        self._checkpointer = checkpointer
        self._runtime = _GraphRuntime(workflow=self)
        self._question_graph = self._build_question_graph() if LANGGRAPH_AVAILABLE else None
        self._ready_state_graph = self._build_ready_state_graph() if LANGGRAPH_AVAILABLE else None

    def run(
        self,
        *,
        session_id: str,
        reading_id: str,
        raw_question: str,
        locale: str,
        spread_type: SpreadType,
        client_request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        persistence_handler: Any | None = None,
    ) -> TarotWorkflowState:
        state = self.evaluate_question(
            session_id=session_id,
            reading_id=reading_id,
            raw_question=raw_question,
            locale=locale,
            spread_type=spread_type,
            client_request_id=client_request_id,
            metadata=metadata,
        )
        if state.status is WorkflowStatus.READY_FOR_DRAW:
            state = self.continue_from_ready_state(state)
        if persistence_handler is not None:
            persistence_handler(state)
        return state

    def evaluate_question(
        self,
        *,
        session_id: str,
        reading_id: str,
        raw_question: str,
        locale: str,
        spread_type: SpreadType,
        client_request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        trace_reading_id: str | None = None,
        persistence_handler: Any | None = None,
    ) -> TarotWorkflowState:
        state = TarotWorkflowState(
            session_id=session_id,
            reading_id=reading_id,
            status=WorkflowStatus.QUESTION_RECEIVED,
            locale=locale,
            spread_type=spread_type,
            raw_question=raw_question,
            client_request_id=client_request_id,
            metadata=metadata,
            created_at=datetime.now(UTC),
        )

        if self._question_graph is None:
            state = self._run_question_without_langgraph(state, trace_reading_id=trace_reading_id)
        else:
            compiled = self._question_graph.compile()
            result = compiled.invoke(
                {
                    "state": state.model_dump(mode="json"),
                    "trace_reading_id": trace_reading_id,
                }
            )
            state = TarotWorkflowState.model_validate(result["state"])
        if persistence_handler is not None:
            persistence_handler(state)
        return state

    def continue_from_ready_state(
        self,
        state: TarotWorkflowState,
        *,
        persistence_handler: Any | None = None,
    ) -> TarotWorkflowState:
        if self._ready_state_graph is None:
            final_state = self._run_ready_state_without_langgraph(state)
        else:
            compiled = self._ready_state_graph.compile(checkpointer=self._checkpointer)
            graph_state = {"state": state.model_dump(mode="json")}
            result = compiled.invoke(
                graph_state,
                config={"configurable": {"thread_id": self._thread_id(state)}},
            )
            final_state = TarotWorkflowState.model_validate(result["state"])
        if persistence_handler is not None:
            persistence_handler(final_state)
        return final_state

    def _build_question_graph(self) -> StateGraph:
        graph = _StateGraph(dict)
        graph.add_node("pre_input_security", self._graph_pre_input_security_node)
        graph.add_node("clarifier", self._graph_clarifier_node)
        graph.add_edge(START, "pre_input_security")
        graph.add_conditional_edges(
            "pre_input_security",
            self._route_after_pre_input_security,
            {
                "clarifier": "clarifier",
                "end": END,
            },
        )
        graph.add_edge("clarifier", END)
        return graph

    def _build_ready_state_graph(self) -> StateGraph:
        graph = _StateGraph(dict)
        graph.add_node("draw_interpreter", self._graph_draw_node)
        graph.add_node("intermediate_security", self._graph_intermediate_security_node)
        graph.add_node("synthesis", self._graph_synthesis_node)
        graph.add_node("safety_guard", self._graph_safety_node)
        graph.add_edge(START, "draw_interpreter")
        graph.add_conditional_edges(
            "draw_interpreter",
            self._route_after_draw,
            {
                "intermediate_security": "intermediate_security",
                "end": END,
            },
        )
        graph.add_conditional_edges(
            "intermediate_security",
            self._route_after_intermediate_security,
            {
                "synthesis": "synthesis",
                "end": END,
            },
        )
        graph.add_conditional_edges(
            "synthesis",
            self._route_after_synthesis,
            {
                "safety_guard": "safety_guard",
                "end": END,
            },
        )
        graph.add_edge("safety_guard", END)
        return graph

    def _run_ready_state_without_langgraph(self, state: TarotWorkflowState) -> TarotWorkflowState:
        state = self._run_draw_step(state)
        if state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED:
            return state
        state = self._run_intermediate_security_step(state)
        if state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED:
            return state
        state = self._run_synthesis_step(state)
        if state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED:
            return state
        return self._run_safety_step(state)

    def _run_question_without_langgraph(
        self,
        state: TarotWorkflowState,
        *,
        trace_reading_id: str | None,
    ) -> TarotWorkflowState:
        state = execute_pre_input_security_step(
            state=state,
            observer=self._observer,
            trace_event_factory=self._trace_event,
            trace_logger=self._log_trace_events,
            protective_fallback_factory=self._protective_fallback,
            trace_reading_id=trace_reading_id,
        )
        if state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED:
            return state
        return self._run_clarifier_only(state, trace_reading_id=trace_reading_id)

    def _run_clarifier_only(
        self,
        state: TarotWorkflowState,
        *,
        trace_reading_id: str | None,
    ) -> TarotWorkflowState:
        return execute_clarifier_step(
            state=state,
            clarifier_agent=self._clarifier_agent,
            observer=self._observer,
            trace_event_factory=self._trace_event,
            trace_logger=self._log_trace_events,
            trace_reading_id=trace_reading_id,
        )

    def _graph_pre_input_security_node(self, graph_state: dict[str, Any]) -> dict[str, Any]:
        state = TarotWorkflowState.model_validate(graph_state["state"])
        trace_reading_id = graph_state.get("trace_reading_id")
        state = execute_pre_input_security_step(
            state=state,
            observer=self._observer,
            trace_event_factory=self._trace_event,
            trace_logger=self._log_trace_events,
            protective_fallback_factory=self._protective_fallback,
            trace_reading_id=trace_reading_id,
        )
        return {
            "state": state.model_dump(mode="json"),
            "trace_reading_id": trace_reading_id,
        }

    def _graph_clarifier_node(self, graph_state: dict[str, Any]) -> dict[str, Any]:
        state = TarotWorkflowState.model_validate(graph_state["state"])
        trace_reading_id = graph_state.get("trace_reading_id")
        state = self._run_clarifier_only(state, trace_reading_id=trace_reading_id)
        return {
            "state": state.model_dump(mode="json"),
            "trace_reading_id": trace_reading_id,
        }

    def _graph_draw_node(self, graph_state: dict[str, Any]) -> dict[str, Any]:
        state = TarotWorkflowState.model_validate(graph_state["state"])
        state = self._run_draw_step(state)
        return {"state": state.model_dump(mode="json")}

    def _graph_synthesis_node(self, graph_state: dict[str, Any]) -> dict[str, Any]:
        state = TarotWorkflowState.model_validate(graph_state["state"])
        state = self._run_synthesis_step(state)
        return {"state": state.model_dump(mode="json")}

    def _graph_intermediate_security_node(self, graph_state: dict[str, Any]) -> dict[str, Any]:
        state = TarotWorkflowState.model_validate(graph_state["state"])
        state = self._run_intermediate_security_step(state)
        return {"state": state.model_dump(mode="json")}

    def _graph_safety_node(self, graph_state: dict[str, Any]) -> dict[str, Any]:
        state = TarotWorkflowState.model_validate(graph_state["state"])
        state = self._run_safety_step(state)
        return {"state": state.model_dump(mode="json")}

    @staticmethod
    def _route_after_pre_input_security(graph_state: dict[str, Any]) -> str:
        state = TarotWorkflowState.model_validate(graph_state["state"])
        return "end" if state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED else "clarifier"

    @staticmethod
    def _route_after_draw(graph_state: dict[str, Any]) -> str:
        state = TarotWorkflowState.model_validate(graph_state["state"])
        return "end" if state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED else "intermediate_security"

    @staticmethod
    def _route_after_intermediate_security(graph_state: dict[str, Any]) -> str:
        state = TarotWorkflowState.model_validate(graph_state["state"])
        return "end" if state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED else "synthesis"

    @staticmethod
    def _route_after_synthesis(graph_state: dict[str, Any]) -> str:
        state = TarotWorkflowState.model_validate(graph_state["state"])
        return "end" if state.status is WorkflowStatus.SAFE_FALLBACK_RETURNED else "safety_guard"

    def _run_draw_step(self, state: TarotWorkflowState) -> TarotWorkflowState:
        return execute_draw_step(
            state=state,
            draw_agent=self._draw_agent,
            observer=self._observer,
            trace_event_factory=self._trace_event,
            trace_logger=self._log_trace_events,
            protective_fallback_factory=self._protective_fallback,
        )

    def _run_intermediate_security_step(self, state: TarotWorkflowState) -> TarotWorkflowState:
        return execute_intermediate_security_step(
            state=state,
            observer=self._observer,
            trace_event_factory=self._trace_event,
            trace_logger=self._log_trace_events,
            protective_fallback_factory=self._protective_fallback,
        )

    def _run_synthesis_step(self, state: TarotWorkflowState) -> TarotWorkflowState:
        payload = SynthesisInput(
            normalized_question=state.normalized_question or state.raw_question,
            card_interpretations=[card.interpretation for card in state.cards],
            locale=state.locale,
        )
        with self._observer.observe_step(
            step_name="synthesis",
            as_type="chain",
            input_payload={"card_count": len(state.cards)},
            metadata={"session_id": state.session_id, "reading_id": state.reading_id},
        ) as observation:
            started = perf_counter()
            synthesis_output = self._synthesis_agent.run(payload)
            state.synthesis_output = synthesis_output
            state.status = WorkflowStatus.SYNTHESIS_COMPLETED
            state.trace_events.append(
                self._trace_event(
                    step_name="synthesis",
                    event_status=TraceEventStatus.SUCCEEDED,
                    attempt_no=1,
                    started=started,
                    payload={"summary_length": len(synthesis_output.summary)},
                )
            )
            observation.success(output={"summary_length": len(synthesis_output.summary)})
        self._log_trace_events(state=state, reading_id=state.reading_id, only_latest=True)
        return state

    def _run_safety_step(self, state: TarotWorkflowState) -> TarotWorkflowState:
        synthesis_output = state.synthesis_output
        if synthesis_output is None:
            state.completed_at = datetime.now(UTC)
            state.status = WorkflowStatus.SAFE_FALLBACK_RETURNED
            state.safety_output = self._protective_fallback(
                review_notes="Synthesis output was missing; returned a protective fallback output."
            )
            return state

        payload = SafetyReviewInput(
            summary=synthesis_output.summary,
            action_advice=synthesis_output.action_advice,
            reflection_question=synthesis_output.reflection_question,
            locale=state.locale,
        )
        with self._observer.observe_step(
            step_name="safety_guard",
            as_type="chain",
            input_payload={"locale": state.locale},
            metadata={"session_id": state.session_id, "reading_id": state.reading_id},
        ) as observation:
            started = perf_counter()
            try:
                safety_output = self._safety_guard_agent.run(payload)
                state.safety_output = safety_output
                state.status = WorkflowStatus.COMPLETED
                state.completed_at = datetime.now(UTC)
                state.trace_events.append(
                    self._trace_event(
                        step_name="safety_guard",
                        event_status=TraceEventStatus.SUCCEEDED,
                        attempt_no=1,
                        started=started,
                        payload={
                            "risk_level": safety_output.risk_level.value,
                            "action_taken": safety_output.action_taken.value,
                        },
                    )
                )
                observation.success(
                    output={
                        "risk_level": safety_output.risk_level.value,
                        "action_taken": safety_output.action_taken.value,
                    }
                )
            except Exception as exc:  # pragma: no cover - covered by backend unit tests
                state.trace_events.append(
                    self._trace_event(
                        step_name="safety_guard",
                        event_status=TraceEventStatus.FAILED,
                        attempt_no=1,
                        started=started,
                        error_code="SAFETY_GUARD_FAILED",
                        payload={"reason": f"safety_guard execution failed: {exc}"},
                    )
                )
                state.safety_output = self._protective_fallback(
                    review_notes="Safety guard failed; returned a protective fallback output."
                )
                state.status = WorkflowStatus.SAFE_FALLBACK_RETURNED
                state.completed_at = datetime.now(UTC)
                observation.failure(
                    error_code="SAFETY_GUARD_FAILED",
                    message="Safety guard failed; returned fallback output.",
                    metadata={"exception_type": type(exc).__name__},
                )
        self._log_trace_events(state=state, reading_id=state.reading_id, only_latest=True)
        return state

    @staticmethod
    def _protective_fallback(*, review_notes: str) -> SafetyReviewOutput:
        return SafetyReviewOutput(
            risk_level=RiskLevel.HIGH,
            action_taken=SafetyAction.BLOCK_AND_FALLBACK,
            review_notes=review_notes,
            safe_summary="This reading is paused to keep the response cautious and grounded.",
            safe_action_advice="Restate the question in a simple, concrete way and focus on one area at a time.",
            safe_reflection_question="What is the one concern you most want to understand right now?",
        )

    @staticmethod
    def _thread_id(state: TarotWorkflowState) -> str:
        return f"execution:{state.session_id}:{state.reading_id}"

    def _trace_event(
        self,
        *,
        step_name: str,
        event_status: TraceEventStatus,
        attempt_no: int,
        payload: dict[str, Any],
        started: float | None,
        error_code: str | None = None,
    ) -> TraceEventPayload:
        latency_ms = None if started is None else max(0, round((perf_counter() - started) * 1000))
        return TraceEventPayload(
            event_id=str(uuid4()),
            step_name=step_name,
            event_status=event_status,
            attempt_no=attempt_no,
            latency_ms=latency_ms,
            error_code=error_code,
            payload=payload,
            created_at=datetime.now(UTC),
        )

    def _log_trace_events(
        self,
        *,
        state: TarotWorkflowState,
        reading_id: str | None,
        only_latest: bool = False,
    ) -> None:
        events = state.trace_events[-1:] if only_latest else state.trace_events
        for event in events:
            extra = {
                "session_id": state.session_id,
                "reading_id": reading_id,
                "trace_event_id": event.event_id,
                "step_name": event.step_name,
                "event_status": event.event_status.value,
                "attempt_no": event.attempt_no,
                "latency_ms": event.latency_ms,
                "error_code": event.error_code,
                "trace_payload": event.payload,
            }
            if event.event_status is TraceEventStatus.FAILED:
                logger.error("workflow_trace_event", extra=extra)
            elif event.event_status is TraceEventStatus.FALLBACK:
                logger.warning("workflow_trace_event", extra=extra)
            else:
                logger.info("workflow_trace_event", extra=extra)


def build_tarot_workflow() -> StateGraph:
    """Construct the LangGraph graph for the ready-for-draw execution path."""

    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError("LangGraph is not installed in the current environment.")
    return TarotReflectionWorkflow()._build_ready_state_graph()


def _requires_clarification(question: str) -> bool:
    compact = "".join(question.split())
    if len(compact) <= 8:
        return True
    ambiguous_questions = {
        "我该怎么办？",
        "我该怎么办",
        "怎么办？",
        "怎么办",
    }
    return compact in ambiguous_questions
