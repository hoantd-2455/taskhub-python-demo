from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.workspace import WorkspaceMember


async def get_accessible_projects(
    db: AsyncSession,
    *,
    user_id: int,
    is_admin: bool,
) -> list[Project]:
    """Return projects visible to the caller through workspace membership or admin role."""

    statement = select(Project).order_by(Project.id)
    if not is_admin:
        statement = statement.join(
            WorkspaceMember,
            WorkspaceMember.workspace_id == Project.workspace_id,
        ).where(WorkspaceMember.user_id == user_id)
    result = await db.scalars(statement)
    return list(result.all())


async def get_project_by_id(db: AsyncSession, project_id: int) -> Project | None:
    """Return one project when it exists, otherwise None."""

    statement = select(Project).where(Project.id == project_id)
    result = await db.scalars(statement)
    return result.one_or_none()
