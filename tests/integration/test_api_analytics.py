from fastapi.testclient import TestClient


def test_summary_requires_login(client: TestClient):
    assert client.get("/analytics/summary").status_code == 401


def test_summary_rejects_a_clerk(clerk_client: TestClient):
    assert clerk_client.get("/analytics/summary").status_code == 403


def test_summary_returns_data_for_a_manager(manager_client: TestClient):
    response = manager_client.get("/analytics/summary")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["status_counts"], list)
    assert isinstance(body["exception_reasons"], list)
    assert isinstance(body["usage_by_day"], list)
    if body["status_counts"]:
        assert {"decision_status", "count"} <= body["status_counts"][0].keys()
    if body["exception_reasons"]:
        assert {"step", "rule_code", "count"} <= body["exception_reasons"][0].keys()
    if body["usage_by_day"]:
        assert {"date", "investigations", "total_tokens", "estimated_cost_usd"} <= body["usage_by_day"][
            0
        ].keys()
