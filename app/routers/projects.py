from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import projects as project_crud
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.authorization import ProjectAccess, require_project_roles
from app.models.enums import UserRole, WorkspaceRole
from app.models.user import User
from app.schemas.project import ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


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
