from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.cache import get_redis_client
from app.crud import projects as project_crud
from app.crud import refresh_tokens as refresh_token_crud
from app.crud import tasks as task_crud
from app.crud import users as user_crud
from app.crud import workspaces as workspace_crud
from app.main import app
from app.models.enums import ProjectStatus, TaskPriority, TaskStatus, UserRole, WorkspaceRole
from app.models.project import Project
from app.models.refresh_token import RefreshToken
from app.models.task import Task
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.user import UserRegister


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_redis_client] = lambda: None
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_register_login_and_create_task_api_flow(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the main Day 7 HTTP flow without needing an external test database."""

    users_by_email: dict[str, User] = {}
    created_task_titles: list[str] = []
    project = Project(
        id=10,
        workspace_id=20,
        name="Integration project",
        description=None,
        status=ProjectStatus.ACTIVE,
        created_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )

    async def fake_get_user_by_email(_: object, email: str) -> User | None:
        return users_by_email.get(email)

    async def fake_create_user(_: object, user_in: UserRegister, hashed_password: str) -> User:
        user = User(
            id=1,
            email=str(user_in.email),
            full_name=user_in.full_name,
            hashed_password=hashed_password,
            role=UserRole.MEMBER,
            is_active=True,
            created_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )
        users_by_email[user.email] = user
        return user

    async def fake_get_user_by_id(_: object, user_id: int) -> User | None:
        return next((user for user in users_by_email.values() if user.id == user_id), None)

    async def fake_create_refresh_token(_: object, **kwargs: object) -> RefreshToken:
        return RefreshToken(
            id=1,
            user_id=int(kwargs["user_id"]),
            jti=str(kwargs["jti"]),
            expires_at=kwargs["expires_at"],
        )

    async def fake_get_project_by_id(_: object, __: int) -> Project:
        return project

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

    async def fake_create_task(
        _: object,
        project_id: int,
        task_in: object,
        created_by: int,
    ) -> Task:
        created_task_titles.append(task_in.title)
        return Task(
            id=30,
            project_id=project_id,
            assignee_id=None,
            title=task_in.title,
            description=task_in.description,
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            due_date=None,
            created_by=created_by,
            created_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(user_crud, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(user_crud, "create_user", fake_create_user)
    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(refresh_token_crud, "create_refresh_token", fake_create_refresh_token)
    monkeypatch.setattr(project_crud, "get_project_by_id", fake_get_project_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(task_crud, "create_task", fake_create_task)

    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "learner@example.com",
            "full_name": "Day Seven Learner",
            "password": "learning-password",
        },
    )
    logged_in = client.post(
        "/api/v1/auth/login",
        data={"username": "learner@example.com", "password": "learning-password"},
    )
    created = client.post(
        "/api/v1/projects/10/tasks",
        headers={"Authorization": f"Bearer {logged_in.json()['access_token']}"},
        json={"title": "Task created through the API flow"},
    )

    assert registered.status_code == 201
    assert logged_in.status_code == 200
    assert created.status_code == 201
    assert created.json()["created_by"] == 1
    assert created_task_titles == ["Task created through the API flow"]
