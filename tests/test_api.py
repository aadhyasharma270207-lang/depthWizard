from fastapi.testclient import TestClient
from depthwizard.api.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["system"] == "DepthWizard SIH 2026 Backend"


def test_demo_list_endpoint():
    response = client.get("/api/v1/demo/list")
    assert response.status_code == 200
    data = response.json()
    assert "datasets" in data
    assert len(data["datasets"]) >= 2
