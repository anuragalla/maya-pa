"""NAMS summary generator — daily, weekly, monthly.

Fetches health data from Live150 API, generates a compact narrative summary
via Flash-Lite, and saves it to pgvector so the agent can recall it via
search_memory("weekly summary") without making API calls each turn.
"""

import logging
from datetime import date, timedelta

from live150.agent.genai_client import get_genai_client
from live150.agent.model_router import LITE_MODEL
from live150.db.session import async_session_factory
from live150.memory.service import MemoryService
from live150.tools.base import live150_get

logger = logging.getLogger(__name__)

_memory_service = MemoryService()

_SUMMARY_PROMPT = """\
You are a health data summarizer. Given raw health data for a user over a {period}, \
write a single concise summary sentence (max 2 sentences). Include only what is present \
in the data. Focus on: activity performed, nutrition adherence, sleep duration/quality, \
mindfulness sessions. Use plain language, no emojis.

Data:
{data}
"""


async def _llm_summarize(period: str, data: dict) -> str:
    """Call Flash-Lite to turn raw health data into a one-line summary."""
    try:
        client = get_genai_client()
        resp = await client.aio.models.generate_content(
            model=LITE_MODEL,
            contents=_SUMMARY_PROMPT.format(period=period, data=str(data)[:3000]),
        )
        return resp.text.strip() if resp.text else ""
    except Exception as e:
        logger.warning("summarizer_llm_failed", extra={"period": period, "error": str(e)})
        return ""


async def generate_daily_summary(user_id: str, api_token: str, for_date: date | None = None) -> bool:
    """Generate and store a daily NAMS summary for the user."""
    target = for_date or (date.today() - timedelta(days=1))
    date_str = target.isoformat()

    try:
        data = await live150_get(api_token, "/api/v1/progress", params={"date": date_str})
    except Exception as e:
        logger.warning("daily_summary_fetch_failed", extra={"user_id": user_id, "date": date_str, "error": str(e)})
        return False

    summary = await _llm_summarize("day", data)
    if not summary:
        return False

    content = f"Daily summary for {date_str}: {summary}"
    async with async_session_factory() as db:
        await _memory_service.save(
            db=db,
            user_id=user_id,
            kind="note",
            content=content,
            source="system",
            metadata={"period": "daily", "date": date_str},
        )

    logger.info("daily_summary_saved", extra={"user_id": user_id, "date": date_str})
    return True


async def generate_weekly_summary(user_id: str, api_token: str, week_start: date | None = None) -> bool:
    """Generate and store a weekly NAMS summary for the user."""
    today = date.today()
    start = week_start or (today - timedelta(days=today.weekday() + 7))
    end = start + timedelta(days=6)
    week_label = f"{start.isoformat()} to {end.isoformat()}"

    try:
        # Fetch each day and combine — use holistic analysis for the week
        data = await live150_get(
            api_token,
            "/api/v1/progress",
            params={"date_from": start.isoformat(), "date_to": end.isoformat()},
        )
    except Exception as e:
        logger.warning("weekly_summary_fetch_failed", extra={"user_id": user_id, "week": week_label, "error": str(e)})
        return False

    summary = await _llm_summarize("week", data)
    if not summary:
        return False

    # ISO week number e.g. 2026-W16
    iso_week = f"{start.isocalendar()[0]}-W{start.isocalendar()[1]:02d}"
    content = f"Weekly summary for {week_label}: {summary}"

    async with async_session_factory() as db:
        await _memory_service.save(
            db=db,
            user_id=user_id,
            kind="note",
            content=content,
            source="system",
            metadata={"period": "weekly", "week": iso_week, "week_start": start.isoformat()},
        )

    logger.info("weekly_summary_saved", extra={"user_id": user_id, "week": iso_week})
    return True


async def generate_monthly_summary(user_id: str, api_token: str, year: int | None = None, month: int | None = None) -> bool:
    """Generate and store a monthly NAMS summary for the user."""
    today = date.today()
    y = year or (today.year if today.month > 1 else today.year - 1)
    m = month or (today.month - 1 if today.month > 1 else 12)

    start = date(y, m, 1)
    # Last day of month
    if m == 12:
        end = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(y, m + 1, 1) - timedelta(days=1)

    month_label = start.strftime("%B %Y")

    try:
        data = await live150_get(
            api_token,
            "/api/v1/progress",
            params={"date_from": start.isoformat(), "date_to": end.isoformat()},
        )
    except Exception as e:
        logger.warning("monthly_summary_fetch_failed", extra={"user_id": user_id, "month": month_label, "error": str(e)})
        return False

    summary = await _llm_summarize("month", data)
    if not summary:
        return False

    content = f"Monthly summary for {month_label}: {summary}"

    async with async_session_factory() as db:
        await _memory_service.save(
            db=db,
            user_id=user_id,
            kind="note",
            content=content,
            source="system",
            metadata={"period": "monthly", "month": f"{y}-{m:02d}"},
        )

    logger.info("monthly_summary_saved", extra={"user_id": user_id, "month": month_label})
    return True
