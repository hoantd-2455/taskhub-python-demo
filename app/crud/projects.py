from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.project import Project


async def get_projects(db: AsyncSession) -> list[Project]:
    """Return all projects in a stable order.

    Workspace filtering and pagination are intentionally introduced in later sessions.
    """

    result = await db.scalars(select(Project).order_by(Project.id))
    return list(result.all())


async def get_project_by_id(db: AsyncSession, project_id: int) -> Project | None:
    """Return one project when it exists, otherwise None."""

    statement = select(Project).where(Project.id == project_id)
    result = await db.scalars(statement)
    return result.one_or_none()


async def get_project_with_tasks(db: AsyncSession, project_id: int) -> Project | None:
    """Return a project and its tasks in one eager-loaded query."""

    statement = select(Project).options(joinedload(Project.tasks)).where(Project.id == project_id)
    result = await db.scalars(statement)
    return result.unique().one_or_none()
