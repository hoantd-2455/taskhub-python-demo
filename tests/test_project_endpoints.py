from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.crud import labels as label_crud
from app.crud import projects as project_crud
from app.main import app
from app.models.enums import ProjectStatus, UserRole
from app.models.label import Label
from app.models.project import Project
from app.models.user import User


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


@pytest.fixture
def sample_user() -> User:
    return User(
        id=1,
        email="reader@example.com",
        full_name="Project Reader",
        hashed_password="test-only-hash",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime(2026, 7, 20, tzinfo=timezone.utc),
    )


def test_list_projects_returns_response_models(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_project: Project,
    sample_user: User,
) -> None:
    async def fake_get_user_by_id(_: object, __: int) -> User:
        return sample_user

    async def fake_get_accessible_projects(_: object, **__: object) -> list[Project]:
        return [sample_project]

    monkeypatch.setattr(project_crud, "get_accessible_projects", fake_get_accessible_projects)
    monkeypatch.setattr("app.crud.users.get_user_by_id", fake_get_user_by_id)

    response = client.get(
        "/api/v1/projects",
        headers={"Authorization": f"Bearer {create_access_token(sample_user.id)}"},
    )

    assert response.status_code == 200
    assert response.json()[0]["name"] == "TaskHub API"
    assert response.json()[0]["status"] == "ACTIVE"


def test_get_project_returns_404_when_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    async def fake_get_user_by_id(_: object, __: int) -> User:
        return sample_user

    async def fake_get_project_by_id(_: object, __: int) -> None:
        return None

    monkeypatch.setattr(project_crud, "get_project_by_id", fake_get_project_by_id)
    monkeypatch.setattr("app.crud.users.get_user_by_id", fake_get_user_by_id)

    response = client.get(
        "/api/v1/projects/999",
        headers={"Authorization": f"Bearer {create_access_token(sample_user.id)}"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_list_labels_returns_response_models(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    sample_label = Label(id=1, project_id=1, name="backend", color="#2563EB")

    async def fake_get_user_by_id(_: object, __: int) -> User:
        return sample_user

    async def fake_get_accessible_labels(_: object, **__: object) -> list[Label]:
        return [sample_label]

    monkeypatch.setattr(label_crud, "get_accessible_labels", fake_get_accessible_labels)
    monkeypatch.setattr("app.crud.users.get_user_by_id", fake_get_user_by_id)

    response = client.get(
        "/api/v1/labels",
        headers={"Authorization": f"Bearer {create_access_token(sample_user.id)}"},
    )

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "project_id": 1, "name": "backend", "color": "#2563EB"}]
