"""Explicit Vertex context caching for the static prompt prefix.

Caches SOUL.md + AGENTS.md + IDENTITY.md once as a platform-wide CachedContent.
Tools and the dynamic context block (local time, user profile, calendar) are
NOT cached — tools stay in the per-request payload, dynamic context moves into
the user message at request time. See before_model_cb in callbacks.py.

One cache covers all 10k users — the static prefix is identical for everyone.
Per-user sessions live in Postgres and sit after the cache boundary.

Feature flag: LIVE150_USE_EXPLICIT_CACHE=1  (default off — safe rollout).
"""

import asyncio
import logging
import os
from pathlib import Path

from live150.agent.genai_client import get_genai_client
from live150.agent.model_router import DEFAULT_MODEL

logger = logging.getLogger(__name__)

_AGENT_DIR = Path(__file__).parent
_SOUL_PATH = _AGENT_DIR / "SOUL.md"
_AGENTS_PATH = _AGENT_DIR / "AGENTS.md"
_IDENTITY_PATH = _AGENT_DIR / "IDENTITY.md"

CACHE_TTL_SECONDS = 3600  # 1h TTL; refresh every 50 min
REFRESH_INTERVAL_SECONDS = 50 * 60
CACHE_DISPLAY_NAME = "live150-static-v1"

_cache_name: str | None = None
_refresh_task: asyncio.Task | None = None


def is_enabled() -> bool:
    """True when the feature flag is set to 1/true."""
    return os.environ.get("LIVE150_USE_EXPLICIT_CACHE", "").strip().lower() in {"1", "true", "yes"}


def get_cache_name() -> str | None:
    """Current cache resource name, or None when disabled / not yet created / failed."""
    return _cache_name


def _load_base_text() -> str:
    """Read SOUL.md + AGENTS.md + IDENTITY.md into the static instruction body."""
    parts: list[str] = []
    for path in (_SOUL_PATH, _AGENTS_PATH, _IDENTITY_PATH):
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


async def create_or_refresh_cache() -> str | None:
    """Create a fresh CachedContent. Returns the resource name, or None on failure.

    Replaces any previously-tracked cache name atomically. The old cache is
    left to expire on its own TTL (no explicit delete — Vertex cleans up).
    """
    global _cache_name

    if not is_enabled():
        return None

    try:
        from google.genai import types

        client = get_genai_client()
        base = _load_base_text()
        if not base.strip():
            logger.warning("Static prefix is empty; skipping cache create")
            return None

        system_instruction = types.Content(parts=[types.Part(text=base)], role="user")

        cache = await client.aio.caches.create(
            model=DEFAULT_MODEL,
            config=types.CreateCachedContentConfig(
                system_instruction=system_instruction,
                ttl=f"{CACHE_TTL_SECONDS}s",
                display_name=CACHE_DISPLAY_NAME,
            ),
        )
        _cache_name = cache.name
        logger.info(
            "Explicit cache ready",
            extra={"cache_name": _cache_name, "base_chars": len(base)},
        )
        return _cache_name
    except Exception as e:
        logger.warning("Cache create failed; falling back to inline prompt", extra={"error": str(e)})
        # Keep old name if we had one — better stale cache than none, until TTL expires
        return _cache_name


async def _refresh_loop() -> None:
    """Background task: (re)create cache every REFRESH_INTERVAL_SECONDS."""
    while True:
        try:
            await create_or_refresh_cache()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Cache refresh loop error", extra={"error": str(e)})
        try:
            await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise


def start_refresh_loop() -> None:
    """Start the background refresh task. Idempotent. No-op when flag is off."""
    global _refresh_task
    if not is_enabled():
        logger.info("Explicit cache disabled (LIVE150_USE_EXPLICIT_CACHE not set)")
        return
    if _refresh_task is not None and not _refresh_task.done():
        return
    loop = asyncio.get_event_loop()
    _refresh_task = loop.create_task(_refresh_loop(), name="cache-refresh")
    logger.info("Explicit cache refresh loop started")


async def stop_refresh_loop() -> None:
    """Cancel the refresh loop on shutdown. Idempotent."""
    global _refresh_task
    if _refresh_task is None:
        return
    _refresh_task.cancel()
    try:
        await _refresh_task
    except (asyncio.CancelledError, Exception):
        pass
    finally:
        _refresh_task = None


def build_dynamic_context(state: dict) -> str:
    """Render the per-turn dynamic block — local time, timezone, user profile.

    Kept here (not in builder.py) so before_model_cb can build the same string
    when the cache replaces the static instruction.
    """
    local_time = state.get("user_local_time", "unknown")
    timezone = state.get("user_timezone", "UTC")
    profile = state.get("user_profile_summary", "")

    lines = [
        "## Current context",
        "",
        f"- **User's local time:** {local_time}",
        f"- **Timezone:** {timezone}",
    ]
    if profile:
        lines.append("")
        lines.append("### User profile")
        lines.append("")
        lines.append(profile)
    return "\n".join(lines)
