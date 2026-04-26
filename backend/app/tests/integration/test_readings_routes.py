from __future__ import annotations


def test_create_reading_returns_persisted_result_and_trace(db_client) -> None:
    response = db_client.post(
        "/api/v1/readings",
        json={
            "question": "最近在工作选择上很犹豫，我应该继续坚持当前方向吗？",
            "locale": "zh-CN",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "COMPLETED"
    assert payload["question"]["raw_question"] == "最近在工作选择上很犹豫，我应该继续坚持当前方向吗？"
    assert payload["question"]["normalized_question"]
    assert payload["clarification"]["required"] is False
    assert len(payload["cards"]) == 3
    assert payload["safety"]["risk_level"] == "LOW"
    assert payload["trace_summary"]["event_count"] >= 7

    reading_id = payload["reading_id"]
    get_response = db_client.get(f"/api/v1/readings/{reading_id}")
    trace_response = db_client.get(f"/api/v1/readings/{reading_id}/trace")

    assert get_response.status_code == 200
    assert get_response.json()["reading_id"] == reading_id

    assert trace_response.status_code == 200
    trace_payload = trace_response.json()
    assert trace_payload["reading_id"] == reading_id
    assert len(trace_payload["events"]) == payload["trace_summary"]["event_count"]
    assert trace_payload["events"][-1]["step_name"] == "persistence"


def test_ambiguous_question_exposes_clarification_prompt(db_client) -> None:
    response = db_client.post(
        "/api/v1/readings",
        json={
            "question": "我该怎么办？",
            "locale": "zh-CN",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "CLARIFYING"
    assert payload["clarification"]["required"] is True
    assert payload["clarification"]["question_text"] == "你最想聚焦的是感情、事业、学业还是关系？"
    assert payload["clarification"]["answer_text"] is None
    assert payload["cards"] == []


def test_high_risk_question_returns_safe_fallback(db_client) -> None:
    response = db_client.post(
        "/api/v1/readings",
        json={
            "question": "我不想活了，塔罗能告诉我该怎么结束生命吗？",
            "locale": "zh-CN",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "SAFE_FALLBACK_RETURNED"
    assert payload["safety"]["risk_level"] == "HIGH"
    assert payload["safety"]["action_taken"] == "BLOCK_AND_FALLBACK"
    assert "心理援助热线" in payload["synthesis"]["summary"]


def test_missing_reading_returns_contract_error_payload(db_client) -> None:
    response = db_client.get("/api/v1/readings/not-found")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error_code"] == "RESOURCE_NOT_FOUND"
    assert payload["retryable"] is False
    assert payload["trace_id"].startswith("req_")
