import pytest
from sqlalchemy.exc import OperationalError


@pytest.mark.parametrize(
    "path",
    [
        "/health",
        "/api/analytics/overview",
        "/api/analytics/skills",
        "/api/analytics/jobs",
        "/api/analytics/filters",
    ],
)
def test_read_endpoints(client, path):
    result = client.get(path)
    assert result.status_code == 200, result.text


def test_health_reports_database_and_index(client):
    assert client.get("/health").json() == {
        "status": "ok",
        "database": "connected",
        "jobs": 4,
        "chunks": 4,
        "index_ready": True,
    }
    status = client.get("/api/system/status")
    assert status.status_code == 200
    assert status.json()["index_version"] == "v1"
    assert status.json()["embeddings"] == 4
    assert status.json()["ready"]
    assert "password" not in status.text.lower()


def test_filtered_jobs_and_validation(client):
    assert client.get("/api/analytics/jobs?country=France").json()["total"] == 2
    result = client.get("/api/analytics/jobs", params={"search": "PYTHON", "limit": 1})
    assert result.json()["total"] == 3 and len(result.json()["items"]) == 1
    assert client.get("/api/analytics/jobs?search=Python&country=France").json()["total"] == 1
    assert client.get("/api/analytics/jobs", params={"search": "%"}).json()["total"] == 0
    assert client.get("/api/analytics/jobs", params={"search": "' OR 1=1 --"}).json()["total"] == 0
    assert client.get("/api/analytics/jobs", params={"search": "x" * 201}).status_code == 422
    assert client.get("/api/analytics/jobs?limit=1000").status_code == 422
    assert client.post("/api/assistant/query", json={"question": ""}).status_code == 422
    assert (
        client.post(
            "/api/assistant/query", json={"question": "Hello", "filters": {"sql": "bad"}}
        ).status_code
        == 422
    )


def test_assistant_routes_and_rag(client):
    result = client.post(
        "/api/assistant/query", json={"question": "What percentage of jobs mention Python?"}
    ).json()
    assert result["route"] == "analytics"
    assert result["data"]["percentage"] == 75
    result = client.post("/api/rag/query", json={"question": "Describe Kubernetes deployments"})
    assert result.status_code == 200
    assert result.json()["sources"]
    assert client.post("/api/rag/query", json={"question": "How many jobs?"}).status_code == 422


def test_reindex_auth_and_execution(client):
    assert client.post("/api/rag/reindex", json={}).status_code == 403
    result = client.post("/api/rag/reindex", json={}, headers={"X-Admin-Token": "test-admin"})
    assert result.status_code == 200, result.text
    assert result.json()["jobs"] == 4


def test_database_failure_does_not_expose_credentials(client, monkeypatch):
    from src.analytics.service import AnalyticsService

    def fail(*args):
        raise OperationalError("sensitive SQL", {}, Exception("secret password"))

    monkeypatch.setattr(AnalyticsService, "overview", fail)
    result = client.get("/api/analytics/overview")
    assert result.status_code == 503
    assert "secret" not in result.text
