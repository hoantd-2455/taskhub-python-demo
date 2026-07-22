from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


async def create_refresh_token(
    db: AsyncSession,
    *,
    user_id: int,
    jti: str,
    expires_at: datetime,
) -> RefreshToken:
    """Persist only a refresh token identifier, never the token value itself."""

    refresh_token = RefreshToken(user_id=user_id, jti=jti, expires_at=expires_at)
    db.add(refresh_token)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(refresh_token)
    return refresh_token


async def get_active_refresh_token(db: AsyncSession, jti: str) -> RefreshToken | None:
    """Return a refresh token that has neither expired nor been revoked."""

    result = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    return result.one_or_none()


async def revoke_refresh_token(db: AsyncSession, refresh_token: RefreshToken) -> None:
    """Mark one refresh token unusable for future refresh or logout requests."""

    refresh_token.revoked_at = datetime.now(timezone.utc)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise


async def rotate_refresh_token(
    db: AsyncSession,
    current_token: RefreshToken,
    *,
    user_id: int,
    jti: str,
    expires_at: datetime,
) -> RefreshToken:
    """Revoke one refresh token and persist its replacement atomically."""

    current_token.revoked_at = datetime.now(timezone.utc)
    replacement = RefreshToken(user_id=user_id, jti=jti, expires_at=expires_at)
    db.add(replacement)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(replacement)
    return replacement
