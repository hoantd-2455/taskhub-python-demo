from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.crud import comments as comment_crud
from app.crud import tasks as task_crud
from app.crud import users as user_crud
from app.crud import workspaces as workspace_crud
from app.main import app
from app.models.comment import Comment
from app.models.enums import ProjectStatus, TaskPriority, TaskStatus, UserRole, WorkspaceRole
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import WorkspaceMember


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def make_user(user_id: int, role: UserRole = UserRole.MEMBER) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@example.com",
        full_name=f"User {user_id}",
        hashed_password="test-only-hash",
        role=role,
        is_active=True,
        created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )


@pytest.fixture
def task() -> Task:
    project = Project(
        id=10,
        workspace_id=20,
        name="Day 6 project",
        description=None,
        status=ProjectStatus.ACTIVE,
        created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    return Task(
        id=30,
        project=project,
        project_id=project.id,
        assignee_id=2,
        title="Review transaction handling",
        description=None,
        status=TaskStatus.TODO,
        priority=TaskPriority.HIGH,
        due_date=None,
        created_by=1,
        created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )


def patch_task_access(
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
    current_user: User,
    workspace_role: WorkspaceRole | None,
) -> None:
    async def fake_get_user_by_id(_: object, __: int) -> User:
        return current_user

    async def fake_get_task_with_project(_: object, task_id: int) -> Task | None:
        return task if task_id == task.id else None

    async def fake_get_workspace_member(
        _: object,
        workspace_id: int,
        user_id: int,
    ) -> WorkspaceMember | None:
        if user_id != current_user.id or workspace_role is None:
            return None
        return WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=workspace_role,
        )

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(task_crud, "get_task_with_project", fake_get_task_with_project)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)


def test_editor_can_assign_task_to_workspace_member(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    editor = make_user(2)
    assignee = make_user(3)
    patch_task_access(monkeypatch, task, editor, WorkspaceRole.EDITOR)
    assigned_to: list[int] = []

    async def fake_get_user_by_id(_: object, user_id: int) -> User:
        return editor if user_id == editor.id else assignee

    async def fake_get_workspace_member(
        _: object,
        workspace_id: int,
        user_id: int,
    ) -> WorkspaceMember | None:
        if user_id in {editor.id, assignee.id}:
            return WorkspaceMember(
                workspace_id=workspace_id,
                user_id=user_id,
                role=WorkspaceRole.EDITOR,
            )
        return None

    async def fake_assign_task(_: object, assigned_task: Task, assignee_id: int) -> Task:
        assigned_to.append(assignee_id)
        assigned_task.assignee_id = assignee_id
        return assigned_task

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)
    monkeypatch.setattr(task_crud, "assign_task", fake_assign_task)

    response = client.post(
        f"/api/v1/tasks/{task.id}/assign",
        headers={"Authorization": f"Bearer {create_access_token(editor.id)}"},
        json={"assignee_id": assignee.id},
    )

    assert response.status_code == 200
    assert response.json()["assignee_id"] == assignee.id
    assert assigned_to == [assignee.id]


