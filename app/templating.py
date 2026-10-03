"""Jinja2 template environment, flash messages and a tiny render helper."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .config import APP_NAME, APP_VERSION
from .utils import human_size

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _context_processor(request: Request) -> dict[str, Any]:
    flashes: list[dict[str, str]] = []
    if "session" in request.scope:
        flashes = request.session.pop("_flashes", [])
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "flashes": flashes,
        "current_path": request.url.path,
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
