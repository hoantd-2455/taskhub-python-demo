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
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.schemas.task import TaskListParams


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def project() -> Project:
    return Project(
        id=10,
        workspace_id=20,
        name="RBAC project",
        description=None,
        status=ProjectStatus.ACTIVE,
        created_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )


@pytest.fixture
def task() -> Task:
    return Task(
        id=30,
        project_id=10,
        assignee_id=2,
        title="Filtered task",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        due_date=date(2026, 8, 1),
        created_by=1,
        created_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )


def make_user(user_id: int, role: UserRole = UserRole.MEMBER) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@example.com",
        full_name=f"User {user_id}",
        hashed_password="test-only-hash",
        role=role,
        is_active=True,
        created_at=datetime(2026, 7, 22, tzinfo=timezone.utc),
    )


def test_global_task_list_applies_filters_and_pagination(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    viewer = make_user(1)
    captured_params: list[TaskListParams] = []
    captured_is_admin: list[bool] = []

    async def fake_get_user_by_id(_: object, __: int) -> User:
        return viewer

    async def fake_get_accessible_task_page(
        _: object,
        *,
        user_id: int,
        is_admin: bool,
        params: TaskListParams,
    ) -> task_crud.TaskPage:
        assert user_id == viewer.id
        captured_is_admin.append(is_admin)
        captured_params.append(params)
        return task_crud.TaskPage(items=[task], total=1)

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(task_crud, "get_accessible_task_page", fake_get_accessible_task_page)

    response = client.get(
        "/api/v1/tasks?status=TODO&priority=HIGH&assignee_id=2&page=2&limit=5",
        headers={"Authorization": f"Bearer {create_access_token(viewer.id)}"},
    )
    invalid_page = client.get(
        "/api/v1/tasks?page=0&limit=101",
        headers={"Authorization": f"Bearer {create_access_token(viewer.id)}"},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["page"] == 2
    assert response.json()["limit"] == 5
    assert captured_params[0].status == TaskStatus.TODO
    assert captured_params[0].priority == TaskPriority.HIGH
    assert captured_params[0].assignee_id == 2
    assert captured_is_admin == [False]
    assert invalid_page.status_code == 422


def test_viewer_can_read_project_tasks_but_cannot_create(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    project: Project,
    task: Task,
) -> None:
    viewer = make_user(1)

    async def fake_get_user_by_id(_: object, __: int) -> User:
        return viewer

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
            role=WorkspaceRole.VIEWER,
        )

    async def fake_get_project_task_page(_: object, __: int, ___: object) -> task_crud.TaskPage:
        return task_crud.TaskPage(items=[task], total=1)

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(project_crud, "get_project_by_id", fake_get_project_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(task_crud, "get_project_task_page", fake_get_project_task_page)
    headers = {"Authorization": f"Bearer {create_access_token(viewer.id)}"}

    read_response = client.get("/api/v1/projects/10/tasks", headers=headers)
    create_response = client.post(
        "/api/v1/projects/10/tasks",
        headers=headers,
        json={"title": "Viewer must not create"},
    )

    assert read_response.status_code == 200
    assert create_response.status_code == 403
    assert create_response.json() == {"detail": "Insufficient workspace role"}


def test_non_member_cannot_read_project_tasks(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    project: Project,
) -> None:
    outsider = make_user(99)

    async def fake_get_user_by_id(_: object, __: int) -> User:
        return outsider

    async def fake_get_project_by_id(_: object, __: int) -> Project:
        return project

    async def fake_get_workspace_member(
        _: object,
        workspace_id: int,
        user_id: int,
    ) -> None:
        assert workspace_id == project.workspace_id
        assert user_id == outsider.id
        return None

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(project_crud, "get_project_by_id", fake_get_project_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)

    response = client.get(
        "/api/v1/projects/10/tasks",
        headers={"Authorization": f"Bearer {create_access_token(outsider.id)}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Workspace membership required"}


def test_admin_can_list_all_tasks_without_workspace_membership(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    admin = make_user(500, UserRole.ADMIN)
    captured_is_admin: list[bool] = []

    async def fake_get_user_by_id(_: object, __: int) -> User:
        return admin

    async def fake_get_accessible_task_page(
        _: object,
        *,
        user_id: int,
        is_admin: bool,
        params: TaskListParams,
    ) -> task_crud.TaskPage:
        assert user_id == admin.id
        captured_is_admin.append(is_admin)
        return task_crud.TaskPage(items=[task], total=1)

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(task_crud, "get_accessible_task_page", fake_get_accessible_task_page)

    response = client.get(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {create_access_token(admin.id)}"},
    )

    assert response.status_code == 200
    assert captured_is_admin == [True]


def test_editor_cannot_assign_task_to_user_outside_workspace(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    project: Project,
) -> None:
    editor = make_user(2)
    outsider = make_user(3)

    async def fake_get_user_by_id(_: object, user_id: int) -> User:
        return editor if user_id == editor.id else outsider

    async def fake_get_project_by_id(_: object, __: int) -> Project:
        return project

    async def fake_get_workspace_member(
        _: object,
        workspace_id: int,
        user_id: int,
    ) -> WorkspaceMember | None:
        if user_id == editor.id:
            return WorkspaceMember(
                workspace_id=workspace_id,
                user_id=editor.id,
                role=WorkspaceRole.EDITOR,
            )
        return None

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(project_crud, "get_project_by_id", fake_get_project_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)

    response = client.post(
        "/api/v1/projects/10/tasks",
        headers={"Authorization": f"Bearer {create_access_token(editor.id)}"},
        json={"title": "Invalid assignment", "assignee_id": outsider.id},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Assignee must be a workspace member"}
