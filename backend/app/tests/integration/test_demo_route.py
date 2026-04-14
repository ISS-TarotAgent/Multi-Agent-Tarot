from __future__ import annotations


def test_demo_route_serves_manual_backend_chain_page(client) -> None:
    response = client.get("/demo")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "后端全链路测试 Demo" in response.text
    assert "健康检查" in response.text
    assert "readings 主链路" in response.text
    assert "sessions 澄清链路" in response.text
