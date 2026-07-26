from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment
from app.schemas.comment import CommentCreate


async def get_comment_for_task(
    db: AsyncSession,
    task_id: int,
    comment_id: int,
) -> Comment | None:
    """Return a comment only when it belongs to the requested parent task."""

    result = await db.scalars(
        select(Comment).where(Comment.id == comment_id, Comment.task_id == task_id)
    )
    return result.one_or_none()


async def create_comment(
    db: AsyncSession,
    *,
    task_id: int,
    author_id: int,
    comment_in: CommentCreate,
) -> Comment:
    """Create a comment atomically and roll back failed writes."""

    comment = Comment(task_id=task_id, author_id=author_id, content=comment_in.content)
    db.add(comment)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(comment)
    return comment


async def delete_comment(db: AsyncSession, comment: Comment) -> None:
    """Delete a comment atomically and roll back failed writes."""

    await db.delete(comment)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
