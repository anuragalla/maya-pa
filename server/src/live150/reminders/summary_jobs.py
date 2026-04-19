"""System-level summary jobs — daily, weekly, monthly NAMS summaries.

These are fixed cron jobs registered at scheduler startup (not user-created).
They iterate all active users (chat activity in last 30 days) and generate
summaries via the summarizer, saving results to pgvector.

Schedule (UTC):
  daily   — 02:00 every day      (past midnight for IST UTC+5:30)
  weekly  — 03:00 every Sunday
  monthly — 03:00 on 1st of month
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, distinct

logger = logging.getLogger(__name__)


async def _get_active_user_ids() -> list[str]:
    """Return user_ids with chat activity in the last 30 days."""
    from live150.db.session import async_session_factory
    from live150.db.models.chat_message import ChatMessage

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    async with async_session_factory() as db:
        rows = (await db.execute(
            select(distinct(ChatMessage.user_id)).where(ChatMessage.created_at >= cutoff)
        )).all()
    return [r[0] for r in rows]


async def _get_token_for_user(user_id: str) -> str | None:
    """Impersonate user to get a Live150 API token for data fetching."""
    try:
        from live150.live150_client import get_client
        client = get_client()
        resp = await client.impersonate(user_id)
        return resp.access_token
    except Exception as e:
        logger.warning("summary_impersonation_failed", extra={"user_id": user_id, "error": str(e)})
        return None


async def fire_daily_summaries() -> None:
    """Generate yesterday's daily summary for all active users."""
    from live150.agent.summarizer import generate_daily_summary

    user_ids = await _get_active_user_ids()
    logger.info("daily_summary_job_start", extra={"user_count": len(user_ids)})

    for user_id in user_ids:
        token = await _get_token_for_user(user_id)
        if not token:
            continue
        try:
            await generate_daily_summary(user_id, token)
        except Exception as e:
            logger.warning("daily_summary_failed", extra={"user_id": user_id, "error": str(e)})

    logger.info("daily_summary_job_done", extra={"user_count": len(user_ids)})


async def fire_weekly_summaries() -> None:
    """Generate last week's summary for all active users."""
    from live150.agent.summarizer import generate_weekly_summary

    user_ids = await _get_active_user_ids()
    logger.info("weekly_summary_job_start", extra={"user_count": len(user_ids)})

    for user_id in user_ids:
        token = await _get_token_for_user(user_id)
        if not token:
            continue
        try:
            await generate_weekly_summary(user_id, token)
        except Exception as e:
            logger.warning("weekly_summary_failed", extra={"user_id": user_id, "error": str(e)})

    logger.info("weekly_summary_job_done", extra={"user_count": len(user_ids)})


async def fire_monthly_summaries() -> None:
    """Generate last month's summary for all active users."""
    from live150.agent.summarizer import generate_monthly_summary

    user_ids = await _get_active_user_ids()
    logger.info("monthly_summary_job_start", extra={"user_count": len(user_ids)})

    for user_id in user_ids:
        token = await _get_token_for_user(user_id)
        if not token:
            continue
        try:
            await generate_monthly_summary(user_id, token)
        except Exception as e:
            logger.warning("monthly_summary_failed", extra={"user_id": user_id, "error": str(e)})

    logger.info("monthly_summary_job_done", extra={"user_count": len(user_ids)})
