"""Jinja2 template environment, flash messages and a tiny render helper."""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .config import APP_NAME, APP_VERSION
from .i18n import LANGUAGES, resolve_language, translate
from .utils import human_size

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _context_processor(request: Request) -> dict[str, Any]:
    has_session = "session" in request.scope
    flashes: list[dict[str, str]] = request.session.pop("_flashes", []) if has_session else []
    settings = getattr(request.app.state, "settings", None)
    language = resolve_language(request)

    def meal_name(value: str) -> str:
        if not value:
            return ""
        key = f"meal.{value.lower()}"
        text = translate(request, key)
        return value if text == key else text

    next_url = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "flashes": flashes,
        "current_path": request.url.path,
        "auth_enabled": bool(settings and settings.auth_enabled),
        "current_user": request.session.get("user") if has_session else None,
        "t": partial(translate, request),
        "current_language": language,
        "languages": LANGUAGES,
        "meal_name": meal_name,
        "next_url": quote(next_url, safe=""),
    }


templates = Jinja2Templates(directory=str(TEMPLATES_DIR), context_processors=[_context_processor])
templates.env.filters["human_size"] = human_size


def flash(request: Request, message: str, category: str = "success") -> None:
    """Queue a one-shot flash message for the next rendered page.

    The list is reassigned (not mutated in place) so Starlette's session
    middleware notices the change and re-issues the session cookie.
    """
    flashes = list(request.session.get("_flashes", []))
    flashes.append({"message": message, "category": category})
    request.session["_flashes"] = flashes


def render(request: Request, name: str, status_code: int = 200, **context: Any):
    return templates.TemplateResponse(request, name, context, status_code=status_code)
