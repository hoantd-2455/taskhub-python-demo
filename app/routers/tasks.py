from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis_client
from app.crud import comments as comment_crud
from app.crud import labels as label_crud
from app.crud import tasks as task_crud
from app.crud import users as user_crud
from app.crud import workspaces as workspace_crud
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.dependencies.authorization import (
    ProjectAccess,
    TaskAccess,
    require_project_roles,
    require_task_roles,
)
from app.models.enums import UserRole, WorkspaceRole
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentResponse
from app.schemas.label import LabelResponse
from app.schemas.task import (
    TaskAssign,
    TaskCreate,
    TaskListParams,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)
from app.services import task_cache
from app.services.notifications import send_assignment_notification

router = APIRouter(prefix="/tasks", tags=["tasks"])
project_tasks_router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


def task_page_response(
    page: task_crud.TaskPage,
    params: TaskListParams,
) -> TaskListResponse:
    """Serialize a CRUD task page without exposing ORM entities directly."""

    return TaskListResponse(
        items=[TaskResponse.model_validate(task) for task in page.items],
        total=page.total,
        page=params.page,
        limit=params.limit,
    )


@router.get(
    "",
    response_model=TaskListResponse,
    responses={401: {"description": "Authentication required"}},
)
async def list_accessible_tasks(
    params: Annotated[TaskListParams, Depends()],
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskListResponse:
    """List filtered tasks from workspaces available to the current user."""

    page = await task_crud.get_accessible_task_page(
        db,
        user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
        params=params,
    )
    return task_page_response(page, params)


@project_tasks_router.get(
    "",
    response_model=TaskListResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Workspace membership or read role required"},
        404: {"description": "Project not found"},
    },
)
async def list_project_tasks(
    params: Annotated[TaskListParams, Depends()],
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
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> TaskListResponse:
    """List one workspace project's tasks with filtering and validated pagination."""

    cache_key = task_cache.build_project_task_list_cache_key(access.project.id, params)
    cached_response = await task_cache.get_cached_project_task_list(redis, cache_key)
    if cached_response is not None:
        return cached_response
    page = await task_crud.get_project_task_page(db, access.project.id, params)
    response = task_page_response(page, params)
    await task_cache.cache_project_task_list(redis, cache_key, response)
    return response


@project_tasks_router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Owner or editor role required"},
        404: {"description": "Project or assignee not found"},
        422: {"description": "Assignee is outside the workspace"},
    },
)
async def create_task_for_project(
    task_in: TaskCreate,
    access: Annotated[
        ProjectAccess,
        Depends(require_project_roles(WorkspaceRole.OWNER, WorkspaceRole.EDITOR)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> TaskResponse:
    """Create a task for an existing project as the authenticated user."""

    if task_in.assignee_id is not None:
        assignee = await user_crud.get_user_by_id(db, task_in.assignee_id)
        if assignee is None or not assignee.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")
        assignee_membership = await workspace_crud.get_workspace_member(
            db,
            workspace_id=access.project.workspace_id,
            user_id=assignee.id,
        )
        if assignee_membership is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Assignee must be a workspace member",
            )

    task = await task_crud.create_task(db, access.project.id, task_in, access.user.id)
    await task_cache.invalidate_project_task_lists(redis, access.project.id)
    return TaskResponse.model_validate(task)


@router.post(
    "/{task_id}/assign",
    response_model=TaskResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Owner or editor role required"},
        404: {"description": "Task or assignee not found"},
        422: {"description": "Assignee is outside the workspace"},
    },
)
async def assign_task(
    assignment: TaskAssign,
    background_tasks: BackgroundTasks,
    access: Annotated[
        TaskAccess,
        Depends(require_task_roles(WorkspaceRole.OWNER, WorkspaceRole.EDITOR)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> TaskResponse:
    """Assign a task to an active member of the task's parent workspace."""

    assignee = await user_crud.get_user_by_id(db, assignment.assignee_id)
    if assignee is None or not assignee.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")
    membership = await workspace_crud.get_workspace_member(
        db,
        workspace_id=access.project.workspace_id,
        user_id=assignee.id,
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Assignee must be a workspace member",
        )
    task = await task_crud.assign_task(db, access.task, assignee.id)
    await task_cache.invalidate_project_task_lists(redis, access.project.id)
    background_tasks.add_task(
        send_assignment_notification,
        recipient_email=assignee.email,
        task_title=task.title,
        project_name=access.project.name,
    )
    return TaskResponse.model_validate(task)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Owner or editor role required"},
        404: {"description": "Task or assignee not found"},
        422: {"description": "Assignee is outside the workspace"},
    },
)
async def update_task(
    task_in: TaskUpdate,
    background_tasks: BackgroundTasks,
    access: Annotated[
        TaskAccess,
        Depends(require_task_roles(WorkspaceRole.OWNER, WorkspaceRole.EDITOR)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> TaskResponse:
    """Update task fields after validating any newly selected assignee."""

    assignee: User | None = None
    if "assignee_id" in task_in.model_fields_set and task_in.assignee_id is not None:
        assignee = await user_crud.get_user_by_id(db, task_in.assignee_id)
        if assignee is None or not assignee.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")
        membership = await workspace_crud.get_workspace_member(
            db,
            workspace_id=access.project.workspace_id,
            user_id=assignee.id,
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Assignee must be a workspace member",
            )
    task = await task_crud.update_task(db, access.task, task_in)
    await task_cache.invalidate_project_task_lists(redis, access.project.id)
    if assignee is not None:
        background_tasks.add_task(
            send_assignment_notification,
            recipient_email=assignee.email,
            task_title=task.title,
            project_name=access.project.name,
        )
    return TaskResponse.model_validate(task)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Owner or editor role required"},
        404: {"description": "Task not found"},
    },
)
async def delete_task(
    access: Annotated[
        TaskAccess,
        Depends(require_task_roles(WorkspaceRole.OWNER, WorkspaceRole.EDITOR)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> Response:
    """Delete a task and invalidate cached task-list pages for its project."""

    await task_crud.delete_task(db, access.task)
    await task_cache.invalidate_project_task_lists(redis, access.project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{task_id}/labels/{label_id}",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Owner or editor role required"},
        404: {"description": "Task or label not found"},
    },
)
async def add_label_to_task(
    label_id: int,
    access: Annotated[
        TaskAccess,
        Depends(require_task_roles(WorkspaceRole.OWNER, WorkspaceRole.EDITOR)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> LabelResponse:
    """Attach only a label from the task's own project."""

    label = await label_crud.get_label_for_project(db, access.project.id, label_id)
    if label is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    await label_crud.add_label_to_task(db, access.task.id, label.id)
    await task_cache.invalidate_project_task_lists(redis, access.project.id)
    return LabelResponse.model_validate(label)


@router.delete(
    "/{task_id}/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Owner or editor role required"},
        404: {"description": "Task, label, or task-label link not found"},
    },
)
async def remove_label_from_task(
    label_id: int,
    access: Annotated[
        TaskAccess,
        Depends(require_task_roles(WorkspaceRole.OWNER, WorkspaceRole.EDITOR)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis | None, Depends(get_redis_client)],
) -> Response:
    """Remove a label link only when the label belongs to the task project."""

    label = await label_crud.get_label_for_project(db, access.project.id, label_id)
    if label is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Label not found")
    removed = await label_crud.remove_label_from_task(db, access.task.id, label.id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task label not found")
    await task_cache.invalidate_project_task_lists(redis, access.project.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{task_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Owner or editor role required"},
        404: {"description": "Task not found"},
    },
)
async def add_comment(
    comment_in: CommentCreate,
    access: Annotated[
        TaskAccess,
        Depends(require_task_roles(WorkspaceRole.OWNER, WorkspaceRole.EDITOR)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CommentResponse:
    """Add a comment as an owner, editor or system admin in the task workspace."""

    comment = await comment_crud.create_comment(
        db,
        task_id=access.task.id,
        author_id=access.user.id,
        comment_in=comment_in,
    )
    return CommentResponse.model_validate(comment)


@router.delete(
    "/{task_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Comment author, workspace owner or admin required"},
        404: {"description": "Task or comment not found"},
    },
)
async def remove_comment(
    comment_id: int,
    access: Annotated[
        TaskAccess,
        Depends(
            require_task_roles(
                WorkspaceRole.OWNER,
                WorkspaceRole.EDITOR,
                WorkspaceRole.VIEWER,
            )
        ),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Delete a comment only as its author, the workspace owner or an admin."""

    comment = await comment_crud.get_comment_for_task(db, access.task.id, comment_id)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    is_workspace_owner = access.workspace_role == WorkspaceRole.OWNER
    if comment.author_id != access.user.id and not access.is_admin and not is_workspace_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Comment deletion is not permitted",
        )
    await comment_crud.delete_comment(db, comment)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
