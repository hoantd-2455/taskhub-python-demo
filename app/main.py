import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.cache import close_redis_client
from app.core.config import settings
from app.core.logging import configure_logging
from app.routers import api_router

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Release optional infrastructure clients during graceful shutdown."""

    logger.info("TaskHub API is starting")
    yield
    await close_redis_client()
    logger.info("TaskHub API stopped")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Task management API for the TaskHub learning project.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Report that the HTTP application is available."""

    return {"status": "ok"}
