from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_200_with_valid_status():
    # No live DB in this test environment — health.py catches the connection
    # failure and reports "down" rather than raising, which this also checks.
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] in {"ok", "degraded", "down"}