def test_assignment_rejects_user_outside_workspace(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    editor = make_user(2)
    outsider = make_user(99)
    patch_task_access(monkeypatch, task, editor, WorkspaceRole.EDITOR)

    async def fake_get_user_by_id(_: object, user_id: int) -> User:
        return editor if user_id == editor.id else outsider

    async def fake_get_workspace_member(
        _: object,
        workspace_id: int,
        user_id: int,
    ) -> WorkspaceMember | None:
        if user_id == editor.id:
            return WorkspaceMember(
                workspace_id=workspace_id,
                user_id=user_id,
                role=WorkspaceRole.EDITOR,
            )
        return None

    monkeypatch.setattr(user_crud, "get_user_by_id", fake_get_user_by_id)
    monkeypatch.setattr(workspace_crud, "get_workspace_member", fake_get_workspace_member)

    response = client.post(
        f"/api/v1/tasks/{task.id}/assign",
        headers={"Authorization": f"Bearer {create_access_token(editor.id)}"},
        json={"assignee_id": outsider.id},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Assignee must be a workspace member"}


def test_viewer_cannot_assign_or_add_comment(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    viewer = make_user(4)
    patch_task_access(monkeypatch, task, viewer, WorkspaceRole.VIEWER)
    headers = {"Authorization": f"Bearer {create_access_token(viewer.id)}"}

    assign_response = client.post(
        f"/api/v1/tasks/{task.id}/assign",
        headers=headers,
        json={"assignee_id": viewer.id},
    )
    comment_response = client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers=headers,
        json={"content": "Viewer cannot add this."},
    )

    assert assign_response.status_code == 403
    assert comment_response.status_code == 403


def test_editor_can_add_comment(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    editor = make_user(2)
    patch_task_access(monkeypatch, task, editor, WorkspaceRole.EDITOR)
    created: list[Comment] = []

    async def fake_create_comment(
        _: object,
        *,
        task_id: int,
        author_id: int,
        comment_in: object,
    ) -> Comment:
        comment = Comment(
            id=40,
            task_id=task_id,
            author_id=author_id,
            content=comment_in.content,
            created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
        )
        created.append(comment)
        return comment

    monkeypatch.setattr(comment_crud, "create_comment", fake_create_comment)
    response = client.post(
        f"/api/v1/tasks/{task.id}/comments",
        headers={"Authorization": f"Bearer {create_access_token(editor.id)}"},
        json={"content": "Transaction behaviour reviewed."},
    )

    assert response.status_code == 201
    assert response.json()["author_id"] == editor.id
    assert created[0].task_id == task.id


def test_comment_author_can_delete_own_comment_as_viewer(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    viewer = make_user(4)
    comment = Comment(
        id=40,
        task_id=task.id,
        author_id=viewer.id,
        content="My earlier comment",
        created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    patch_task_access(monkeypatch, task, viewer, WorkspaceRole.VIEWER)
    deleted: list[int] = []

    async def fake_get_comment_for_task(_: object, __: int, ___: int) -> Comment:
        return comment

    async def fake_delete_comment(_: object, deleted_comment: Comment) -> None:
        deleted.append(deleted_comment.id)

    monkeypatch.setattr(comment_crud, "get_comment_for_task", fake_get_comment_for_task)
    monkeypatch.setattr(comment_crud, "delete_comment", fake_delete_comment)
    response = client.delete(
        f"/api/v1/tasks/{task.id}/comments/{comment.id}",
        headers={"Authorization": f"Bearer {create_access_token(viewer.id)}"},
    )

    assert response.status_code == 204
    assert deleted == [comment.id]


def test_editor_cannot_delete_another_authors_comment(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    editor = make_user(2)
    comment = Comment(
        id=40,
        task_id=task.id,
        author_id=3,
        content="Owner comment",
        created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    patch_task_access(monkeypatch, task, editor, WorkspaceRole.EDITOR)

    async def fake_get_comment_for_task(_: object, __: int, ___: int) -> Comment:
        return comment

    monkeypatch.setattr(comment_crud, "get_comment_for_task", fake_get_comment_for_task)
    response = client.delete(
        f"/api/v1/tasks/{task.id}/comments/{comment.id}",
        headers={"Authorization": f"Bearer {create_access_token(editor.id)}"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Comment deletion is not permitted"}


def test_owner_can_delete_another_authors_comment(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    owner = make_user(1)
    comment = Comment(
        id=40,
        task_id=task.id,
        author_id=2,
        content="Editor comment",
        created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    patch_task_access(monkeypatch, task, owner, WorkspaceRole.OWNER)
    deleted: list[int] = []

    async def fake_get_comment_for_task(_: object, __: int, ___: int) -> Comment:
        return comment

    async def fake_delete_comment(_: object, deleted_comment: Comment) -> None:
        deleted.append(deleted_comment.id)

    monkeypatch.setattr(comment_crud, "get_comment_for_task", fake_get_comment_for_task)
    monkeypatch.setattr(comment_crud, "delete_comment", fake_delete_comment)
    response = client.delete(
        f"/api/v1/tasks/{task.id}/comments/{comment.id}",
        headers={"Authorization": f"Bearer {create_access_token(owner.id)}"},
    )

    assert response.status_code == 204
    assert deleted == [comment.id]


def test_admin_can_delete_another_authors_comment(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    admin = make_user(500, UserRole.ADMIN)
    comment = Comment(
        id=40,
        task_id=task.id,
        author_id=2,
        content="Editor comment",
        created_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
    )
    patch_task_access(monkeypatch, task, admin, None)
    deleted: list[int] = []

    async def fake_get_comment_for_task(_: object, __: int, ___: int) -> Comment:
        return comment

    async def fake_delete_comment(_: object, deleted_comment: Comment) -> None:
        deleted.append(deleted_comment.id)

    monkeypatch.setattr(comment_crud, "get_comment_for_task", fake_get_comment_for_task)
    monkeypatch.setattr(comment_crud, "delete_comment", fake_delete_comment)
    response = client.delete(
        f"/api/v1/tasks/{task.id}/comments/{comment.id}",
        headers={"Authorization": f"Bearer {create_access_token(admin.id)}"},
    )

    assert response.status_code == 204
    assert deleted == [comment.id]


def test_delete_rejects_comment_from_another_task(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    task: Task,
) -> None:
    owner = make_user(1)
    patch_task_access(monkeypatch, task, owner, WorkspaceRole.OWNER)

    async def fake_get_comment_for_task(_: object, __: int, ___: int) -> None:
        return None

    monkeypatch.setattr(comment_crud, "get_comment_for_task", fake_get_comment_for_task)
    response = client.delete(
        f"/api/v1/tasks/{task.id}/comments/999",
        headers={"Authorization": f"Bearer {create_access_token(owner.id)}"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Comment not found"}
