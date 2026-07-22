from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import labels as label_crud
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.label import LabelResponse

router = APIRouter(prefix="/labels", tags=["labels"])


@router.get(
    "",
    response_model=list[LabelResponse],
    responses={401: {"description": "Authentication required"}},
)
async def list_labels(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LabelResponse]:
    """List labels only from projects the current user may read."""

    labels = await label_crud.get_accessible_labels(
        db,
        user_id=current_user.id,
        is_admin=current_user.role == UserRole.ADMIN,
    )
    return [LabelResponse.model_validate(label) for label in labels]
