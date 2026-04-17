"""Reminder job execution.

APScheduler serializes function references by module path,
so fire_reminder must stay at module scope.
"""

import asyncio
import logging
import uuid

from live150.reminders.notify import NotifyClient

logger = logging.getLogger(__name__)

_notify_client = NotifyClient()


async def _fire_reminder_async(reminder_id: str) -> None:
    """Async implementation of reminder firing."""
    from live150.db.session import async_session_factory
    from live150.db.models.reminder import Reminder
    from sqlalchemy import select
    from datetime import datetime, timezone

    async with async_session_factory() as db:
        stmt = select(Reminder).where(Reminder.reminder_id == uuid.UUID(reminder_id))
        result = await db.execute(stmt)
        reminder = result.scalar_one_or_none()

        if not reminder or reminder.status != "active":
            logger.warning("Reminder not found or inactive", extra={"reminder_id": reminder_id})
            return

        user_id = reminder.user_id

        # In production: run agent with turn_context="reminder" and prompt_template
        # For now, send the prompt_template directly as the notification
        try:
            await _notify_client.send(
                user_id=user_id,
                payload={
                    "type": "reminder",
                    "reminder_id": reminder_id,
                    "title": reminder.title,
                    "body": reminder.prompt_template,
                },
            )
        except Exception:
            logger.exception(
                "reminder_delivery_failed",
                extra={"user_id": user_id, "reminder_id": reminder_id},
            )

        # Update last_fired_at
        reminder.last_fired_at = datetime.now(timezone.utc)
        await db.commit()

        logger.info(
            "reminder_fired",
            extra={"user_id": user_id, "reminder_id": reminder_id},
        )


def fire_reminder(reminder_id: str) -> None:
    """Entry point for APScheduler.

    APScheduler calls this synchronously; we run the async work in the event loop.
    """
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.ensure_future(_fire_reminder_async(reminder_id))
    else:
        loop.run_until_complete(_fire_reminder_async(reminder_id))
