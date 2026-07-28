from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.crud import labels as label_crud
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
from app.models.workspace import Workspace, WorkspaceMember


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(user_id: int) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@example.com",
        full_name=f"User {user_id}",
        hashed_password="test-only-hash",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )


@pytest.fixture
def workspace() -> Workspace:
    return Workspace(
        id=10,
        name="Day 8 workspace",
        owner_id=1,
        created_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )


def test_owner_can_invite_editor_but_viewer_cannot_manage_members(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    workspace: Workspace,
) -> None:
    owner = make_user(1)
    editor = make_user(2)
    invited_roles: list[WorkspaceRole] = []
    caller_role = WorkspaceRole.OWNER

    async def fake_get_user_by_id(_: object, user_id: int) -> User:
        return owner if user_id == owner.id else editor

    async def fake_get_workspace_by_id(_: object, __: int) -> Workspace:
        return workspace

    async def fake_get_workspace_member(
        _: object,
        workspace_id: int,
        user_id: int,
    ) -> WorkspaceMember:
        return WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=caller_role,
        )

    async def fake_upsert_workspace_member(
        _: object,
        *,
        workspace_id: int,
        user_id: int,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        invited_roles.append(role)
        return WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role)

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_by_id", fake_get_workspace_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(workspace_crud, "upsert_workspace_member", fake_upsert_workspace_member)
    headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}

    invited = client.post(
        f"/api/v1/workspaces/{workspace.id}/members",
        headers=headers,
        json={"user_id": editor.id, "role": "EDITOR"},
    )
    caller_role = WorkspaceRole.VIEWER
    denied = client.post(
        f"/api/v1/workspaces/{workspace.id}/members",
        headers=headers,
        json={"user_id": editor.id, "role": "EDITOR"},
    )

    assert invited.status_code == 201
    assert invited_roles == [WorkspaceRole.EDITOR]
    assert denied.status_code == 403


def test_owner_can_create_project_and_editor_can_attach_same_project_label(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    workspace: Workspace,
) -> None:
    owner = make_user(1)
    project = Project(
        id=20,
        workspace_id=workspace.id,
        name="Day 8 project",
        description=None,
        status=ProjectStatus.ACTIVE,
        created_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    task = Task(
        id=30,
        project=project,
        project_id=project.id,
        assignee_id=None,
        title="Task with label",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        due_date=None,
        created_by=owner.id,
        created_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    label = Label(id=40, project_id=project.id, name="backend", color="#2563EB")
    labels_added: list[tuple[int, int]] = []

    async def fake_get_user_by_id(_: object, __: int) -> User:
        return owner

    async def fake_get_workspace_by_id(_: object, __: int) -> Workspace:
        return workspace

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

    async def fake_create_project(_: object, __: int, ___: object) -> Project:
        return project

    async def fake_get_task_with_project(_: object, __: int) -> Task:
        return task

    async def fake_get_label_for_project(_: object, __: int, ___: int) -> Label:
        return label

    async def fake_add_label_to_task(_: object, task_id: int, label_id: int) -> None:
        labels_added.append((task_id, label_id))

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_by_id", fake_get_workspace_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(project_crud, "create_project", fake_create_project)
    monkeypatch.setattr(task_crud, "get_task_with_project", fake_get_task_with_project)
    monkeypatch.setattr(label_crud, "get_label_for_project", fake_get_label_for_project)
    monkeypatch.setattr(label_crud, "add_label_to_task", fake_add_label_to_task)
    headers = {"Authorization": f"Bearer {create_access_token(owner.id)}"}

    created = client.post(
        f"/api/v1/workspaces/{workspace.id}/projects",
        headers=headers,
        json={"name": project.name},
    )
    attached = client.post(
        f"/api/v1/tasks/{task.id}/labels/{label.id}",
        headers=headers,
    )

    assert created.status_code == 201
    assert attached.status_code == 201
    assert labels_added == [(task.id, label.id)]


def test_cors_preflight_accepts_configured_local_frontend(client: TestClient) -> None:
    response = client.options(
        "/api/v1/projects",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
