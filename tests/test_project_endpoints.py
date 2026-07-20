from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.crud import labels as label_crud
from app.crud import projects as project_crud
from app.main import app
from app.models.enums import ProjectStatus
from app.models.label import Label
from app.models.project import Project


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_project() -> Project:
    return Project(
        id=1,
        workspace_id=2,
        name="TaskHub API",
        description="Day 2 CRUD exercise",
        status=ProjectStatus.ACTIVE,
        created_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )


def test_list_projects_returns_response_models(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_project: Project,
) -> None:
    async def fake_get_projects(_: object) -> list[Project]:
        return [sample_project]

    monkeypatch.setattr(project_crud, "get_projects", fake_get_projects)

    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "TaskHub API"
    assert response.json()[0]["status"] == "ACTIVE"


def test_get_project_returns_404_when_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_project_by_id(_: object, __: int) -> None:
        return None

    monkeypatch.setattr(project_crud, "get_project_by_id", fake_get_project_by_id)

    response = client.get("/api/v1/projects/999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_list_labels_returns_response_models(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sample_label = Label(id=1, project_id=1, name="backend", color="#2563EB")

    async def fake_get_labels(_: object) -> list[Label]:
        return [sample_label]

    monkeypatch.setattr(label_crud, "get_labels", fake_get_labels)

    response = client.get("/api/v1/labels")

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "project_id": 1, "name": "backend", "color": "#2563EB"}]
