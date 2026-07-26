from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import Select

from app.models.project import Project
from app.models.task import Task
from app.models.workspace import WorkspaceMember
from app.schemas.task import TaskCreate, TaskListParams


@dataclass(frozen=True)
class TaskPage:
    """Database result for a paginated task query."""

    items: list[Task]
    total: int


async def get_task_with_project(db: AsyncSession, task_id: int) -> Task | None:
    """Return one task with its project eagerly loaded for authorization checks."""

    result = await db.scalars(
        select(Task).options(joinedload(Task.project)).where(Task.id == task_id)
    )
    return result.one_or_none()


async def create_task(
    db: AsyncSession,
    project_id: int,
    task_in: TaskCreate,
    created_by: int,
) -> Task:
    """Create a task and roll back the transaction if the write fails."""

    task = Task(project_id=project_id, created_by=created_by, **task_in.model_dump())
    db.add(task)

    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise

    await db.refresh(task)
    return task


async def assign_task(db: AsyncSession, task: Task, assignee_id: int) -> Task:
    """Assign a task and roll back if the write cannot be committed."""

    task.assignee_id = assignee_id
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(task)
    return task


def apply_task_filters(statement: Select[Any], params: TaskListParams) -> Select[Any]:
    """Add optional task filters to a SQLAlchemy select statement."""

    if params.status is not None:
        statement = statement.where(Task.status == params.status)
    if params.priority is not None:
        statement = statement.where(Task.priority == params.priority)
    if params.assignee_id is not None:
        statement = statement.where(Task.assignee_id == params.assignee_id)
    return statement


async def get_project_task_page(
    db: AsyncSession,
    project_id: int,
    params: TaskListParams,
) -> TaskPage:
    """Return a filtered page of tasks from one project."""

    task_statement: Select[Any] = apply_task_filters(
        select(Task).where(Task.project_id == project_id),
        params,
    )
    count_statement: Select[Any] = apply_task_filters(
        select(func.count()).select_from(Task).where(Task.project_id == project_id),
        params,
    )
    total = await db.scalar(count_statement)
    paginated_statement = (
        task_statement.order_by(Task.id)
        .offset((params.page - 1) * params.limit)
        .limit(params.limit)
    )
    result = await db.scalars(paginated_statement)
    return TaskPage(items=list(result.all()), total=total or 0)


async def get_accessible_task_page(
    db: AsyncSession,
    *,
    user_id: int,
    is_admin: bool,
    params: TaskListParams,
) -> TaskPage:
    """Return only tasks in workspaces the caller may access, unless they are an admin."""

    task_statement: Select[Any] = select(Task).join(Project, Task.project_id == Project.id)
    count_statement: Select[Any] = (
        select(func.count())
        .select_from(Task)
        .join(
            Project,
            Task.project_id == Project.id,
        )
    )
    if not is_admin:
        membership_filter = WorkspaceMember.user_id == user_id
        task_statement = task_statement.join(
            WorkspaceMember,
            WorkspaceMember.workspace_id == Project.workspace_id,
        ).where(membership_filter)
        count_statement = count_statement.join(
            WorkspaceMember,
            WorkspaceMember.workspace_id == Project.workspace_id,
        ).where(membership_filter)

    task_statement = apply_task_filters(task_statement, params)
    count_statement = apply_task_filters(count_statement, params)
    total = await db.scalar(count_statement)
    paginated_statement = (
        task_statement.order_by(Task.id)
        .offset((params.page - 1) * params.limit)
        .limit(params.limit)
    )
    result = await db.scalars(paginated_statement)
    return TaskPage(items=list(result.all()), total=total or 0)
