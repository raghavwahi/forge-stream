"""Endpoint for bootstrapping the CSRF token from the client side."""
from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.config import get_settings
from app.middleware.csrf import (
    _COOKIE_NAME,
    _MAX_TOKEN_AGE_SECONDS,
    _generate_token,
    _is_valid_token,
)

router = APIRouter(prefix="/csrf", tags=["csrf"])


class CSRFTokenResponse(BaseModel):
    token: str


@router.get("/token", response_model=CSRFTokenResponse)
async def get_csrf_token(
    request: Request, response: Response
) -> CSRFTokenResponse:
    """Return the current CSRF token, issuing a new one if absent or expired.

    Clients can call this endpoint on app startup to prime the CSRF cookie
    before making mutating requests. The token returned in the body always
    matches the ``csrf_token`` cookie the client should echo.
    """
    existing = request.cookies.get(_COOKIE_NAME, "")
    if existing and _is_valid_token(existing):
        return CSRFTokenResponse(token=existing)

    new_token = _generate_token()
    secure = get_settings().env != "development"
    response.set_cookie(
        key=_COOKIE_NAME,
        value=new_token,
        httponly=False,  # must be readable by JS
        samesite="strict",
        secure=secure,
        max_age=_MAX_TOKEN_AGE_SECONDS,
        path="/",
    )
    return CSRFTokenResponse(token=new_token)
