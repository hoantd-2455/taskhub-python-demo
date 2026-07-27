"""Redis client lifecycle helpers for optional cache features."""

from redis.asyncio import Redis

from app.core.config import settings

_redis_client: Redis | None = None


def get_redis_client() -> Redis | None:
    """Return the shared Redis client, or disable caching when no URL is configured."""

    global _redis_client
    if not settings.redis_url:
        return None
    if _redis_client is None:
        _redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def close_redis_client() -> None:
    """Close the shared client when the FastAPI process stops."""

    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
