"""Dedicated scheduler entry point — the single process that executes reminder jobs.

Run as: python -m live150.reminders.run_scheduler
"""

import asyncio
import logging
import signal

from live150.logging import setup_logging
from live150.reminders.scheduler import get_scheduler
from live150.reminders.summary_jobs import (
    fire_daily_summaries,
    fire_monthly_summaries,
    fire_weekly_summaries,
)

logger = logging.getLogger(__name__)


async def _poll_noop() -> None:
    """No-op job that keeps the scheduler awake so it polls apscheduler_jobs every 10 s."""
    pass


async def main() -> None:
    setup_logging()
    logger.info("Starting scheduler process")

    scheduler = get_scheduler()
    scheduler.start()

    # Keep the scheduler awake so it polls apscheduler_jobs every 10 s.
    # APScheduler only queries the DB jobstore when _process_jobs() runs, which
    # only happens when a known job is due. Without this, jobs added by the agent
    # after startup are never discovered.
    scheduler.add_job(_poll_noop, "interval", seconds=10, id="__poll__", replace_existing=True)

    # System summary jobs — fixed cron, not user-created.
    # Daily:   02:00 UTC — past midnight for IST (UTC+5:30) and most user timezones
    # Weekly:  03:00 UTC every Sunday
    # Monthly: 03:00 UTC on the 1st of each month
    scheduler.add_job(
        fire_daily_summaries, "cron", hour=2, minute=0,
        id="__daily_summaries__", replace_existing=True,
    )
    scheduler.add_job(
        fire_weekly_summaries, "cron", day_of_week="sun", hour=3, minute=0,
        id="__weekly_summaries__", replace_existing=True,
    )
    scheduler.add_job(
        fire_monthly_summaries, "cron", day=1, hour=3, minute=0,
        id="__monthly_summaries__", replace_existing=True,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: (logger.info("Scheduler shutting down"), stop_event.set()))

    await stop_event.wait()
    scheduler.shutdown(wait=True)
    logger.info("Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
