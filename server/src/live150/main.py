import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import jwt
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from live150.config import settings
from live150.db.session import engine
from live150.logging import setup_logging

_GATE_COOKIE = "maya_gate"
_GATE_SKIP = {"/health", "/ready", "/api/v1/auth/login", "/api/v1/auth/logout", "/api/v1/notifications/push"}

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

    # Explicit prompt cache (feature-flagged: LIVE150_USE_EXPLICIT_CACHE=1)
    try:
        from live150.agent import caching
        if caching.is_enabled():
            await caching.create_or_refresh_cache()
            caching.start_refresh_loop()
    except Exception as e:
        logger.warning("Prompt cache init skipped: %s", e)

    yield
    try:
        from live150.agent import caching
        await caching.stop_refresh_loop()
    except Exception:
        pass
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


@app.middleware("http")
async def gate_middleware(request: Request, call_next):
    if not settings.gate_username:
        return await call_next(request)
    if request.url.path in _GATE_SKIP:
        return await call_next(request)
    token = request.cookies.get(_GATE_COOKIE)
    if not token:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    try:
        jwt.decode(token, settings.gate_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


# CORS for local dev (Vite on :5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "https://150.trackgenie.in"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health stays at root (Docker healthcheck, no versioning)
from live150.api.health import router as health_router  # noqa: E402

app.include_router(health_router)

# All API routes under /api/v1
from fastapi import APIRouter  # noqa: E402
from live150.api.auth import router as auth_router  # noqa: E402
from live150.api.chat import router as chat_router  # noqa: E402
from live150.api.stream import router as stream_router  # noqa: E402
from live150.api.oauth import router as oauth_router  # noqa: E402
from live150.api.reminders import router as reminders_router  # noqa: E402
from live150.api.confirmations import router as confirmations_router  # noqa: E402
from live150.api.notifications import router as notifications_router  # noqa: E402
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth_router, prefix="/auth")
api_v1.include_router(chat_router, prefix="/chat")
api_v1.include_router(stream_router, prefix="/stream")
api_v1.include_router(oauth_router, prefix="/oauth")
api_v1.include_router(reminders_router, prefix="/reminders")
api_v1.include_router(confirmations_router, prefix="/confirmations")
api_v1.include_router(notifications_router, prefix="/notifications")
app.include_router(api_v1)
