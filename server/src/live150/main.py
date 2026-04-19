import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from live150.config import settings
from live150.db.session import engine
from live150.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    logger.info("live150-agent starting", extra={"env": settings.env})

    # Start APScheduler in paused mode — initializes the jobstore so add_job() persists
    # to the shared Postgres apscheduler_jobs table, but never executes jobs here.
    # Only the dedicated scheduler container executes jobs.
    try:
        from live150.reminders.scheduler import get_scheduler
        _sched = get_scheduler()
        if not _sched.running:
            _sched.start(paused=True)
        logger.info("APScheduler started (paused)")
    except Exception as e:
        logger.warning("APScheduler start skipped: %s", e)

    # Initialize CalendarService singleton
    try:
        from live150.calendar.registry import CalendarProviderRegistry
        from live150.calendar.service import CalendarService
        from live150.crypto.vault import Vault
        from live150.tools.calendar_tools import set_calendar_service

        vault = Vault.from_env(settings.master_key) if settings.master_key else None
        if vault:
            registry = CalendarProviderRegistry(vault)
            cal_service = CalendarService(registry)
            set_calendar_service(cal_service)
            logger.info("CalendarService initialized")
    except Exception as e:
        logger.warning("CalendarService init skipped: %s", e)

    yield
    try:
        from live150.reminders.scheduler import get_scheduler
        _sched = get_scheduler()
        if _sched.running:
            _sched.shutdown(wait=False)
    except Exception:
        pass
    await engine.dispose()
    logger.info("live150-agent stopped")


app = FastAPI(title="Live150 Agent", lifespan=lifespan)

# CORS for local dev (Vite on :5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health stays at root (Docker healthcheck, no versioning)
from live150.api.health import router as health_router  # noqa: E402

app.include_router(health_router)

# All API routes under /api/v1
from fastapi import APIRouter  # noqa: E402
from live150.api.chat import router as chat_router  # noqa: E402
from live150.api.stream import router as stream_router  # noqa: E402
from live150.api.oauth import router as oauth_router  # noqa: E402
from live150.api.reminders import router as reminders_router  # noqa: E402
from live150.api.confirmations import router as confirmations_router  # noqa: E402
from live150.api.notifications import router as notifications_router  # noqa: E402
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(chat_router, prefix="/chat")
api_v1.include_router(stream_router, prefix="/stream")
api_v1.include_router(oauth_router, prefix="/oauth")
api_v1.include_router(reminders_router, prefix="/reminders")
api_v1.include_router(confirmations_router, prefix="/confirmations")
api_v1.include_router(notifications_router, prefix="/notifications")
app.include_router(api_v1)
