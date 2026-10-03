"""Login / logout routes (only active when authentication is enabled)."""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..deps import SettingsDep
from ..security import verify_password
from ..templating import flash, render

router = APIRouter()


def _safe_next(value: str | None) -> str:
    """Only allow same-site redirect targets."""
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return "/"


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request, settings: SettingsDep, next: str = "/"):
    if not settings.auth_enabled:
        return RedirectResponse("/", status_code=303)
    return render(request, "auth/login.html", next=_safe_next(next))


@router.post("/login")
def login(
    request: Request,
    settings: SettingsDep,
    username: str = Form(""),
    password: str = Form(""),
    next: str = Form("/"),
):
    if not settings.auth_enabled:
        return RedirectResponse("/", status_code=303)

    if username.strip() == settings.auth_username and verify_password(
        password, settings.auth_password_hash
    ):
        request.session["user"] = settings.auth_username
        flash(request, f"Welcome back, {settings.auth_username}.")
        return RedirectResponse(_safe_next(next), status_code=303)

    flash(request, "Invalid username or password.", "error")
    return render(request, "auth/login.html", next=_safe_next(next), status_code=401)


@router.get("/logout")
@router.post("/logout")
def logout(request: Request):
    request.session.pop("user", None)
    flash(request, "You have been logged out.", "info")
    return RedirectResponse("/login", status_code=303)
