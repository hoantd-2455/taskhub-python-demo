from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TASKHUB_",
        extra="ignore",
    )

    app_name: str = "TaskHub API"
    environment: str = "development"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://taskhub:taskhub@localhost:5432/taskhub"
    jwt_secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)

    @model_validator(mode="after")
    def reject_example_jwt_secret(self) -> "Settings":
        if self.jwt_secret_key.get_secret_value().startswith("replace-with-"):
            raise ValueError("TASKHUB_JWT_SECRET_KEY must be replaced with a random secret")
        return self


@lru_cache
def get_settings() -> Settings:
    # Pydantic reads this required value from TASKHUB_JWT_SECRET_KEY at runtime.
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
