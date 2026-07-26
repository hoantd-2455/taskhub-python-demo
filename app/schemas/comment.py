from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import ORMResponseModel


class CommentCreate(BaseModel):
    """Validated content for a new task comment."""

    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=5000)


class CommentResponse(ORMResponseModel):
    """Public representation of a task comment."""

    id: int
    task_id: int
    author_id: int
    content: str
    created_at: datetime
