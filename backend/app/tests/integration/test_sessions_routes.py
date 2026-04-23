from __future__ import annotations


def test_session_flow_runs_from_ready_state_and_exposes_result_and_history(db_client) -> None:
    create_response = db_client.post("/api/v1/sessions", json={})
    assert create_response.status_code == 200
    create_payload = create_response.json()

    session_id = create_payload["session_id"]
    assert create_payload["status"] == "CREATED"
    assert create_payload["locale"] == "zh-CN"
    assert create_payload["spread_type"] == "THREE_CARD_REFLECTION"

    question_response = db_client.post(
        f"/api/v1/sessions/{session_id}/question",
        json={"raw_question": "最近在工作选择上很犹豫，我应该继续坚持当前方向吗？"},
    )
    assert question_response.status_code == 200
    question_payload = question_response.json()

    assert question_payload["status"] == "READY_FOR_DRAW"
    assert question_payload["clarification_required"] is False
    assert question_payload["clarifier_question"] is None
    assert question_payload["normalized_question"]

    result_before_run_response = db_client.get(f"/api/v1/sessions/{session_id}/result")
    assert result_before_run_response.status_code == 409
    assert result_before_run_response.json()["error_code"] == "INVALID_STATE_TRANSITION"

    run_response = db_client.post(f"/api/v1/sessions/{session_id}/run", json={})
    assert run_response.status_code == 200
    run_payload = run_response.json()

    assert run_payload["session_id"] == session_id
    assert run_payload["status"] == "COMPLETED"
    assert len(run_payload["cards"]) == 3

    snapshot_response = db_client.get(f"/api/v1/sessions/{session_id}")
    assert snapshot_response.status_code == 200
    snapshot_payload = snapshot_response.json()

    assert snapshot_payload["session_id"] == session_id
    assert snapshot_payload["status"] == "COMPLETED"
    assert snapshot_payload["normalized_question"] == question_payload["normalized_question"]
    assert snapshot_payload["current_reading_id"] == run_payload["reading_id"]
    assert snapshot_payload["clarification_turn_count"] == 0
    assert snapshot_payload["completed_at"] is not None

    result_response = db_client.get(f"/api/v1/sessions/{session_id}/result")
    assert result_response.status_code == 200
    assert result_response.json()["reading_id"] == run_payload["reading_id"]

    history_response = db_client.get(f"/api/v1/sessions/{session_id}/history")
    assert history_response.status_code == 200
    history_payload = history_response.json()

    assert history_payload["session_id"] == session_id
    assert [item["message_type"] for item in history_payload["items"]] == [
        "ORIGINAL_QUESTION",
        "FINAL_RESULT_SUMMARY",
    ]
    assert history_payload["items"][0]["content"] == "最近在工作选择上很犹豫，我应该继续坚持当前方向吗？"
    assert history_payload["items"][1]["content"]


def test_session_clarification_flow_blocks_run_until_ready_and_tracks_history(db_client) -> None:
    session_id = db_client.post("/api/v1/sessions", json={}).json()["session_id"]

    question_response = db_client.post(
        f"/api/v1/sessions/{session_id}/question",
        json={"raw_question": "我该怎么办？"},
    )
    assert question_response.status_code == 200
    question_payload = question_response.json()

    assert question_payload["status"] == "CLARIFYING"
    assert question_payload["clarification_required"] is True
    assert question_payload["clarifier_question"] == "你现在最想聚焦的是工作、关系、学习，还是个人状态？"

    run_while_clarifying_response = db_client.post(f"/api/v1/sessions/{session_id}/run", json={})
    assert run_while_clarifying_response.status_code == 409
    assert run_while_clarifying_response.json()["error_code"] == "INVALID_STATE_TRANSITION"

    clarification_response = db_client.post(
        f"/api/v1/sessions/{session_id}/clarifications",
        json={
            "turn_index": 1,
            "answer_text": "我想聚焦工作去留、换岗时机，以及继续留下是否更适合我。",
        },
    )
    assert clarification_response.status_code == 200
    clarification_payload = clarification_response.json()

    assert clarification_payload["status"] == "READY_FOR_DRAW"
    assert clarification_payload["clarification_required"] is False
    assert clarification_payload["next_clarifier_question"] is None
    assert clarification_payload["normalized_question"]

    snapshot_response = db_client.get(f"/api/v1/sessions/{session_id}")
    assert snapshot_response.status_code == 200
    snapshot_payload = snapshot_response.json()

    assert snapshot_payload["status"] == "READY_FOR_DRAW"
    assert snapshot_payload["normalized_question"] == clarification_payload["normalized_question"]
    assert snapshot_payload["clarification_turn_count"] == 1
    assert snapshot_payload["current_reading_id"] is None

    run_response = db_client.post(f"/api/v1/sessions/{session_id}/run", json={})
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "COMPLETED"

    history_response = db_client.get(f"/api/v1/sessions/{session_id}/history")
    assert history_response.status_code == 200
    history_payload = history_response.json()

    assert [item["message_type"] for item in history_payload["items"]] == [
        "ORIGINAL_QUESTION",
        "CLARIFIER_QUESTION",
        "CLARIFICATION_ANSWER",
        "FINAL_RESULT_SUMMARY",
    ]
    assert history_payload["items"][1]["content"] == question_payload["clarifier_question"]
    assert history_payload["items"][2]["content"] == "我想聚焦工作去留、换岗时机，以及继续留下是否更适合我。"


def test_session_invalid_transitions_and_missing_session_follow_contract(db_client) -> None:
    missing_response = db_client.get("/api/v1/sessions/not-found")
    assert missing_response.status_code == 404
    assert missing_response.json()["error_code"] == "RESOURCE_NOT_FOUND"

    session_id = db_client.post("/api/v1/sessions", json={}).json()["session_id"]

    clarification_response = db_client.post(
        f"/api/v1/sessions/{session_id}/clarifications",
        json={"turn_index": 1, "answer_text": "补充说明"},
    )
    assert clarification_response.status_code == 409
    clarification_payload = clarification_response.json()
    assert clarification_payload["error_code"] == "INVALID_STATE_TRANSITION"
    assert clarification_payload["details"]["current_status"] == "CREATED"

    db_client.post(
        f"/api/v1/sessions/{session_id}/question",
        json={"raw_question": "最近在工作选择上很犹豫，我应该继续坚持当前方向吗？"},
    )

    repeated_question_response = db_client.post(
        f"/api/v1/sessions/{session_id}/question",
        json={"raw_question": "我又补了一条问题"},
    )
    assert repeated_question_response.status_code == 409
    repeated_question_payload = repeated_question_response.json()
    assert repeated_question_payload["error_code"] == "INVALID_STATE_TRANSITION"
    assert repeated_question_payload["details"]["current_status"] == "READY_FOR_DRAW"
