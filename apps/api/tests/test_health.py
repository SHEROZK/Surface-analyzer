from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_capabilities_endpoint():
    response = client.get("/api/v1/capabilities")
    assert response.status_code == 200
    assert len(response.json()) >= 5
