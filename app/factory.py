"""Application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import models  # noqa: F401 - importing registers all models on Base.metadata
from .config import Settings, get_settings
from .database import Database
from .middleware import AuthMiddleware
from .routers import attachments, auth, calendar, data, recipes, tags
from .templating import render


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings.database_url)
    database.create_all()

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ARG001
        yield
        database.dispose()

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.state.settings = settings
    app.state.db = database

    # Order matters: the last middleware added is the outermost, so SessionMiddleware
    # wraps AuthMiddleware and populates request.session before the auth check runs.
    if settings.auth_enabled:
        app.add_middleware(AuthMiddleware, login_path="/login")
    app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax")

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(auth.router)
    app.include_router(recipes.router)
    app.include_router(tags.router)
    app.include_router(attachments.router)
    app.include_router(calendar.router)
    app.include_router(data.router)

    @app.exception_handler(404)
    async def not_found(request: Request, exc):  # noqa: ARG001
        if request.url.path.startswith(("/static", "/attachments", "/media")):
            return HTMLResponse("Not found", status_code=404)
        return render(request, "errors/404.html", status_code=404)

    return app
