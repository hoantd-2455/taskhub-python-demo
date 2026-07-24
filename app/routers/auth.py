from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_subject,
    hash_password,
    verify_password,
)
from app.crud import refresh_tokens as refresh_token_crud
from app.crud import users as user_crud
from app.database import get_db
from app.dependencies.auth import credentials_exception
from app.models.refresh_token import RefreshToken
from app.schemas.auth import RefreshTokenRequest, TokenResponse
from app.schemas.user import UserProfileResponse, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


async def issue_token_pair(db: AsyncSession, user_id: int) -> TokenResponse:
    """Create a short-lived access token and a revocable refresh token."""

    access_token = create_access_token(user_id)
    refresh_token, jti, expires_at = create_refresh_token(user_id)
    await refresh_token_crud.create_refresh_token(
        db,
        user_id=user_id,
        jti=jti,
        expires_at=expires_at,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def rotate_token_pair(
    db: AsyncSession,
    user_id: int,
    current_token: RefreshToken,
) -> TokenResponse:
    """Rotate a refresh session in one database transaction."""

    access_token = create_access_token(user_id)
    refresh_token, jti, expires_at = create_refresh_token(user_id)
    await refresh_token_crud.rotate_refresh_token(
        db,
        current_token,
        user_id=user_id,
        jti=jti,
        expires_at=expires_at,
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def get_refresh_token_payload(token: str) -> dict[str, Any]:
    """Validate the JWT-specific claims needed by refresh and logout endpoints."""

    try:
        payload = decode_token(token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        get_token_subject(payload)
        jti = payload.get("jti")
        if not isinstance(jti, str) or not jti:
            raise ValueError("Refresh token identifier is missing")
    except ValueError as exc:
        raise credentials_exception() from exc
    return payload


@router.post(
    "/register",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Email already registered"}},
)
async def register(
    user_in: UserRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserProfileResponse:
    """Create a member account with an Argon2-hashed password."""

    existing_user = await user_crud.get_user_by_email(db, str(user_in.email))
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    try:
        user = await user_crud.create_user(db, user_in, hash_password(user_in.password))
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    return UserProfileResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"description": "Invalid email or password"}},
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Exchange an OAuth2 password form for an access and refresh token pair.

    The OAuth2 `username` field is the account email for this application.
    """

    user = await user_crud.get_user_by_email(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return await issue_token_pair(db, user.id)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"description": "Invalid or revoked refresh token"}},
)
async def refresh_access_token(
    token_in: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Rotate a valid refresh token and issue a new credential pair."""

    payload = get_refresh_token_payload(token_in.refresh_token)
    refresh_token = await refresh_token_crud.get_active_refresh_token(db, payload["jti"])
    if refresh_token is None:
        raise credentials_exception()

    user = await user_crud.get_user_by_id(db, get_token_subject(payload))
    if user is None or not user.is_active or refresh_token.user_id != user.id:
        raise credentials_exception()

    return await rotate_token_pair(db, user.id, refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={401: {"description": "Invalid or revoked refresh token"}},
)
async def logout(
    token_in: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Revoke a refresh token so it cannot be used to obtain another session."""

    payload = get_refresh_token_payload(token_in.refresh_token)
    refresh_token = await refresh_token_crud.get_active_refresh_token(db, payload["jti"])
    if refresh_token is None or refresh_token.user_id != get_token_subject(payload):
        raise credentials_exception()
    await refresh_token_crud.revoke_refresh_token(db, refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
