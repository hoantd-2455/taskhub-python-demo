from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskPriority, TaskStatus
from app.schemas.base import ORMResponseModel


class TaskCreate(BaseModel):
    """Validated input for creating a task inside a project."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    assignee_id: int | None = Field(default=None, gt=0)
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: date | None = None


class TaskAssign(BaseModel):
    """Validated request to assign a task to one workspace member."""

    model_config = ConfigDict(extra="forbid")

    assignee_id: int = Field(gt=0)


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


class TaskListParams(BaseModel):
    """Optional filters and validated pagination for task-list endpoints."""

    model_config = ConfigDict(extra="forbid")

    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    assignee_id: int | None = Field(default=None, gt=0)
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class TaskListResponse(BaseModel):
    """One page of tasks together with the pagination metadata."""

    items: list[TaskResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=100)
