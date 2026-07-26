import asyncio

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.crud import comments as comment_crud
from app.crud import tasks as task_crud
from app.models.comment import Comment
from app.models.enums import TaskPriority, TaskStatus
from app.models.task import Task
from app.schemas.comment import CommentCreate


class FailingWriteSession:
    """Minimal async session double that fails exactly at database commit."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.rollback_count = 0

    def add(self, instance: object) -> None:
        self.added.append(instance)

    async def delete(self, instance: object) -> None:
        self.deleted.append(instance)

    async def commit(self) -> None:
        raise SQLAlchemyError("database write failed")

    async def rollback(self) -> None:
        self.rollback_count += 1

    async def refresh(self, _: object) -> None:
        raise AssertionError("refresh must not run after a failed commit")


def test_assign_task_rolls_back_when_commit_fails() -> None:
    session = FailingWriteSession()
    task = Task(
        id=30,
        project_id=10,
        assignee_id=2,
        title="Rollback assignment",
        status=TaskStatus.TODO,
        priority=TaskPriority.MEDIUM,
        created_by=1,
    )

    with pytest.raises(SQLAlchemyError, match="database write failed"):
        asyncio.run(task_crud.assign_task(session, task, assignee_id=3))  # type: ignore[arg-type]

    assert session.rollback_count == 1


def test_create_comment_rolls_back_when_commit_fails() -> None:
    session = FailingWriteSession()

    with pytest.raises(SQLAlchemyError, match="database write failed"):
        asyncio.run(
            comment_crud.create_comment(
                session,  # type: ignore[arg-type]
                task_id=30,
                author_id=2,
                comment_in=CommentCreate(content="This write must be rolled back."),
            )
        )

    assert len(session.added) == 1
    assert session.rollback_count == 1


def test_delete_comment_rolls_back_when_commit_fails() -> None:
    session = FailingWriteSession()
    comment = Comment(id=40, task_id=30, author_id=2, content="Delete rollback")

    with pytest.raises(SQLAlchemyError, match="database write failed"):
        asyncio.run(comment_crud.delete_comment(session, comment))  # type: ignore[arg-type]

    assert session.deleted == [comment]
    assert session.rollback_count == 1
