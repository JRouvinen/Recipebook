"""Detect likely duplicate recipes when adding a new one.

A candidate is flagged when the normalised name matches exactly, when the name is
very similar (``difflib`` ratio), or when the source link matches. The caller decides
what to do — the app shows a warning and lets the user save anyway.
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
    reason: str
    score: float


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
        reasons: list[str] = []
        score = 0.0

        if target_url and normalize_url(recipe.source_url) == target_url:
            reasons.append("same source link")
            score = max(score, 1.0)

        if target_name:
            existing_name = normalize_name(recipe.name)
            if existing_name == target_name:
                reasons.append("same name")
                score = max(score, 1.0)
            else:
                ratio = difflib.SequenceMatcher(None, target_name, existing_name).ratio()
                if ratio >= threshold:
                    reasons.append(f"similar name ({round(ratio * 100)}%)")
                    score = max(score, ratio)

        if reasons:
            duplicates.append(Duplicate(recipe=recipe, reason=", ".join(reasons), score=score))

    duplicates.sort(key=lambda item: (-item.score, item.recipe.name.lower()))
    return duplicates
