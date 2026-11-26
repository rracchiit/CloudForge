from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "CloudForge API",
    }


def test_api_documentation():
    response = client.get("/docs")

    assert response.status_code == 200


def test_openapi_schema():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    assert schema["info"]["title"] == "CloudForge API"


def test_apps_endpoint_exists():
    response = client.get("/api/v1/apps/")

    assert response.status_code != 404
