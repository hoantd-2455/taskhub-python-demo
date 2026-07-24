from pydantic import ConfigDict, Field

from app.schemas.base import ORMResponseModel


class TokenResponse(ORMResponseModel):
    """Access and refresh credentials returned after successful authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(ORMResponseModel):
    """A refresh credential supplied to renew an authenticated session."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1)
