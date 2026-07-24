from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label
from app.models.project import Project
from app.models.workspace import WorkspaceMember


async def get_accessible_labels(
    db: AsyncSession,
    *,
    user_id: int,
    is_admin: bool,
) -> list[Label]:
    """Return labels only from projects the caller may read."""

    statement = select(Label).join(Project, Label.project_id == Project.id).order_by(Label.id)
    if not is_admin:
        statement = statement.join(
            WorkspaceMember,
            WorkspaceMember.workspace_id == Project.workspace_id,
        ).where(WorkspaceMember.user_id == user_id)
    result = await db.scalars(statement)
    return list(result.all())
