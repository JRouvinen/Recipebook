"""Detect likely duplicate recipes when adding a new one.

A candidate is flagged when the normalised name matches exactly, when the name is
very similar (``difflib`` ratio), or when the source link matches. The caller decides
what to do — the app shows a warning and lets the user save anyway. Reasons are returned
as structured flags so the UI can translate them.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Recipe

SIMILARITY_THRESHOLD = 0.85
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    text = _NON_WORD.sub(" ", (name or "").lower())
    return _WHITESPACE.sub(" ", text).strip()


def normalize_url(url: str) -> str:
    url = (url or "").strip().lower()
    if not url:
        return ""
    url = re.sub(r"^https?://", "", url)
    return url.rstrip("/")


@dataclass
class Duplicate:
    recipe: Recipe
    score: float
    same_name: bool = False
    same_link: bool = False
    similarity: float | None = None


def find_duplicates(
    session: Session,
    name: str = "",
    source_url: str = "",
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[Duplicate]:
    """Return existing recipes that look like the one being added."""
    target_name = normalize_name(name)
    target_url = normalize_url(source_url)
    if not target_name and not target_url:
        return []

    duplicates: list[Duplicate] = []
    for recipe in session.execute(select(Recipe)).scalars().all():
        same_name = False
        same_link = False
        similarity: float | None = None

        if target_url and normalize_url(recipe.source_url) == target_url:
            same_link = True

        if target_name:
            existing_name = normalize_name(recipe.name)
            if existing_name == target_name:
                same_name = True
            else:
                ratio = difflib.SequenceMatcher(None, target_name, existing_name).ratio()
                if ratio >= threshold:
                    similarity = ratio

        if not (same_name or same_link or similarity is not None):
            continue

        score = 1.0 if (same_name or same_link) else (similarity or 0.0)
        duplicates.append(
            Duplicate(
                recipe=recipe,
                score=score,
                same_name=same_name,
                same_link=same_link,
                similarity=similarity,
            )
        )

    duplicates.sort(key=lambda item: (-item.score, item.recipe.name.lower()))
    return duplicates
