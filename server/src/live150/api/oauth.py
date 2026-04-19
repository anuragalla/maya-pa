import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from live150.auth.middleware import AuthedUser, require_user
from live150.config import settings
from live150.crypto.vault import Vault
from live150.db.models.oauth_token import OAuthToken
from live150.db.session import get_db
from live150.db.models.connect_state import ConnectState
from live150.db.models.user_calendar import UserCalendar
from live150.oauth.flow import exchange_code, generate_auth_url, revoke_token, verify_state
from live150.oauth.providers import PROVIDERS
from live150.tools.integration_tools import verify_state_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["oauth"])


def _get_vault() -> Vault:
    return Vault.from_env(settings.master_key)


@router.get("/{provider}/start")
async def oauth_start(provider: str, user: AuthedUser = Depends(require_user)):
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    url = generate_auth_url(user.user_id, provider)
    return {"redirect_url": url}


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    if provider not in PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Try connect-state (HMAC) first, then fall back to JWT state
    user_id: str | None = None
    connect_state_row: ConnectState | None = None

    cs_stmt = select(ConnectState).where(ConnectState.state_token == state)
    connect_state_row = (await db.execute(cs_stmt)).scalar_one_or_none()

    if connect_state_row is not None:
        # Validate HMAC signature + expiry
        if connect_state_row.consumed_at is not None:
            raise HTTPException(status_code=400, detail="State already consumed")
        if connect_state_row.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="State expired")
        if connect_state_row.provider != provider:
            raise HTTPException(status_code=400, detail="Provider mismatch")
        if not verify_state_token(state, connect_state_row.user_id, provider):
            raise HTTPException(status_code=400, detail="Invalid state signature")

        user_id = connect_state_row.user_id
        connect_state_row.consumed_at = datetime.now(timezone.utc)
    else:
        # Fall back to JWT state (existing flow)
        try:
            state_data = verify_state(state)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid or expired state")
        if state_data.get("provider") != provider:
            raise HTTPException(status_code=400, detail="Provider mismatch")
        user_id = state_data["sub"]

    token_data = await exchange_code(provider, code)

    vault = _get_vault()
    aad = f"oauth:{user_id}:{provider}".encode()

    access_blob = vault.encrypt(token_data["access_token"], aad=aad)

    refresh_blob = None
    if "refresh_token" in token_data:
        refresh_blob = vault.encrypt(token_data["refresh_token"], aad=aad)

    access_expires_at = None
    if "expires_in" in token_data:
        access_expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])

    # Upsert oauth_token
    stmt = select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.provider == provider)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing:
        existing.access_token_ct = access_blob.ciphertext
        existing.access_token_nonce = access_blob.nonce
        existing.access_expires_at = access_expires_at
        existing.key_version = access_blob.key_version
        if refresh_blob:
            existing.refresh_token_ct = refresh_blob.ciphertext
            existing.refresh_token_nonce = refresh_blob.nonce
        if "scope" in token_data:
            existing.scopes = token_data["scope"].split()
    else:
        row = OAuthToken(
            oauth_token_id=uuid7(),
            user_id=user_id,
            provider=provider,
            scopes=token_data.get("scope", "").split() if "scope" in token_data else [],
            access_token_ct=access_blob.ciphertext,
            access_token_nonce=access_blob.nonce,
            refresh_token_ct=refresh_blob.ciphertext if refresh_blob else None,
            refresh_token_nonce=refresh_blob.nonce if refresh_blob else None,
            access_expires_at=access_expires_at,
            key_version=access_blob.key_version,
        )
        db.add(row)

    # Upsert user_calendar row for calendar-category integrations
    if connect_state_row is not None:
        uc_stmt = select(UserCalendar).where(
            UserCalendar.user_id == user_id, UserCalendar.provider == provider
        )
        uc = (await db.execute(uc_stmt)).scalar_one_or_none()
        if uc is None:
            db.add(UserCalendar(
                user_id=user_id,
                provider=provider,
                preferred=True,
            ))

    await db.commit()

    # Eagerly create the Live150 sub-calendar if this is a calendar integration
    if connect_state_row is not None:
        try:
            from live150.calendar.registry import CalendarProviderRegistry
            registry = CalendarProviderRegistry(vault)
            client = await registry.get_provider(user_id, provider, db)
            cal_id = await client.ensure_managed_calendar("Live150", "UTC")
            # Update user_calendar with the calendar_id
            uc_row = (await db.execute(
                select(UserCalendar).where(
                    UserCalendar.user_id == user_id, UserCalendar.provider == provider
                )
            )).scalar_one_or_none()
            if uc_row:
                uc_row.calendar_id = cal_id
                await db.commit()
        except Exception as e:
            logger.warning("Failed to eagerly create Live150 calendar: %s", e)

    # Redirect back to the web app
    redirect_url = f"{settings.oauth_success_redirect}/oauth/success?provider={provider}"
    return HTMLResponse(
        content=f"""
        <html><body>
        <h2>Connected!</h2>
        <p>Redirecting back to Live150...</p>
        <script>window.location.href = "{redirect_url}";</script>
        <p>If not redirected, <a href="{redirect_url}">click here</a>.</p>
        </body></html>
        """,
        status_code=200,
    )


@router.delete("/{provider}")
async def oauth_disconnect(
    provider: str,
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(OAuthToken).where(OAuthToken.user_id == user.user_id, OAuthToken.provider == provider)
    token_row = (await db.execute(stmt)).scalar_one_or_none()

    if not token_row:
        raise HTTPException(status_code=404, detail="Not connected")

    # Best-effort revoke
    try:
        vault = _get_vault()
        aad = f"oauth:{user.user_id}:{provider}".encode()
        access_blob = type("B", (), {"ciphertext": token_row.access_token_ct, "nonce": token_row.access_token_nonce, "key_version": token_row.key_version})()
        access_token = vault.decrypt(access_blob, aad=aad).decode()
        await revoke_token(provider, access_token)
    except Exception:
        logger.warning("Failed to revoke token", exc_info=True)

    await db.delete(token_row)
    await db.commit()
    return {"status": "disconnected"}


@router.get("/connected")
async def list_connected(
    user: AuthedUser = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(OAuthToken.provider, OAuthToken.scopes).where(OAuthToken.user_id == user.user_id)
    rows = (await db.execute(stmt)).all()
    return {"providers": [{"provider": r.provider, "scopes": r.scopes} for r in rows]}
