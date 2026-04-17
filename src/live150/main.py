import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from live150.config import settings
from live150.db.session import engine
from live150.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    logger.info("live150-agent starting", extra={"env": settings.env})
    yield
    await engine.dispose()
    logger.info("live150-agent stopped")


app = FastAPI(title="Live150 Agent", lifespan=lifespan)

# Register routers
from live150.api.health import router as health_router  # noqa: E402
from live150.api.chat import router as chat_router  # noqa: E402
from live150.api.oauth import router as oauth_router  # noqa: E402
from live150.api.reminders import router as reminders_router  # noqa: E402
from live150.api.confirmations import router as confirmations_router  # noqa: E402

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(oauth_router)
app.include_router(reminders_router)
app.include_router(confirmations_router)
