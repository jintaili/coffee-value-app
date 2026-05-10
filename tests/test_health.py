from fastapi.testclient import TestClient

from coffee_value_app.main import create_app


def test_health_endpoint() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "coffee-value-app",
        "version": "0.1.0",
    }

