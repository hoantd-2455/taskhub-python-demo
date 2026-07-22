from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Return a one-way Argon2 hash for a plaintext password."""

    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a plaintext password against its stored hash."""

    return password_hash.verify(password, hashed_password)


def create_access_token(user_id: int) -> str:
    """Create a short-lived JWT used in the Authorization header."""

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": str(user_id), "type": "access", "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """Create a longer-lived JWT and its identifier for server-side revocation."""

    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid4())
    payload = {"sub": str(user_id), "type": "refresh", "jti": jti, "exp": expires_at}
    token = jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), settings.jwt_algorithm)
    return token, jti, expires_at


def decode_token(token: str) -> dict[str, Any]:
    """Decode a signed token and raise ValueError for invalid or expired tokens."""

    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise ValueError("Invalid or expired token") from exc


def get_token_subject(payload: dict[str, Any]) -> int:
    """Extract a positive numeric user ID from a decoded JWT payload."""

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit() or int(subject) < 1:
        raise ValueError("Token subject is invalid")
    return int(subject)
