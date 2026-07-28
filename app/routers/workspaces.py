from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import users as user_crud
from app.crud import workspaces as workspace_crud
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.authorization import (
    WorkspaceAccess,
    require_workspace_roles,
)
from app.models.enums import UserRole, WorkspaceRole
from app.models.user import User
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceResponse,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get(
    "",
    response_model=list[WorkspaceResponse],
    responses={401: {"description": "Authentication required"}},
)
async def list_workspaces(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkspaceResponse]:
    """List only workspaces visible to the authenticated caller."""

    workspaces = await workspace_crud.get_accessible_workspaces(
        db,
        user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )
    return [WorkspaceResponse.model_validate(workspace) for workspace in workspaces]


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={401: {"description": "Authentication required"}},
)
async def create_workspace(
    workspace_in: WorkspaceCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceResponse:
    """Create a workspace and make the caller its owner in one transaction."""

    workspace = await workspace_crud.create_workspace(db, workspace_in, current_user.id)
    return WorkspaceResponse.model_validate(workspace)


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace membership required"},
        404: {"description": "Workspace not found"},
    },
)
async def get_workspace(
    access: Annotated[
        WorkspaceAccess,
        Depends(
            require_workspace_roles(
                WorkspaceRole.OWNER,
                WorkspaceRole.EDITOR,
                WorkspaceRole.VIEWER,
            )
        ),
    ],
) -> WorkspaceResponse:
    """Read one workspace after membership validation."""

    return WorkspaceResponse.model_validate(access.workspace)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace owner role required"},
        404: {"description": "Workspace not found"},
    },
)
async def update_workspace(
    workspace_in: WorkspaceUpdate,
    access: Annotated[
        WorkspaceAccess,
        Depends(require_workspace_roles(WorkspaceRole.OWNER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceResponse:
    """Rename a workspace as its owner or an admin."""

    workspace = await workspace_crud.update_workspace(db, access.workspace, workspace_in)
    return WorkspaceResponse.model_validate(workspace)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace owner role required"},
        404: {"description": "Workspace not found"},
    },
)
async def delete_workspace(
    access: Annotated[
        WorkspaceAccess,
        Depends(require_workspace_roles(WorkspaceRole.OWNER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Delete a workspace and the resources it owns."""

    await workspace_crud.delete_workspace(db, access.workspace)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace owner role required"},
        404: {"description": "Workspace or user not found"},
        422: {"description": "Workspace owner role cannot be invited"},
    },
)
async def invite_workspace_member(
    member_in: WorkspaceMemberCreate,
    access: Annotated[
        WorkspaceAccess,
        Depends(require_workspace_roles(WorkspaceRole.OWNER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceMemberResponse:
    """Invite an active user as editor or viewer, or replace that member's role."""

    if member_in.role == WorkspaceRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Workspace owner role cannot be invited",
        )
    user = await user_crud.get_user_by_id(db, member_in.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    member = await workspace_crud.upsert_workspace_member(
        db,
        workspace_id=access.workspace.id,
        user_id=user.id,
        role=member_in.role,
    )
    return WorkspaceMemberResponse.model_validate(member)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace owner role required"},
        404: {"description": "Workspace or member not found"},
        422: {"description": "Workspace owner cannot be removed"},
    },
)
async def remove_workspace_member(
    user_id: int,
    access: Annotated[
        WorkspaceAccess,
        Depends(require_workspace_roles(WorkspaceRole.OWNER)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Remove a non-owner member from the workspace."""

    if user_id == access.workspace.owner_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Workspace owner cannot be removed",
        )
    member = await workspace_crud.get_workspace_member(db, access.workspace.id, user_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace member not found",
        )
    await workspace_crud.remove_workspace_member(db, member)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
