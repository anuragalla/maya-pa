"""Voice WebSocket endpoint and prewarm."""

import logging
from datetime import date

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.responses import Response
from starlette.websockets import WebSocketState

import httpx

from live150.config import settings
from live150.db.session import async_session_factory, engine
from live150.memory.service import MemoryService
from live150.voice.onboarding_session import OnboardingVoiceSession
from live150.voice.session import VoiceSession

logger = logging.getLogger(__name__)
router = APIRouter()

_memory_service = MemoryService()


def _decode_token(token: str) -> dict | None:
    """Decode a liv150-api JWT. Returns claims or None."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


async def _load_user_profile(access_token: str) -> dict | None:
    try:
        async with httpx.AsyncClient(
            base_url=settings.liv150_api_base, timeout=5.0,
        ) as client:
            r = await client.get(
                "/api/v1/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning("voice_profile_fetch_failed", extra={"error": str(e)})
        return None


@router.websocket("/ws")
async def voice_ws(websocket: WebSocket, token: str = ""):
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    claims = _decode_token(token)
    if not claims:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = claims.get("sub", "")
    user_phone = claims.get("phone", "")
    if not user_id or not user_phone:
        await websocket.close(code=4001, reason="Invalid token: missing claims")
        return

    await websocket.accept()
    logger.info("voice_ws_connected", extra={"user": user_phone})

    profile = await _load_user_profile(token)

    display_name = "there"
    age = None
    goals: list[str] = []
    conditions: list[str] = []
    timezone_name = "UTC"

    if profile:
        display_name = profile.get("display_name") or "there"
        if profile.get("date_of_birth"):
            try:
                dob = date.fromisoformat(profile["date_of_birth"])
                age = date.today().year - dob.year
            except (ValueError, TypeError):
                pass
        goals = profile.get("goals") or []
        conditions = profile.get("conditions") or []
        timezone_name = profile.get("timezone_name") or "UTC"

    memories: list[str] = []
    try:
        async with async_session_factory() as db:
            hits = await _memory_service.recall(
                db=db, user_id=user_phone, query="user profile preferences goals recent", limit=12,
            )
            memories = [h.content for h in hits]
    except Exception as e:
        logger.warning("voice_memory_load_failed", extra={"error": str(e)})

    session = VoiceSession(
        user_phone=user_phone,
        access_token=token,
        api_base=settings.liv150_api_base,
    )

    try:
        await session.connect(
            display_name=display_name,
            age=age,
            goals=goals,
            conditions=conditions,
            timezone_name=timezone_name,
            memories=memories,
        )

        await websocket.send_json({"type": "state", "state": "listening"})
        await session.relay(websocket)

    except WebSocketDisconnect:
        logger.info("voice_ws_disconnected", extra={"user": user_phone})
    except Exception as e:
        logger.error("voice_ws_error", extra={"user": user_phone, "error": str(e)})
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=1011, reason="Internal error")
    finally:
        await session.close()
        logger.info("voice_session_closed", extra={"user": user_phone})


@router.websocket("/onboarding/ws")
async def onboarding_voice_ws(websocket: WebSocket, token: str = ""):
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    claims = _decode_token(token)
    if not claims:
        await websocket.close(code=4001, reason="Invalid token")
        return

    user_id = claims.get("sub", "")
    user_phone = claims.get("phone", "")
    if not user_id or not user_phone:
        await websocket.close(code=4001, reason="Invalid token: missing claims")
        return

    await websocket.accept()
    logger.info("onboarding_voice_ws_connected", extra={"user": user_phone})

    profile = await _load_user_profile(token)
    display_name = (profile.get("display_name") or "there") if profile else "there"

    session = OnboardingVoiceSession(user_id=user_id, user_phone=user_phone)

    try:
        await session.connect(display_name=display_name)
        await websocket.send_json({"type": "state", "state": "listening"})
        await session.relay(websocket)

    except WebSocketDisconnect:
        logger.info("onboarding_voice_ws_disconnected", extra={"user": user_phone})
    except Exception as e:
        logger.error("onboarding_voice_ws_error", extra={"user": user_phone, "error": str(e)})
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=1011, reason="Internal error")
    finally:
        await session.close()
        logger.info("onboarding_voice_session_closed", extra={"user": user_phone})


@router.post("/prewarm", status_code=204)
async def prewarm():
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text("SELECT 1"))
    except Exception:
        pass
    return Response(status_code=204)
