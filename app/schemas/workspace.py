from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import WorkspaceRole
from app.schemas.base import ORMResponseModel


class WorkspaceCreate(BaseModel):
    """Validated input for a new workspace owned by the current user."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


class WorkspaceUpdate(BaseModel):
    """Mutable workspace fields; omitted fields remain unchanged."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)


class WorkspaceMemberCreate(BaseModel):
    """A member invitation or role replacement made by a workspace owner."""

    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(gt=0)
    role: WorkspaceRole


class WorkspaceResponse(ORMResponseModel):
    """Public workspace representation."""

    id: int
    name: str
    owner_id: int
    created_at: datetime


class WorkspaceMemberResponse(ORMResponseModel):
    """Public membership representation without exposing user credentials."""

    workspace_id: int
    user_id: int
    role: WorkspaceRole
