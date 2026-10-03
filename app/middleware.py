"""Optional authentication gate.

When authentication is enabled every request must carry a logged-in session,
except for a small set of public paths (the login page, static assets and a
health endpoint). Unauthenticated requests are redirected to ``/login`` with a
``next`` parameter pointing back to the page they wanted.
"""

from __future__ import annotations

from urllib.parse import quote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

PUBLIC_PATHS = {"/login", "/logout", "/favicon.ico", "/health"}
PUBLIC_PREFIXES = ("/static/",)


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, login_path: str = "/login") -> None:
        super().__init__(app)
        self.login_path = login_path

    @staticmethod
    def is_public(path: str) -> bool:
        return path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self.is_public(path) or request.session.get("user"):
            return await call_next(request)

        target = path + (f"?{request.url.query}" if request.url.query else "")
        return RedirectResponse(f"{self.login_path}?next={quote(target, safe='')}", status_code=303)
