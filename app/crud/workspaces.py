from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import WorkspaceMember


async def get_workspace_member(
    db: AsyncSession,
    workspace_id: int,
    user_id: int,
) -> WorkspaceMember | None:
    """Return a user's membership and role for one workspace."""

    result = await db.scalars(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    return result.one_or_none()
