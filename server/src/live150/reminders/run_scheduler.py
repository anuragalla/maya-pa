"""Dedicated scheduler entry point.

Run as: python -m live150.reminders.run_scheduler

This is the scheduler container's main process. It owns APScheduler
and should run as exactly one instance (not in Uvicorn workers).
"""

import asyncio
import logging
import signal

from live150.logging import setup_logging
from live150.reminders.scheduler import get_scheduler

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    logger.info("Starting scheduler process")

    scheduler = get_scheduler()
    scheduler.start()

    stop_event = asyncio.Event()

    def _signal_handler():
        logger.info("Scheduler shutting down")
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()
    scheduler.shutdown(wait=True)
    logger.info("Scheduler stopped")


if __name__ == "__main__":
    asyncio.run(main())
