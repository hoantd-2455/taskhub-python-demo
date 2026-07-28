"""Application logging setup shared by local and Docker execution."""

import logging

from app.core.config import settings


def configure_logging() -> None:
    """Configure concise timestamped logs without replacing Uvicorn's handlers."""

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
