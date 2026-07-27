"""Background notification adapter used by the Day 7 assignment flow."""

import logging

logger = logging.getLogger(__name__)


async def send_assignment_notification(
    *,
    recipient_email: str,
    task_title: str,
    project_name: str,
) -> None:
    """Record a demo email notification without delaying the HTTP response.

    A real mail provider is deliberately outside this learning session. Keeping this adapter
    separate lets a future implementation replace the log call without changing the router.
    """

    logger.info(
        "Assignment notification queued for %s: task=%r project=%r",
        recipient_email,
        task_title,
        project_name,
    )
