from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import users as user_crud
from app.database import get_db
from app.schemas.user import UserProfileResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/{user_id}/profile",
    response_model=UserProfileResponse,
    responses={404: {"description": "User not found"}},
)
async def get_user_profile(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserProfileResponse:
    """Return a public profile by user ID.

    The final TaskHub schema has no username column, so this route uses `user_id`.
    """

    user = await user_crud.get_user_profile(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserProfileResponse.model_validate(user)
