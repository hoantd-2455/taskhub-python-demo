from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.cache import close_redis_client
from app.core.config import settings
from app.routers import api_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Release optional infrastructure clients during graceful shutdown."""

    yield
    await close_redis_client()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Task management API for the TaskHub learning project.",
    lifespan=lifespan,
)
app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Report that the HTTP application is available."""

    return {"status": "ok"}
