from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis_client
from app.crud import projects as project_crud
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.authorization import (
    ProjectAccess,
    WorkspaceAccess,
    require_project_roles,
    require_workspace_roles,
)
from app.models.enums import UserRole, WorkspaceRole
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services import task_cache

router = APIRouter(prefix="/projects", tags=["projects"])
workspace_projects_router = APIRouter(
    prefix="/workspaces/{workspace_id}/projects",
    tags=["projects"],
)


@router.get(
    "",
    response_model=list[ProjectResponse],
    responses={401: {"description": "Authentication required"}},
)
async def list_projects(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ProjectResponse]:
    """List only projects visible through the caller's workspace membership."""

    projects = await project_crud.get_accessible_projects(
        db,
        user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace membership or read role required"},
        404: {"description": "Project not found"},
    },
)
async def get_project(
    project_id: int,
    access: Annotated[
        ProjectAccess,
        Depends(
            require_project_roles(
                WorkspaceRole.OWNER,
                WorkspaceRole.EDITOR,
                WorkspaceRole.VIEWER,
            )
        ),
    ],
) -> ProjectResponse:
    """Get one project after checking access to its parent workspace."""

    return ProjectResponse.model_validate(access.project)


@workspace_projects_router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace owner role required"},
        404: {"description": "Workspace not found"},
        409: {"description": "Project name already exists in workspace"},
    },
)
async def create_project(
    project_in: ProjectCreate,
    access: Annotated[
        WorkspaceAccess,
        Depends(require_workspace_roles(WorkspaceRole.OWNER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    """Create a project as the workspace owner or system admin."""

    try:
        project = await project_crud.create_project(db, access.workspace.id, project_in)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project name already exists in workspace",
        ) from exc
    return ProjectResponse.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace owner role required"},
        404: {"description": "Project not found"},
        409: {"description": "Project name already exists in workspace"},
    },
)
async def update_project(
    project_in: ProjectUpdate,
    access: Annotated[
        ProjectAccess,
        Depends(require_project_roles(WorkspaceRole.OWNER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectResponse:
    """Update or archive a project as its workspace owner or system admin."""

    try:
        project = await project_crud.update_project(db, access.project, project_in)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project name already exists in workspace",
        ) from exc
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace owner role required"},
        404: {"description": "Project not found"},
    },
)
async def delete_project(
    access: Annotated[
        ProjectAccess,
        Depends(require_project_roles(WorkspaceRole.OWNER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> Response:
    """Delete a project and invalidate its cached task-list pages."""

    await project_crud.delete_project(db, access.project)
    await task_cache.invalidate_project_task_lists(redis, access.project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
