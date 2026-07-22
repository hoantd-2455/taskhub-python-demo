from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.schemas.task import TaskCreate


async def create_task(db: AsyncSession, project_id: int, task_in: TaskCreate) -> Task:
    """Create a task and roll back the transaction if the write fails."""

    task = Task(project_id=project_id, **task_in.model_dump())
    db.add(task)

    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise

    await db.refresh(task)
    return task
