from __future__ import annotations

from sqlalchemy import create_engine, text


def test_postgresql_chain_runs_mvp_reading_via_alembic_and_persists_facts(
    postgres_db_client,
    postgres_database_url: str,
) -> None:
    response = postgres_db_client.post(
        "/api/v1/readings",
        json={
            "question": "最近在工作选择上很犹豫，我应该继续坚持当前方向吗？",
            "locale": "zh-CN",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    trace_response = postgres_db_client.get(f"/api/v1/readings/{payload['reading_id']}/trace")
    assert trace_response.status_code == 200

    engine = create_engine(postgres_database_url, future=True)
    try:
        with engine.connect() as connection:
            reading_row = (
                connection.execute(
                    text(
                        """
                    select status, normalized_question, risk_level, fallback_used
                    from readings
                    where id = :reading_id
                    """
                    ),
                    {"reading_id": payload["reading_id"]},
                )
                .mappings()
                .one()
            )
            session_row = (
                connection.execute(
                    text(
                        """
                    select status, normalized_question
                    from sessions
                    where id = :session_id
                    """
                    ),
                    {"session_id": payload["session_id"]},
                )
                .mappings()
                .one()
            )
            trace_count = connection.execute(
                text(
                    """
                    select count(*)
                    from trace_events
                    where reading_id = :reading_id
                    """
                ),
                {"reading_id": payload["reading_id"]},
            ).scalar_one()
    finally:
        engine.dispose()

    assert payload["status"] == "COMPLETED"
    assert reading_row["status"] == "COMPLETED"
    assert session_row["status"] == "COMPLETED"
    assert reading_row["normalized_question"] == payload["question"]["normalized_question"]
    assert session_row["normalized_question"] == payload["question"]["normalized_question"]
    assert reading_row["risk_level"] == payload["safety"]["risk_level"]
    assert reading_row["fallback_used"] is False
    assert trace_count == payload["trace_summary"]["event_count"]
    assert len(trace_response.json()["events"]) == trace_count


def test_postgresql_chain_runs_session_clarification_flow_and_persists_stage3_facts(
    postgres_db_client,
    postgres_database_url: str,
) -> None:
    create_response = postgres_db_client.post("/api/v1/sessions", json={})
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    question_response = postgres_db_client.post(
        f"/api/v1/sessions/{session_id}/question",
        json={"raw_question": "我该怎么办？"},
    )
    assert question_response.status_code == 200
    question_payload = question_response.json()
    assert question_payload["status"] == "CLARIFYING"
    assert question_payload["clarification_required"] is True

    clarification_response = postgres_db_client.post(
        f"/api/v1/sessions/{session_id}/clarifications",
        json={
            "turn_index": 1,
            "answer_text": "主要是工作去留和换岗时机，我想知道现在是不是该离开当前岗位。",
        },
    )
    assert clarification_response.status_code == 200
    clarification_payload = clarification_response.json()
    assert clarification_payload["status"] == "READY_FOR_DRAW"
    assert clarification_payload["clarification_required"] is False

    run_response = postgres_db_client.post(f"/api/v1/sessions/{session_id}/run", json={})
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["status"] == "COMPLETED"

    history_response = postgres_db_client.get(f"/api/v1/sessions/{session_id}/history")
    assert history_response.status_code == 200
    history_payload = history_response.json()

    engine = create_engine(postgres_database_url, future=True)
    try:
        with engine.connect() as connection:
            session_row = (
                connection.execute(
                    text(
                        """
                    select status, normalized_question
                    from sessions
                    where id = :session_id
                    """
                    ),
                    {"session_id": session_id},
                )
                .mappings()
                .one()
            )
            reading_row = (
                connection.execute(
                    text(
                        """
                    select id::text as id, status, normalized_question
                    from readings
                    where session_id = :session_id
                    """
                    ),
                    {"session_id": session_id},
                )
                .mappings()
                .one()
            )
            message_rows = (
                connection.execute(
                    text(
                        """
                    select message_type, sender_role, turn_index, content
                    from session_messages
                    where session_id = :session_id
                    order by turn_index, created_at
                    """
                    ),
                    {"session_id": session_id},
                )
                .mappings()
                .all()
            )
            trace_rows = (
                connection.execute(
                    text(
                        """
                    select step_name, event_status, reading_id::text as reading_id
                    from trace_events
                    where session_id = :session_id
                    order by created_at, step_name
                    """
                    ),
                    {"session_id": session_id},
                )
                .mappings()
                .all()
            )
    finally:
        engine.dispose()

    assert session_row["status"] == "COMPLETED"
    assert session_row["normalized_question"] == clarification_payload["normalized_question"]
    assert reading_row["id"] == run_payload["reading_id"]
    assert reading_row["status"] == "COMPLETED"
    assert reading_row["normalized_question"] == clarification_payload["normalized_question"]
    assert [item["message_type"] for item in history_payload["items"]] == [
        "ORIGINAL_QUESTION",
        "CLARIFIER_QUESTION",
        "CLARIFICATION_ANSWER",
        "FINAL_RESULT_SUMMARY",
    ]
    assert [(row["message_type"], row["sender_role"], row["turn_index"]) for row in message_rows] == [
        ("ORIGINAL_QUESTION", "USER", 1),
        ("CLARIFIER_QUESTION", "AGENT", 2),
        ("CLARIFICATION_ANSWER", "USER", 3),
        ("FINAL_RESULT_SUMMARY", "SYSTEM", 4),
    ]
    assert message_rows[1]["content"] == question_payload["clarifier_question"]
    assert message_rows[2]["content"] == "主要是工作去留和换岗时机，我想知道现在是不是该离开当前岗位。"

    session_level_steps = [(row["step_name"], row["event_status"]) for row in trace_rows if row["reading_id"] is None]
    reading_level_steps = [
        (row["step_name"], row["event_status"]) for row in trace_rows if row["reading_id"] == run_payload["reading_id"]
    ]

    assert session_level_steps == [
        ("session_bootstrap", "SUCCEEDED"),
        ("pre_input_security", "SUCCEEDED"),
        ("clarifier", "SUCCEEDED"),
        ("persistence", "SUCCEEDED"),
        ("clarifier", "SUCCEEDED"),
        ("persistence", "SUCCEEDED"),
    ]
    assert sorted(reading_level_steps) == sorted(
        [
            ("draw_interpreter", "STARTED"),
            ("draw_interpreter", "SUCCEEDED"),
            ("synthesis", "STARTED"),
            ("synthesis", "SUCCEEDED"),
            ("safety_guard", "STARTED"),
            ("safety_guard", "SUCCEEDED"),
            ("persistence", "SUCCEEDED"),
        ]
    )
