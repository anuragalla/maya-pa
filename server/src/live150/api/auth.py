import datetime

import jwt
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from live150.config import settings

router = APIRouter()

_ALGORITHM = "HS256"
_TOKEN_TTL = datetime.timedelta(hours=24)
_COOKIE_NAME = "maya_gate"


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(body: LoginRequest, response: Response) -> dict[str, str]:
    if not settings.gate_username or not settings.gate_password:
        raise HTTPException(status_code=503, detail="Auth not configured")

    if body.username != settings.gate_username or body.password != settings.gate_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode(
        {"sub": body.username, "exp": datetime.datetime.utcnow() + _TOKEN_TTL},
        settings.gate_jwt_secret,
        algorithm=_ALGORITHM,
    )
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=int(_TOKEN_TTL.total_seconds()),
        samesite="lax",
    )
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(_COOKIE_NAME)
    return {"status": "ok"}
