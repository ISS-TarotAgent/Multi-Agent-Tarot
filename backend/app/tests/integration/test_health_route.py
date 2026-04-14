def test_health_route_returns_expected_payload(client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"].startswith("req_")

    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "multi-agent-tarot-backend"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "local"
    assert payload["timestamp"].endswith("Z")
