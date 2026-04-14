from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_tarot_reading_service
from app.api.errors import AppError
from app.main import create_app


class BrokenReadingService:
    def create_reading(self, request):  # noqa: ANN001
        raise AppError.dependency_unavailable(
            "Database operation failed.",
            details={"reason": "forced by test"},
        )


def test_create_reading_invalid_request_returns_contract_error_payload(db_client) -> None:
    response = db_client.post(
        "/api/v1/readings",
        json={
            "question": "   ",
            "locale": "zh-CN",
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "INVALID_REQUEST"
    assert payload["retryable"] is False
    assert payload["trace_id"].startswith("req_")
    assert payload["details"]["errors"]


def test_create_reading_dependency_failure_returns_contract_error_payload() -> None:
    app = create_app()
    app.dependency_overrides[get_tarot_reading_service] = lambda: BrokenReadingService()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/readings",
            json={
                "question": "最近在工作选择上很犹豫，我应该继续坚持当前方向吗？",
                "locale": "zh-CN",
            },
        )

    payload = response.json()
    assert response.status_code == 503
    assert payload["error_code"] == "DEPENDENCY_UNAVAILABLE"
    assert payload["retryable"] is True
    assert payload["details"]["reason"] == "forced by test"
    assert payload["trace_id"].startswith("req_")
