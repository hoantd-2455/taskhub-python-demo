from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ProjectStatus
from app.schemas.base import ORMResponseModel
from app.schemas.task import TaskSummaryResponse


class ProjectCreate(BaseModel):
    """Validated input for creating a project inside a workspace."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    """Validated input for a partial project update or archive operation."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus | None = None


class ProjectResponse(ORMResponseModel):
    """Public project representation returned by the API."""

    id: int
    workspace_id: int
    name: str
    description: str | None
    status: ProjectStatus
    created_at: datetime


class ProjectWithTasksResponse(ProjectResponse):
    """Project response with an eagerly loaded task collection."""

    tasks: list[TaskSummaryResponse]
