"""PWA endpoints: the service worker, web app manifest and offline page."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse

from ..templating import render

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@router.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@router.get("/manifest.webmanifest", include_in_schema=False)
def web_manifest():
    return FileResponse(
        STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json"
    )


@router.get("/offline", response_class=HTMLResponse, include_in_schema=False)
def offline(request: Request):
    return render(request, "offline.html")
