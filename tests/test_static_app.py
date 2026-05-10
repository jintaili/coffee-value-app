from fastapi.testclient import TestClient

from coffee_value_app.main import create_app


def test_index_served() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Worth the Roast?" in response.text
    assert "/static/app.js" in response.text
