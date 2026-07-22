from datetime import datetime

from pydantic import ConfigDict, EmailStr, Field, model_validator

from app.models.enums import UserRole
from app.schemas.base import ORMResponseModel


class UserRegister(ORMResponseModel):
    """Data accepted when a person creates a TaskHub account."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(ORMResponseModel):
    """Mutable profile fields; PATCH keeps omitted values unchanged."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)


class PasswordChange(ORMResponseModel):
    """Current password proof and its replacement."""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_must_differ(self) -> "PasswordChange":
        if self.current_password == self.new_password:
            raise ValueError("New password must differ from current password")
        return self


class UserProfileResponse(ORMResponseModel):
    """Public user profile; intentionally excludes the password hash."""

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
