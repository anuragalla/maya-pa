"""Thin wrapper around ADK Runner for Live150.

Session state holds the access_token for tool calls and the
user_profile_summary rendered from USER.md for the agent's context.
The user's local time is injected fresh on every turn.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _user_local_time(tz_name: str) -> str:
    """Format the user's local time as a human-readable string."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    now = datetime.now(tz)
    return now.strftime("%A, %B %d %Y, %I:%M %p %Z")


class Live150Runner:
    def __init__(self, agent: LlmAgent, session_service: Any | None = None):
        self.agent = agent
        self.session_service = session_service or InMemorySessionService()
        self.runner = Runner(
            agent=self.agent,
            app_name="live150",
            session_service=self.session_service,
        )

    async def _fetch_user_context(self, access_token: str) -> tuple[str, str]:
        """Fetch initial context and return (profile_summary, timezone_name)."""
        try:
            from live150.live150_client import get_client
            from live150.agent.user_context import render_user_profile

            client = get_client()
            ctx = await client.get_initial_context(access_token)
            profile = render_user_profile(ctx)
            tz_name = ctx.user_data.timezone_name or "UTC"
            return profile, tz_name
        except Exception as e:
            logger.warning("Failed to fetch user profile", extra={"error": str(e)})
            return "(User profile unavailable)", "UTC"

    async def run_turn(
        self,
        user_id: str,
        session_id: uuid.UUID,
        access_token: str,
        message: str,
        turn_context: Literal["interactive", "reminder"] = "interactive",
    ) -> AsyncIterator[Any]:
        """Run a single agent turn, yielding ADK events."""
        from google.genai import types

        session = await self.session_service.get_session(
            app_name="live150",
            user_id=user_id,
            session_id=str(session_id),
        )

        if session is None:
            profile_summary, tz_name = await self._fetch_user_context(access_token)

            session = await self.session_service.create_session(
                app_name="live150",
                user_id=user_id,
                session_id=str(session_id),
                state={
                    "user_id": user_id,
                    "access_token": access_token,
                    "turn_context": turn_context,
                    "session_id": str(session_id),
                    "user_profile_summary": profile_summary,
                    "user_timezone": tz_name,
                    "user_local_time": _user_local_time(tz_name),
                    "recent_tool_call_count": 0,
                },
            )
        else:
            session.state["access_token"] = access_token
            session.state["turn_context"] = turn_context
            # Refresh local time on every turn
            tz_name = session.state.get("user_timezone", "UTC")
            session.state["user_local_time"] = _user_local_time(tz_name)

        # Sync-on-chat: refresh calendar snapshot if stale (>1 hour)
        if turn_context == "interactive":
            await self._maybe_sync_calendar(user_id, session)

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)],
        )

        async for event in self.runner.run_async(
            user_id=user_id,
            session_id=str(session_id),
            new_message=content,
        ):
            yield event

    async def _maybe_sync_calendar(self, user_id: str, session: Any) -> None:
        """Sync calendar snapshot if connected and last sync > 1 hour ago."""
        try:
            from live150.db.models.user_calendar import UserCalendar
            from live150.db.models.oauth_token import OAuthToken
            from live150.db.session import async_session_factory

            async with async_session_factory() as db:
                uc = (await db.execute(
                    select(UserCalendar).where(
                        UserCalendar.user_id == user_id,
                        UserCalendar.preferred == True,  # noqa: E712
                    )
                )).scalar_one_or_none()

                if uc is None:
                    # No calendar connected — populate state accordingly
                    session.state["connected_integrations"] = []
                    session.state["calendar_needs_reconnect"] = False
                    return

                # Populate integration state
                session.state["connected_integrations"] = [f"{uc.provider}_calendar"]
                session.state["calendar_needs_reconnect"] = uc.last_sync_status == "auth_failed"

                # Check if sync is needed
                now = datetime.now(timezone.utc)
                if uc.last_sync_at and (now - uc.last_sync_at) < timedelta(hours=1):
                    return  # Fresh enough

                # Trigger sync
                from live150.tools.calendar_tools import _get_service
                try:
                    svc = _get_service()
                    await svc.sync_snapshot(user_id, db)
                    logger.info("Calendar synced on chat entry for user=%s", user_id)
                except Exception as e:
                    logger.warning("Calendar sync failed for user=%s: %s", user_id, e)
        except Exception as e:
            logger.debug("Calendar sync check skipped: %s", e)
