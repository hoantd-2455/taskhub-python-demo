from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Return one user by identifier when it exists."""

    result = await db.scalars(select(User).where(User.id == user_id))
    return result.one_or_none()


async def get_user_profile(db: AsyncSession, user_id: int) -> User | None:
    """Return data needed by the public profile endpoint."""

    return await get_user_by_id(db, user_id)
