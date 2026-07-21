from datetime import datetime

from app.models.enums import UserRole
from app.schemas.base import ORMResponseModel


class UserProfileResponse(ORMResponseModel):
    """Public user profile; intentionally excludes the password hash."""

    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
