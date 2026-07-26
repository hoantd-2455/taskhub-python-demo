from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import projects as project_crud
from app.crud import tasks as task_crud
from app.crud import workspaces as workspace_crud
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.enums import UserRole, WorkspaceRole
from app.models.project import Project
from app.models.task import Task
from app.models.user import User


@dataclass(frozen=True)
class ProjectAccess:
    """Authenticated caller's access context for a project and its workspace."""

    project: Project
    user: User
    workspace_role: WorkspaceRole | None

    @property
    def is_admin(self) -> bool:
        return self.user.role == UserRole.ADMIN


@dataclass(frozen=True)
class TaskAccess:
    """Authenticated caller's access context for a task and its parent workspace."""

    task: Task
    project: Project
    user: User
    workspace_role: WorkspaceRole | None

    @property
    def is_admin(self) -> bool:
        return self.user.role == UserRole.ADMIN


async def get_project_access(
    project_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectAccess:
    """Verify that the caller belongs to the parent workspace of a project."""

    project = await project_crud.get_project_by_id(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if current_user.role == UserRole.ADMIN:
        return ProjectAccess(project=project, user=current_user, workspace_role=None)

    membership = await workspace_crud.get_workspace_member(
        db,
        workspace_id=project.workspace_id,
        user_id=current_user.id,
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace membership required",
        )
    return ProjectAccess(project=project, user=current_user, workspace_role=membership.role)


def require_project_roles(
    *allowed_roles: WorkspaceRole,
) -> Callable[[ProjectAccess], Awaitable[ProjectAccess]]:
    """Create a dependency that permits an admin or a selected workspace role."""

    async def dependency(
        access: Annotated[ProjectAccess, Depends(get_project_access)],
    ) -> ProjectAccess:
        if access.is_admin or access.workspace_role in allowed_roles:
            return access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient workspace role",
        )

    return dependency


async def get_task_access(
    task_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskAccess:
    """Verify access to a task through the task's eagerly loaded parent project."""

    task = await task_crud.get_task_with_project(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    project = task.project
    if current_user.role == UserRole.ADMIN:
        return TaskAccess(task=task, project=project, user=current_user, workspace_role=None)

    membership = await workspace_crud.get_workspace_member(
        db,
        workspace_id=project.workspace_id,
        user_id=current_user.id,
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace membership required",
        )
    return TaskAccess(
        task=task,
        project=project,
        user=current_user,
        workspace_role=membership.role,
    )


def require_task_roles(
    *allowed_roles: WorkspaceRole,
) -> Callable[[TaskAccess], Awaitable[TaskAccess]]:
    """Create a dependency that permits an admin or selected roles for a task."""

    async def dependency(
        access: Annotated[TaskAccess, Depends(get_task_access)],
    ) -> TaskAccess:
        if access.is_admin or access.workspace_role in allowed_roles:
            return access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient workspace role",
        )

    return dependency
