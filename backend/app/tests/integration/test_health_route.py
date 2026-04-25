def test_health_route_returns_expected_payload(client) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"].startswith("req_")

    payload = response.json()
    assert payload["status"] in ("ok", "degraded")
    assert payload["service"] == "multi-agent-tarot-backend"
    assert payload["version"] == "0.1.0"
    assert payload["environment"] == "local"
    assert payload["timestamp"].endswith("Z")

    deps = payload["dependencies"]
    assert set(deps.keys()) == {"database", "openai", "langfuse"}
    for dep in deps.values():
        assert dep["status"] in ("ok", "unavailable")
