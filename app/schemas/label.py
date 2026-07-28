from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import ORMResponseModel


class LabelCreate(BaseModel):
    """Validated input for a project label."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class LabelUpdate(BaseModel):
    """Validated input for a partial label update."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class LabelResponse(ORMResponseModel):
    """Public label representation returned by the API."""

    id: int
    project_id: int
    name: str
    color: str
