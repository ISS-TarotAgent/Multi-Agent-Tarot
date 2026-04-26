from __future__ import annotations

from app.infrastructure.observability import LangfuseWorkflowObserver, NoOpWorkflowObserver


class FakeObservation:
    def __init__(
        self,
        *,
        client: "FakeLangfuseClient",
        observation_id: str,
        name: str,
        input_payload: dict[str, object] | None,
        metadata: dict[str, object] | None,
    ) -> None:
        self._client = client
        self.id = observation_id
        self.name = name
        self.input_payload = input_payload
        self.metadata = metadata
        self.updates: list[dict[str, object]] = []

    def __enter__(self) -> "FakeObservation":
        self._client.stack.append(self)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        self._client.stack.pop()

    def update(self, **kwargs: object) -> None:
        self.updates.append(kwargs)

    def end(self, **kwargs: object) -> None:
        self.update(**kwargs)

    def span(
        self,
        *,
        name: str,
        input: dict[str, object] | None = None,  # noqa: A002
        metadata: dict[str, object] | None = None,
    ) -> "FakeObservation":
        observation = FakeObservation(
            client=self._client,
            observation_id=f"span_{len(self._client.created)}",
            name=name,
            input_payload=input,
            metadata=metadata,
        )
        self._client.created.append(observation)
        return observation


class FakeLangfuseClient:
    def __init__(self) -> None:
        self.stack: list[FakeObservation] = []
        self.created: list[FakeObservation] = []

    def trace(
        self,
        *,
        id: str | None = None,  # noqa: A002
        name: str,
        session_id: str,
        input: dict[str, object] | None = None,  # noqa: A002
        metadata: dict[str, object] | None = None,
    ) -> FakeObservation:
        observation = FakeObservation(
            client=self,
            observation_id=id or f"trace_{len(self.created)}",
            name=name,
            input_payload=input,
            metadata=metadata | {"session_id": session_id} if metadata is not None else {"session_id": session_id},
        )
        self.created.append(observation)
        return observation

    def start_as_current_observation(
        self,
        *,
        name: str,
        as_type: str,
        input: dict[str, object] | None = None,  # noqa: A002
        metadata: dict[str, object] | None = None,
    ) -> FakeObservation:
        observation = FakeObservation(
            client=self,
            observation_id=f"observation_{len(self.created)}",
            name=name,
            input_payload=input,
            metadata=metadata,
        )
        self.created.append(observation)
        return observation

    def get_current_trace_id(self) -> str | None:
        if not self.stack:
            return None
        return self.stack[0].id


def test_noop_workflow_observer_supports_nested_scopes() -> None:
    observer = NoOpWorkflowObserver()

    with observer.observe_operation(
        name="tarot.reading.create",
        session_id="session-1",
        reading_id="reading-1",
        input_payload={"question": "我应该如何处理当前的工作压力？"},
    ) as operation:
        operation.success(output={"status": "COMPLETED"})
        with observer.observe_step(
            step_name="clarifier",
            as_type="agent",
            input_payload={"raw_question": "我应该如何处理当前的工作压力？"},
        ) as step:
            step.failure(error_code="CLARIFIER_FALLBACK_TO_RAW", message="clarifier failed")

    assert observer.get_current_trace_id() is None


def test_langfuse_workflow_observer_records_operation_and_step_payloads() -> None:
    client = FakeLangfuseClient()
    observer = LangfuseWorkflowObserver(client=client)

    with observer.observe_operation(
        name="tarot.reading.create",
        session_id="session-1",
        reading_id="reading-1",
        input_payload={"question": "我应该如何处理当前的工作压力？"},
        metadata={"locale": "zh-CN"},
    ) as operation:
        assert observer.get_current_trace_id() == "reading-1"
        operation.success(output={"status": "COMPLETED"})

        with observer.observe_step(
            step_name="clarifier",
            as_type="agent",
            input_payload={"raw_question": "我应该如何处理当前的工作压力？"},
            metadata={"attempt_no": 1},
        ) as step:
            step.success(output={"clarification_required": False})

    assert observer.get_current_trace_id() is None
    assert [observation.name for observation in client.created] == [
        "tarot.reading.create",
        "clarifier",
    ]
    assert client.created[0].metadata == {
        "locale": "zh-CN",
        "session_id": "session-1",
        "reading_id": "reading-1",
    }
    assert client.created[0].updates[-1]["output"] == {"status": "COMPLETED"}
    assert client.created[1].updates[-1]["output"] == {"clarification_required": False}
