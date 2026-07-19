from fastapi import FastAPI

from app.core.config import settings
from app.routers import api_router

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Task management API for the TaskHub learning project.",
)
app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Report that the HTTP application is available."""

    return {"status": "ok"}
