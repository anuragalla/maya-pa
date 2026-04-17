import logging
import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from live150.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

_ready_cache: dict[str, float] = {}
READY_CACHE_TTL = 30.0


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict[str, str | bool]:
    now = time.monotonic()
    cached_at = _ready_cache.get("ts", 0.0)

    if now - cached_at < READY_CACHE_TTL:
        return {"status": "ok", "cached": True}

    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.exception("readiness check: db unreachable")
        db_ok = False

    if not db_ok:
        return {"status": "degraded", "db": db_ok, "cached": False}

    _ready_cache["ts"] = now
    return {"status": "ok", "db": db_ok, "cached": False}
