"""Tiny JSON-based translation layer.

A language is resolved per request from a cookie (``recipebook-lang``), falling back to
the ``RECIPEBOOK_LANGUAGE`` setting and then English. Catalogs are plain JSON files in
``app/i18n/<lang>.json``; an optional ``<data_dir>/i18n/<lang>.json`` is merged on top so
translations can be tweaked without rebuilding the image (restart to reload).

Use ``translate(request, "key", **vars)`` in Python and ``t("key", **vars)`` in templates.
Missing keys fall back to English, then to the key itself.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_LANGUAGE = "en"
LANGUAGES = {"en": "English", "fi": "Suomi"}
COOKIE_NAME = "recipebook-lang"
CATALOG_DIR = Path(__file__).resolve().parent / "i18n"


def _read_catalog(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(key): str(value) for key, value in data.items()} if isinstance(data, dict) else {}


def load_catalogs(data_dir: Path | None = None) -> dict[str, dict[str, str]]:
    catalogs: dict[str, dict[str, str]] = {}
    for language in LANGUAGES:
        catalog = _read_catalog(CATALOG_DIR / f"{language}.json")
        if data_dir is not None:
            catalog.update(_read_catalog(Path(data_dir) / "i18n" / f"{language}.json"))
        catalogs[language] = catalog
    return catalogs


def resolve_language(request) -> str:
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie in LANGUAGES:
        return cookie
    settings = getattr(request.app.state, "settings", None)
    default = getattr(settings, "language", DEFAULT_LANGUAGE) if settings else DEFAULT_LANGUAGE
    return default if default in LANGUAGES else DEFAULT_LANGUAGE


def translate(request, key: str, **variables: Any) -> str:
    catalogs = getattr(request.app.state, "translations", None) or {}
    language = resolve_language(request)

    text = catalogs.get(language, {}).get(key)
    if text is None:
        text = catalogs.get(DEFAULT_LANGUAGE, {}).get(key)
    if text is None:
        text = key

    if variables:
        try:
            text = text.format(**variables)
        except (KeyError, IndexError, ValueError):
            return text
    return text
