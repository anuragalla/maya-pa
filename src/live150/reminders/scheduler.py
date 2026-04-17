"""APScheduler setup with SQLAlchemy job store on Postgres.

Note: APScheduler's SQLAlchemyJobStore requires a SYNC database URL
even though the rest of the app uses async. This is a known limitation.
"""

import logging

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from live150.config import settings

logger = logging.getLogger(__name__)


def build_scheduler() -> AsyncIOScheduler:
    """Build the APScheduler instance with Postgres-backed job store."""
    jobstores = {
        "default": SQLAlchemyJobStore(
            url=settings.db_url_sync,
            tablename="apscheduler_jobs",
        )
    }

    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone="UTC",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 300,
        },
    )

    return scheduler
