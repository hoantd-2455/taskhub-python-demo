from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ProjectStatus
from app.schemas.base import ORMResponseModel


class ProjectCreate(BaseModel):
    """Validated input for a future project-creation endpoint."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    """Validated input for a future partial project update."""

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
