from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.user import UserRegister, UserUpdate


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Return one user by identifier when it exists."""

    result = await db.scalars(select(User).where(User.id == user_id))
    return result.one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Return one user by normalized email address when it exists."""

    result = await db.scalars(select(User).where(User.email == email.lower()))
    return result.one_or_none()


async def create_user(db: AsyncSession, user_in: UserRegister, hashed_password: str) -> User:
    """Persist a newly registered member and roll back failed writes."""

    user = User(
        email=str(user_in.email).lower(),
        full_name=user_in.full_name,
        hashed_password=hashed_password,
    )
    db.add(user)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user: User, user_in: UserUpdate) -> User:
    """Apply only fields supplied by a PATCH request."""

    for field_name, value in user_in.model_dump(exclude_unset=True).items():
        if field_name == "email":
            value = str(value).lower()
        setattr(user, field_name, value)
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(user)
    return user


async def change_password(db: AsyncSession, user: User, hashed_password: str) -> User:
    """Change a password and revoke existing refresh sessions in one transaction."""

    user.hashed_password = hashed_password
    result = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    revoked_at = datetime.now(timezone.utc)
    for refresh_token in result:
        refresh_token.revoked_at = revoked_at
    try:
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise
    await db.refresh(user)
    return user


async def get_user_profile(db: AsyncSession, user_id: int) -> User | None:
    """Return data needed by the public profile endpoint."""

    return await get_user_by_id(db, user_id)
