"""Reminder job execution.

APScheduler serializes function references by module path,
so fire_reminder must stay at module scope.
"""

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone

from live150.reminders.notify import NotifyClient
from uuid6 import uuid7

logger = logging.getLogger(__name__)

_notify_client = NotifyClient()


def make_trigger(kind: str, expr: str, tz: str):
    """Build an APScheduler trigger from a parsed schedule. Shared by tool + REST."""
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    if kind == "once":
        return DateTrigger(run_date=datetime.fromisoformat(expr), timezone=tz)
    if kind == "cron":
        fields = expr.split()
        return CronTrigger(
            minute=fields[0], hour=fields[1], day=fields[2],
            month=fields[3], day_of_week=fields[4], timezone=tz,
        )
    if kind == "interval":
        return IntervalTrigger(seconds=int(expr), timezone=tz)
    raise ValueError(f"Unknown schedule kind: {kind}")


def _session_id_for_user(user_id: str) -> uuid.UUID:
    return uuid.UUID(hashlib.md5(f"live150:session:{user_id}".encode()).hexdigest())


async def _fire_reminder_async(reminder_id: str) -> None:
    from live150.db.session import async_session_factory
    from live150.db.models.reminder import Reminder
    from live150.db.models.chat_message import ChatMessage
    from live150.db.models.chat_session import ChatSession
    from sqlalchemy import select

    # Load reminder
    async with async_session_factory() as db:
        reminder = (await db.execute(
            select(Reminder).where(Reminder.reminder_id == uuid.UUID(reminder_id))
        )).scalar_one_or_none()

        if not reminder or reminder.status != "active":
            logger.warning("Reminder not found or inactive", extra={"reminder_id": reminder_id})
            return

        user_id = reminder.user_id
        prompt = reminder.prompt_template
        title = reminder.title

    # Impersonate user to get access token
    from live150.live150_client import get_client
    try:
        client = get_client()
        token_resp = await client.impersonate(user_id)
        access_token = token_resp.access_token
    except Exception:
        logger.exception("reminder_impersonation_failed", extra={"user_id": user_id, "reminder_id": reminder_id})
        return

    session_id = _session_id_for_user(user_id)

    # Ensure chat session exists
    async with async_session_factory() as db:
        existing = (await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )).scalar_one_or_none()
        if not existing:
            db.add(ChatSession(session_id=session_id, user_id=user_id))
            await db.commit()

    # Run agent with the reminder prompt to generate a markdown response.
    # Prepend an explicit framing instruction so the agent leads with the action,
    # not with warnings or advice — the health-advisor persona would otherwise take over.
    framed_prompt = (
        f"REMINDER DELIVERY: The user set a reminder titled \"{title}\".\n"
        f"Your first sentence MUST confirm the reminder action directly "
        f"(e.g. \"Time to {title}!\"). Do not open with warnings, caveats, "
        f"or health context. State the reminder first, then add brief context if useful.\n\n"
        f"{prompt}"
    )

    from live150.agent.builder import build_agent
    from live150.agent.runner import Live150Runner

    runner = Live150Runner(agent=build_agent())
    text_parts: list[str] = []
    try:
        async for event in runner.run_turn(
            user_id=user_id,
            session_id=session_id,
            access_token=access_token,
            message=framed_prompt,
            turn_context="reminder",
        ):
            if not hasattr(event, "content") or not event.content:
                continue
            if not hasattr(event.content, "parts"):
                continue
            for part in event.content.parts:
                if hasattr(part, "thought") and part.thought:
                    continue
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
    except Exception:
        logger.exception("reminder_agent_failed", extra={"reminder_id": reminder_id})
        text_parts = [f"**{title}**\n\n{prompt}"]

    raw = "".join(text_parts)
    raw = re.sub(r"<suggestions>.*?</suggestions>", "", raw, flags=re.DOTALL)
    full_text = raw.strip() or f"**{title}**"

    # Save as chat message and update last_fired_at in one transaction
    message_id = uuid7()
    async with async_session_factory() as db:
        db.add(ChatMessage(
            message_id=message_id,
            session_id=session_id,
            user_id=user_id,
            role="model",
            content=full_text,
            turn_context="reminder",
        ))
        reminder_row = (await db.execute(
            select(Reminder).where(Reminder.reminder_id == uuid.UUID(reminder_id))
        )).scalar_one_or_none()
        if reminder_row:
            reminder_row.last_fired_at = datetime.now(timezone.utc)
            # `once` reminders are single-shot; APScheduler removes the job
            # after firing. Flip status so list_reminders doesn't show a
            # zombie 'active' row forever.
            if reminder_row.schedule_kind == "once":
                reminder_row.status = "cancelled"
        await db.commit()

    # Push to any open SSE connection for this user.
    try:
        from live150.reminders.events import publish_notification
        await publish_notification(
            user_id,
            {
                "type": "reminder",
                "reminder_id": reminder_id,
                "title": title,
                "body": full_text,
                "message_id": str(message_id),
            },
        )
    except Exception:
        logger.exception(
            "reminder_delivery_failed",
            extra={"user_id": user_id, "reminder_id": reminder_id},
        )

    logger.info("reminder_fired", extra={"user_id": user_id, "reminder_id": reminder_id})


async def fire_reminder(reminder_id: str) -> None:
    """Entry point for APScheduler.

    Async so AsyncIOScheduler runs it directly on its event loop — no thread pool,
    no event loop mismatch with the SQLAlchemy async engine.
    """
    await _fire_reminder_async(reminder_id)
