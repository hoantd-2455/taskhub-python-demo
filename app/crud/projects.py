from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.workspace import WorkspaceMember
from app.schemas.project import ProjectCreate, ProjectUpdate


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


async def create_project(
    db: AsyncSession,
    workspace_id: int,
    project_in: ProjectCreate,
) -> Project:
    """Create one project under its authorized workspace."""

    project = Project(workspace_id=workspace_id, **project_in.model_dump())
    db.add(project)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(project)
    return project


async def update_project(
    db: AsyncSession,
    project: Project,
    project_in: ProjectUpdate,
) -> Project:
    """Apply supplied project fields, including archive status."""

    for field_name, value in project_in.model_dump(exclude_unset=True).items():
        setattr(project, field_name, value)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project: Project) -> None:
    """Delete a project and cascading task/label resources atomically."""

    await db.delete(project)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
