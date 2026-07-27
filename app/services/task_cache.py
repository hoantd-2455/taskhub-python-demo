"""Serialize and invalidate Redis cache entries for project task lists."""

import logging

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import settings
from app.schemas.task import TaskListParams, TaskListResponse

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "taskhub:project-tasks"


def build_project_task_list_cache_key(project_id: int, params: TaskListParams) -> str:
    """Build a deterministic key that separates every filter and pagination combination."""

    status = params.status.value if params.status is not None else "all"
    priority = params.priority.value if params.priority is not None else "all"
    assignee_id = str(params.assignee_id) if params.assignee_id is not None else "all"
    return (
        f"{CACHE_KEY_PREFIX}:{project_id}:status={status}:priority={priority}:"
        f"assignee={assignee_id}:page={params.page}:limit={params.limit}"
    )


async def get_cached_project_task_list(
    redis: Redis | None,
    cache_key: str,
) -> TaskListResponse | None:
    """Return a validated cached response; cache connectivity never fails the API request."""

    if redis is None:
        return None
    try:
        cached_value = await redis.get(cache_key)
    except RedisError:
        logger.warning("Redis read failed for task-list cache", exc_info=True)
        return None
    if cached_value is None:
        return None
    try:
        return TaskListResponse.model_validate_json(cached_value)
    except ValidationError:
        logger.warning("Discarding invalid cached task-list response for key %s", cache_key)
        await delete_cache_key(redis, cache_key)
        return None


async def cache_project_task_list(
    redis: Redis | None,
    cache_key: str,
    response: TaskListResponse,
) -> None:
    """Store a serialized task page for the configured short cache lifetime."""

    if redis is None:
        return
    try:
        await redis.set(
            cache_key,
            response.model_dump_json(),
            ex=settings.redis_task_list_ttl_seconds,
        )
    except RedisError:
        logger.warning("Redis write failed for task-list cache", exc_info=True)


async def invalidate_project_task_lists(redis: Redis | None, project_id: int) -> None:
    """Delete every cached filter/page variant after a task mutation in one project."""

    if redis is None:
        return
    try:
        keys = [key async for key in redis.scan_iter(match=f"{CACHE_KEY_PREFIX}:{project_id}:*")]
        if keys:
            await redis.delete(*keys)
    except RedisError:
        logger.warning("Redis invalidation failed for project %s", project_id, exc_info=True)


async def delete_cache_key(redis: Redis, cache_key: str) -> None:
    """Best-effort removal of a corrupt single cache entry."""

    try:
        await redis.delete(cache_key)
    except RedisError:
        logger.warning("Redis deletion failed for key %s", cache_key, exc_info=True)
