"""Dedicated scheduler entry point — the single process that executes reminder jobs.

Run as: python -m live150.reminders.run_scheduler
"""

import asyncio
import logging
import signal

from live150.logging import setup_logging
from live150.reminders.scheduler import get_scheduler

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

    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: (logger.info("Scheduler shutting down"), stop_event.set()))

    await stop_event.wait()
    scheduler.shutdown(wait=True)
    logger.info("Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
