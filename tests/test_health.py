import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_documents_health_check() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]


@pytest.mark.parametrize("path", ["/docs", "/redoc"])
def test_api_documentation_is_available(path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
