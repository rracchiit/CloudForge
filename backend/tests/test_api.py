
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db

# Import all models so SQLAlchemy registers their relationships.
from app.models.application import Application
from app.models.project import Project
from app.models.deployment import Deployment


# Isolated in-memory SQLite database for testing.
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "CloudForge API",
    }


def test_api_documentation(client):
    response = client.get("/docs")

    assert response.status_code == 200


def test_openapi_schema(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "CloudForge API"


def test_list_apps(client):
    response = client.get("/api/v1/apps")

    assert response.status_code == 200
    assert response.json() == []


def test_create_app(client):
    response = client.post(
        "/api/v1/apps",
        json={
            "url": "https://github.com/octocat/Hello-World",
            "branch": "main",
        },
    )

    assert response.status_code == 202

    data = response.json()

    assert data["owner"] == "octocat"
    assert data["repo"] == "Hello-World"
    assert data["branch"] == "main"
    assert data["status"] == "QUEUED"
    assert data["deployment_id"]


def test_duplicate_app_rejected(client):
    payload = {
        "url": "https://github.com/octocat/Hello-World",
        "branch": "main",
    }

    first_response = client.post("/api/v1/apps", json=payload)
    second_response = client.post("/api/v1/apps", json=payload)

    assert first_response.status_code == 202
    assert second_response.status_code == 409


def test_invalid_github_url_rejected(client):
    response = client.post(
        "/api/v1/apps",
        json={
            "url": "https://example.com/not-a-github-repo",
            "branch": "main",
        },
    )

    assert response.status_code == 422


def test_get_nonexistent_app(client):
    response = client.get("/api/v1/apps/99999")

    assert response.status_code == 404
