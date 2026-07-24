from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import projects as project_crud
from app.crud import tasks as task_crud
from app.crud import users as user_crud
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.task import TaskCreate, TaskResponse

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task_for_project(
    project_id: int,
    task_in: TaskCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TaskResponse:
    """Create a task for an existing project as the authenticated user."""

    project = await project_crud.get_project_by_id(db, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if task_in.assignee_id is not None:
        assignee = await user_crud.get_user_by_id(db, task_in.assignee_id)
        if assignee is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee not found")

    task = await task_crud.create_task(db, project_id, task_in, current_user.id)
    return TaskResponse.model_validate(task)
