from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.crud import projects as project_crud
from app.crud import tasks as task_crud
from app.crud import users as user_crud
from app.crud import workspaces as workspace_crud
from app.main import app
from app.models.enums import ProjectStatus, TaskPriority, TaskStatus, UserRole, WorkspaceRole
from app.models.label import Label
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import WorkspaceMember


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_task() -> Task:
    return Task(
        id=10,
        project_id=1,
        assignee_id=None,
        title="Model relationships",
        description="Connect Project and Task",
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 7, 25),
        created_by=1,
        created_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_project(sample_task: Task) -> Project:
    project = Project(
        id=1,
        workspace_id=2,
        name="TaskHub API",
        description="Day 3 relationships",
        status=ProjectStatus.ACTIVE,
        created_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )
    project.tasks.append(sample_task)
    return project


@pytest.fixture
def sample_user() -> User:
    return User(
        id=1,
        email="day3@example.test",
        full_name="Day Three User",
        hashed_password="not-exposed",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )


def test_task_label_relationship_is_bidirectional(sample_task: Task) -> None:
    label = Label(id=5, project_id=1, name="backend", color="#2563EB")

    sample_task.labels.append(label)

    assert label in sample_task.labels
    assert sample_task in label.tasks


def test_get_project_tasks_returns_paginated_tasks(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_project: Project,
    sample_task: Task,
    sample_user: User,
) -> None:
    async def fake_get_project_by_id(_: object, __: int) -> Project:
        return sample_project

    async def fake_get_user_by_id(_: object, __: int) -> User:
        return sample_user

    async def fake_get_workspace_member(
        _: object,
        workspace_id: int,
        user_id: int,
    ) -> WorkspaceMember:
        return WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=WorkspaceRole.VIEWER,
        )

    async def fake_get_project_task_page(_: object, __: int, ___: object) -> task_crud.TaskPage:
        return task_crud.TaskPage(items=[sample_task], total=1)

    monkeypatch.setattr(project_crud, "get_project_by_id", fake_get_project_by_id)
    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(task_crud, "get_project_task_page", fake_get_project_task_page)

    response = client.get(
        "/api/v1/projects/1/tasks?page=1&limit=10",
        headers={"Authorization": f"Bearer {create_access_token(sample_user.id)}"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": 10,
            "project_id": 1,
            "assignee_id": None,
            "title": "Model relationships",
            "description": "Connect Project and Task",
            "status": "TODO",
            "priority": "HIGH",
            "due_date": "2026-07-25",
            "created_by": 1,
            "created_at": "2026-07-21T00:00:00Z",
        }
    ]
    assert response.json()["total"] == 1


def test_create_task_returns_201(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_project: Project,
    sample_task: Task,
    sample_user: User,
) -> None:
    async def fake_get_project_by_id(_: object, __: int) -> Project:
        return sample_project

    async def fake_get_user_by_id(_: object, __: int) -> User:
        return sample_user

    async def fake_create_task(_: object, __: int, ___: object, ____: int) -> Task:
        return sample_task

    async def fake_get_workspace_member(
        _: object,
        workspace_id: int,
        user_id: int,
    ) -> WorkspaceMember:
        return WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=WorkspaceRole.EDITOR,
        )

    monkeypatch.setattr(project_crud, "get_project_by_id", fake_get_project_by_id)
    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(task_crud, "create_task", fake_create_task)

    task_body = {
        "title": "Model relationships",
        "description": "Connect Project and Task",
        "priority": "HIGH",
        "due_date": "2026-07-25",
    }
    unauthenticated = client.post("/api/v1/projects/1/tasks", json=task_body)
    response = client.post(
        "/api/v1/projects/1/tasks",
        json=task_body,
        headers={"Authorization": f"Bearer {create_access_token(sample_user.id)}"},
    )

    assert unauthenticated.status_code == 401
    assert response.status_code == 201
    assert response.json()["project_id"] == 1
    assert response.json()["created_by"] == 1


def test_get_user_profile_excludes_password_hash(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    sample_user: User,
) -> None:
    async def fake_get_user_profile(_: object, __: int) -> User:
        return sample_user

    monkeypatch.setattr(user_crud, "get_user_profile", fake_get_user_profile)

    response = client.get("/api/v1/users/1/profile")

    assert response.status_code == 200
    assert response.json()["email"] == "day3@example.test"
    assert "hashed_password" not in response.json()
