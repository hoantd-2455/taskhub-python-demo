from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis_client
from app.crud import labels as label_crud
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.authorization import ProjectAccess, require_project_roles
from app.models.enums import UserRole, WorkspaceRole
from app.models.user import User
from app.schemas.label import LabelCreate, LabelResponse, LabelUpdate
from app.services import task_cache

router = APIRouter(prefix="/labels", tags=["labels"])
project_labels_router = APIRouter(prefix="/projects/{project_id}/labels", tags=["labels"])


@router.get(
    "",
    response_model=list[LabelResponse],
    responses={401: {"description": "Authentication required"}},
)
async def list_labels(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LabelResponse]:
    """List labels only from projects the current user may read."""

    labels = await label_crud.get_accessible_labels(
        db,
        user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )
    return [LabelResponse.model_validate(label) for label in labels]


@project_labels_router.get(
    "",
    response_model=list[LabelResponse],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace membership or read role required"},
        404: {"description": "Project not found"},
    },
)
async def list_project_labels(
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
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LabelResponse]:
    """List labels only after validating access to the parent project workspace."""

    labels = await label_crud.get_labels_for_project(db, access.project.id)
    return [LabelResponse.model_validate(label) for label in labels]


@project_labels_router.post(
    "",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Owner or editor role required"},
        404: {"description": "Project not found"},
        409: {"description": "Label name already exists in project"},
    },
)
async def create_label(
    label_in: LabelCreate,
    access: Annotated[
        ProjectAccess,
        Depends(require_project_roles(WorkspaceRole.OWNER, WorkspaceRole.EDITOR)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> LabelResponse:
    """Create a project label and invalidate task-list cache variants."""

    try:
        label = await label_crud.create_label(db, access.project.id, label_in)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Label name already exists in project",
        ) from exc
    await task_cache.invalidate_project_task_lists(redis, access.project.id)
    return LabelResponse.model_validate(label)


@project_labels_router.patch(
    "/{label_id}",
    response_model=LabelResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Owner or editor role required"},
        404: {"description": "Project or label not found"},
        409: {"description": "Label name already exists in project"},
    },
)
async def update_label(
    label_id: int,
    label_in: LabelUpdate,
    access: Annotated[
        ProjectAccess,
        Depends(require_project_roles(WorkspaceRole.OWNER, WorkspaceRole.EDITOR)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> LabelResponse:
    """Update a label only when it belongs to the authorized project."""

    label = await label_crud.get_label_for_project(db, access.project.id, label_id)
    if label is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    try:
        label = await label_crud.update_label(db, label, label_in)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Label name already exists in project",
        ) from exc
    await task_cache.invalidate_project_task_lists(redis, access.project.id)
    return LabelResponse.model_validate(label)


@project_labels_router.delete(
    "/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Owner or editor role required"},
        404: {"description": "Project or label not found"},
    },
)
async def delete_label(
    label_id: int,
    access: Annotated[
        ProjectAccess,
        Depends(require_project_roles(WorkspaceRole.OWNER, WorkspaceRole.EDITOR)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> Response:
    """Delete a label from its project and invalidate cached task pages."""

    label = await label_crud.get_label_for_project(db, access.project.id, label_id)
    if label is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    await label_crud.delete_label(db, label)
    await task_cache.invalidate_project_task_lists(redis, access.project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
