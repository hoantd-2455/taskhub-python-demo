from collections.abc import AsyncIterator
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.cache import get_redis_client
from app.core.security import create_access_token
from app.crud import projects as project_crud
from app.crud import tasks as task_crud
from app.crud import users as user_crud
from app.crud import workspaces as workspace_crud
from app.main import app
from app.models.enums import ProjectStatus, TaskPriority, TaskStatus, UserRole, WorkspaceRole
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.routers import tasks as task_router
from app.schemas.task import TaskListParams
from app.services.task_cache import build_project_task_list_cache_key


class FakeRedis:
    """Small in-memory Redis stand-in that supports the cache operations used by the API."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.get_calls = 0
        self.set_calls = 0
        self.deleted_keys: list[str] = []

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self.values.get(key)

    async def set(self, key: str, value: str, *, ex: int) -> None:
        assert ex > 0
        self.set_calls += 1
        self.values[key] = value

    async def scan_iter(self, *, match: str) -> AsyncIterator[str]:
        prefix = match.removesuffix("*")
        for key in list(self.values):
            if key.startswith(prefix):
                yield key

    async def delete(self, *keys: str) -> int:
        for key in keys:
            self.deleted_keys.append(key)
            self.values.pop(key, None)
        return len(keys)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def project() -> Project:
    return Project(
        id=10,
        workspace_id=20,
        name="Cached project",
        description=None,
        status=ProjectStatus.ACTIVE,
        created_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )


@pytest.fixture
def owner() -> User:
    return User(
        id=1,
        email="owner@example.com",
        full_name="Cache Owner",
        hashed_password="test-only-hash",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )


@pytest.fixture
def task(project: Project) -> Task:
    return Task(
        id=30,
        project_id=project.id,
        assignee_id=None,
        title="Cached task",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        due_date=None,
        created_by=1,
        created_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )


def configure_project_access(
    monkeypatch: pytest.MonkeyPatch,
    project: Project,
    owner: User,
) -> None:
    async def fake_get_user_by_id(_: object, __: int) -> User:
        return owner

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
            role=WorkspaceRole.OWNER,
        )

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(project_crud, "get_project_by_id", fake_get_project_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)


def test_project_task_list_uses_redis_after_first_database_read(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    project: Project,
    owner: User,
    task: Task,
) -> None:
    redis = FakeRedis()
    app.dependency_overrides[get_redis_client] = lambda: redis
    configure_project_access(monkeypatch, project, owner)
    database_calls = 0

    async def fake_get_project_task_page(
        _: object,
        __: int,
        ___: TaskListParams,
    ) -> task_crud.TaskPage:
        nonlocal database_calls
        database_calls += 1
        return task_crud.TaskPage(items=[task], total=1)

    monkeypatch.setattr(task_crud, "get_project_task_page", fake_get_project_task_page)
    headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}

    first_response = client.get(
        f"/api/v1/projects/{project.id}/tasks?status=TODO&page=1&limit=5",
        headers=headers,
    )
    second_response = client.get(
        f"/api/v1/projects/{project.id}/tasks?status=TODO&page=1&limit=5",
        headers=headers,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert database_calls == 1
    assert redis.set_calls == 1
    assert redis.get_calls == 2


def test_cache_key_changes_with_filter_and_pagination() -> None:
    first_page = TaskListParams(status=TaskStatus.TODO, page=1, limit=20)
    second_page = TaskListParams(status=TaskStatus.TODO, page=2, limit=20)
    changed_filter = TaskListParams(status=TaskStatus.DONE, page=1, limit=20)

    assert build_project_task_list_cache_key(10, first_page) != build_project_task_list_cache_key(
        10,
        second_page,
    )
    assert build_project_task_list_cache_key(10, first_page) != build_project_task_list_cache_key(
        10,
        changed_filter,
    )


def test_create_task_invalidates_all_cached_project_task_pages(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    project: Project,
    owner: User,
    task: Task,
) -> None:
    redis = FakeRedis()
    redis.values[build_project_task_list_cache_key(project.id, TaskListParams())] = "cached"
    redis.values[build_project_task_list_cache_key(project.id, TaskListParams(page=2))] = "cached"
    app.dependency_overrides[get_redis_client] = lambda: redis
    configure_project_access(monkeypatch, project, owner)

    async def fake_create_task(_: object, __: int, ___: object, ____: int) -> Task:
        return task

    monkeypatch.setattr(task_crud, "create_task", fake_create_task)
    response = client.post(
        f"/api/v1/projects/{project.id}/tasks",
        headers={"Authorization": f"Bearer {create_access_token(owner.id)}"},
        json={"title": task.title},
    )

    assert response.status_code == 201
    assert redis.values == {}
    assert len(redis.deleted_keys) == 2


def test_redis_error_falls_back_to_database_response(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    project: Project,
    owner: User,
    task: Task,
) -> None:
    class BrokenRedis(FakeRedis):
        async def get(self, _: str) -> str | None:
            raise RedisConnectionError("Redis is offline")

        async def set(self, _: str, __: str, *, ex: int) -> None:
            raise RedisConnectionError("Redis is offline")

    app.dependency_overrides[get_redis_client] = BrokenRedis
    configure_project_access(monkeypatch, project, owner)

    async def fake_get_project_task_page(
        _: object,
        __: int,
        ___: TaskListParams,
    ) -> task_crud.TaskPage:
        return task_crud.TaskPage(items=[task], total=1)

    monkeypatch.setattr(task_crud, "get_project_task_page", fake_get_project_task_page)
    response = client.get(
        f"/api/v1/projects/{project.id}/tasks",
        headers={"Authorization": f"Bearer {create_access_token(owner.id)}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_assignment_invalidates_cache_and_schedules_notification(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    project: Project,
    owner: User,
    task: Task,
) -> None:
    editor = User(
        id=2,
        email="editor@example.com",
        full_name="Assigned Editor",
        hashed_password="test-only-hash",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime(2026, 7, 27, tzinfo=timezone.utc),
    )
    task.project = project
    redis = FakeRedis()
    redis.values[build_project_task_list_cache_key(project.id, TaskListParams())] = "cached"
    app.dependency_overrides[get_redis_client] = lambda: redis
    notifications: list[tuple[str, str, str]] = []

    async def fake_get_user_by_id(_: object, user_id: int) -> User:
        return owner if user_id == owner.id else editor

    async def fake_get_task_with_project(_: object, task_id: int) -> Task | None:
        return task if task_id == task.id else None

    async def fake_get_workspace_member(
        _: object,
        workspace_id: int,
        user_id: int,
    ) -> WorkspaceMember | None:
        if user_id not in {owner.id, editor.id}:
            return None
        return WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=WorkspaceRole.OWNER if user_id == owner.id else WorkspaceRole.EDITOR,
        )

    async def fake_assign_task(_: object, assigned_task: Task, assignee_id: int) -> Task:
        assigned_task.assignee_id = assignee_id
        return assigned_task

    async def fake_notification(
        *,
        recipient_email: str,
        task_title: str,
        project_name: str,
    ) -> None:
        notifications.append((recipient_email, task_title, project_name))

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(task_crud, "get_task_with_project", fake_get_task_with_project)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(task_crud, "assign_task", fake_assign_task)
    monkeypatch.setattr(task_router, "send_assignment_notification", fake_notification)

    response = client.post(
        f"/api/v1/tasks/{task.id}/assign",
        headers={"Authorization": f"Bearer {create_access_token(owner.id)}"},
        json={"assignee_id": editor.id},
    )

    assert response.status_code == 200
    assert redis.values == {}
    assert notifications == [(editor.email, task.title, project.name)]
