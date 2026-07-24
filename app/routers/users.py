from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.crud import users as user_crud
from app.database import get_db
from app.dependencies.auth import get_current_active_user
from app.models.user import User
from app.schemas.user import PasswordChange, UserProfileResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserProfileResponse,
    responses={401: {"description": "Authentication required"}},
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserProfileResponse:
    """Return the account represented by the supplied bearer access token."""

    return UserProfileResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    responses={
        401: {"description": "Authentication required"},
        409: {"description": "Email in use"},
    },
)
async def update_me(
    user_in: UserUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserProfileResponse:
    """Update only profile fields explicitly included in the PATCH body."""

    if user_in.email is not None and str(user_in.email).lower() != current_user.email:
        existing_user = await user_crud.get_user_by_email(db, str(user_in.email))
        if existing_user is not None and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )
    try:
        user = await user_crud.update_user(db, current_user, user_in)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    return UserProfileResponse.model_validate(user)


@router.post(
    "/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={400: {"description": "Current password is incorrect"}},
)
async def change_password(
    password_in: PasswordChange,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Replace the password and revoke refresh sessions created before the change."""

    if not verify_password(password_in.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    await user_crud.change_password(db, current_user, hash_password(password_in.new_password))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
