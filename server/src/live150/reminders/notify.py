"""Client for the Live150 notify API."""

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from live150.config import settings

logger = logging.getLogger(__name__)


class NotifyClient:
    """Sends notifications to users via the Live150 notify API."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def send(self, user_id: str, payload: dict) -> None:
        """POST notification to the Live150 notify API.

        Retries with exponential backoff: 1s, 2s, 4s.
        On final failure, raises the exception (caller should log to audit).
        """
        headers = {}
        if settings.service_api_token:
            headers["Authorization"] = f"Bearer {settings.service_api_token}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                settings.notify_url,
                json={"user_id": user_id, **payload},
                headers=headers,
            )
            resp.raise_for_status()
            logger.info("Notification sent", extra={"user_id": user_id})
