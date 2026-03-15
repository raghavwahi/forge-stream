"""Endpoint for refreshing the CSRF token from the client side."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/csrf", tags=["csrf"])


class CSRFTokenResponse(BaseModel):
    token: str


@router.get("/token", response_model=CSRFTokenResponse)
async def get_csrf_token(request: Request) -> CSRFTokenResponse:
    """Return the current CSRF token from the cookie.

    Clients can call this endpoint on app startup to prime the CSRF cookie
    before making mutating requests. The middleware will set a fresh cookie
    in the response.
    """
    token = request.cookies.get("csrf_token", "")
    return CSRFTokenResponse(token=token)
