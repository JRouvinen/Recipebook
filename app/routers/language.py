"""Language switching (sets the per-browser cookie)."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ..i18n import COOKIE_NAME, LANGUAGES

router = APIRouter()

ONE_YEAR = 60 * 60 * 24 * 365


def _safe_next(value: str | None) -> str:
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


@router.get("/language/{code}", include_in_schema=False)
def set_language(code: str, request: Request, next: str = "/"):
    response = RedirectResponse(_safe_next(next), status_code=303)
    if code in LANGUAGES:
        response.set_cookie(
            COOKIE_NAME, code, max_age=ONE_YEAR, samesite="lax", httponly=False
        )
    return response
