from pydantic import BaseModel, ConfigDict


class ORMResponseModel(BaseModel):
    """Base response schema that can validate SQLAlchemy model instances."""

    model_config = ConfigDict(from_attributes=True)
