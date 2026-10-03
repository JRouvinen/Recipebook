"""Turn planned recipes into a merged shopping list.

Ingredients are stored as free text (one per line), so we split them into lines,
strip common list markers ("-", "*", "1.", ...) and merge duplicates across the
recipes planned for a date range, counting how many recipes need each item.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_MARKER = re.compile(r"^\s*(?:[-*•·–—]|\(?\d+[.)])\s*")


@dataclass
class ShoppingItem:
    key: str
    text: str
    count: int = 1


def parse_ingredients(text: str) -> list[str]:
    """Split an ingredients blob into cleaned, non-empty lines."""
    items: list[str] = []
    for line in (text or "").splitlines():
        cleaned = _MARKER.sub("", line).strip()
        if cleaned:
            items.append(cleaned)
    return items


def build_shopping_list(recipes) -> list[ShoppingItem]:
    """Merge the ingredients of several recipes into a de-duplicated list."""
    merged: dict[str, ShoppingItem] = {}
    for recipe in recipes:
        for ingredient in parse_ingredients(getattr(recipe, "ingredients", "")):
            key = " ".join(ingredient.lower().split())
            existing = merged.get(key)
            if existing is None:
                merged[key] = ShoppingItem(key=key, text=ingredient, count=1)
            else:
                existing.count += 1
    return sorted(merged.values(), key=lambda item: item.text.lower())
