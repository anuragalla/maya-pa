import httpx

from live150.config import settings


async def live150_get(api_token: str, path: str, params: dict | None = None) -> dict:
    """Make a GET request to the Live150 health API."""
    async with httpx.AsyncClient(base_url=settings.api_base, timeout=30.0) as client:
        r = await client.get(path, params=params, headers={"Authorization": f"Bearer {api_token}"})
        r.raise_for_status()
        return r.json()


async def live150_post(api_token: str, path: str, json: dict | None = None) -> dict:
    """Make a POST request to the Live150 health API."""
    async with httpx.AsyncClient(base_url=settings.api_base, timeout=30.0) as client:
        r = await client.post(path, json=json, headers={"Authorization": f"Bearer {api_token}"})
        r.raise_for_status()
        return r.json()
