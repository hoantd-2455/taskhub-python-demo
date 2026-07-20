from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.label import Label


async def get_labels(db: AsyncSession) -> list[Label]:
    """Return all labels in a stable order."""

    result = await db.scalars(select(Label).order_by(Label.id))
    return list(result.all())
