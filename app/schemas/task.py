from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import TaskPriority, TaskStatus
from app.schemas.base import ORMResponseModel


class TaskCreate(BaseModel):
    """Validated input for creating a task inside a project."""

    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    assignee_id: int | None = Field(default=None, gt=0)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None
    created_by: int = Field(gt=0)


class TaskSummaryResponse(ORMResponseModel):
    """Task fields embedded in a project response."""

    id: int
    title: str
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None


class TaskResponse(TaskSummaryResponse):
    """Full public task representation returned after creation."""

    project_id: int
    assignee_id: int | None
    description: str | None
    created_by: int
    created_at: datetime
