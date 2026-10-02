"""Small pure helpers shared across the app."""

from __future__ import annotations

import re
from datetime import date, timedelta

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".avif", ".ico"}
TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".text", ".csv", ".log", ".json", ".yaml", ".yml", ".rst", ".ini",
}


def human_size(num: int | None) -> str:
    size = float(num or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def classify_attachment(filename: str, content_type: str = "") -> str:
    """Return ``image``, ``text`` or ``other`` for an uploaded file."""
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if content_type.startswith("image/") or suffix in IMAGE_EXTENSIONS:
        return "image"
    if content_type.startswith("text/") or suffix in TEXT_EXTENSIONS:
        return "text"
    return "other"


def parse_tag_names(raw: str) -> list[str]:
    """Split a comma/newline separated tag string into unique, cleaned names."""
    seen: set[str] = set()
    names: list[str] = []
    for part in re.split(r"[,\n;]+", raw or ""):
        name = " ".join(part.split())
        if name and name.lower() not in seen:
            seen.add(name.lower())
            names.append(name)
    return names


def week_bounds(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def month_bounds(day: date) -> tuple[date, date]:
    start = day.replace(day=1)
    following = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    return start, following - timedelta(days=1)


def parse_date(value: str | None, fallback: date | None = None) -> date:
    if value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return fallback or date.today()
