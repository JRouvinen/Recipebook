"""Parse free-text ingredient lines into structured parts.

Recipe ingredients are stored as free text (one per line) so people can write them
however they like, but for things like the shopping list it helps to know the
quantity, unit and name. This module does a best-effort parse of the common formats:

* decimals (``1.5``), simple fractions (``1/2``), mixed numbers (``1 1/2``) and
  unicode fractions (``½``)
* ranges (``2-3``)
* a broad set of units, including Finnish ones (``rkl``/``tl``/``dl``/``rs``/``tlk``)
* parenthetical notes (``1 tin (400 g) chopped tomatoes``) and preparation notes
  after a comma (``onion, finely chopped``)

When something cannot be parsed the whole line is kept as the name, so nothing is lost.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

UNICODE_FRACTIONS = {
    "½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4",
    "⅕": "1/5", "⅖": "2/5", "⅗": "3/5", "⅘": "4/5",
    "⅙": "1/6", "⅚": "5/6", "⅐": "1/7", "⅛": "1/8", "⅜": "3/8",
    "⅝": "5/8", "⅞": "7/8", "⅑": "1/9", "⅒": "1/10",
}

_LINE_MARKER = re.compile(r"^\s*(?:[-*•·–—]|\(?\d+[.)])\s*")
_PAREN = re.compile(r"\(([^)]*)\)")
_NUMBER = r"\d+(?:[.,]\d+)?"
_FRACTION = r"\d+/\d+"
_QUANTITY = rf"(?:\d+\s+\d+/\d+|{_FRACTION}|{_NUMBER})"
_QUANTITY_RE = re.compile(rf"^(?P<qty>{_QUANTITY})\s*(?P<rest>.*)$")
_RANGE_RE = re.compile(rf"^(?P<a>{_NUMBER})\s*[-–—]\s*(?P<b>{_NUMBER})\s*(?P<rest>.*)$")

UNIT_ALIASES = {
    # mass
    "g": "g", "gram": "g", "grams": "g", "gr": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "mg": "mg",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    # volume
    "ml": "ml", "millilitre": "ml", "millilitres": "ml", "milliliter": "ml", "milliliters": "ml",
    "cl": "cl", "dl": "dl",
    "l": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp", "tl": "tsp",
    "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp", "tbs": "tbsp", "rkl": "tbsp",
    "cup": "cup", "cups": "cup",
    # count / containers
    "clove": "clove", "cloves": "clove",
    "slice": "slice", "slices": "slice",
    "tin": "tin", "tins": "tin", "can": "tin", "cans": "tin", "tlk": "tin",
    "jar": "jar", "jars": "jar", "prk": "jar", "purkki": "jar", "purkkia": "jar",
    "pack": "pack", "packs": "pack", "packet": "pack", "packets": "pack", "pkt": "pack",
    "rs": "pack", "ps": "pack", "pss": "pack", "pussi": "pack", "pussia": "pack",
    "bunch": "bunch", "bunches": "bunch", "ruukku": "bunch", "ruukkua": "bunch",
    "sprig": "sprig", "sprigs": "sprig",
    "piece": "piece", "pieces": "piece", "pc": "piece", "pcs": "piece", "kpl": "piece",
    "pinch": "pinch", "pinches": "pinch",
    "dash": "dash", "dashes": "dash",
    "handful": "handful", "handfuls": "handful",
}


_FRACTION_DISPLAY = ((0.25, "¼"), (0.5, "½"), (0.75, "¾"), (1 / 3, "⅓"), (2 / 3, "⅔"))


@dataclass
class Ingredient:
    raw: str
    name: str = ""
    quantity: float | None = None
    quantity_text: str = ""
    unit: str = ""
    note: str = ""


def clean_lines(text: str) -> list[str]:
    """Split an ingredients blob into lines, stripping list markers and blanks."""
    lines: list[str] = []
    for line in (text or "").splitlines():
        cleaned = _LINE_MARKER.sub("", line).strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def _normalize(text: str) -> str:
    for glyph, replacement in UNICODE_FRACTIONS.items():
        text = text.replace(glyph, f" {replacement} ")
    return re.sub(r"\s+", " ", text).strip()


def _to_number(value: str) -> float:
    value = value.replace(",", ".")
    if " " in value:  # mixed number, e.g. "1 1/2"
        whole, fraction = value.split(None, 1)
        return _to_number(whole) + _to_number(fraction)
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        return float(numerator) / float(denominator)
    return float(value)


def parse_ingredient(raw: str) -> Ingredient:
    """Parse a single ingredient line into quantity / unit / name / note."""
    cleaned = _LINE_MARKER.sub("", unescape(raw)).strip()
    if not cleaned:
        return Ingredient(raw=raw)
    text = _normalize(cleaned)

    notes = _PAREN.findall(text)
    text = re.sub(r"\s+", " ", _PAREN.sub(" ", text)).strip()

    quantity: float | None = None
    quantity_text = ""
    rest = text

    range_match = _RANGE_RE.match(text)
    if range_match:
        quantity_text = f"{range_match['a']}-{range_match['b']}"
        rest = range_match["rest"].strip()
    else:
        quantity_match = _QUANTITY_RE.match(text)
        if quantity_match:
            quantity_text = quantity_match["qty"]
            quantity = _to_number(quantity_match["qty"])
            rest = quantity_match["rest"].strip()

    unit = ""
    name = rest
    if rest:
        head, _, tail = rest.partition(" ")
        candidate = head.rstrip(".").lower()
        if candidate in UNIT_ALIASES:
            unit = UNIT_ALIASES[candidate]
            name = tail.strip()

    note = ", ".join(part.strip() for part in notes if part.strip())
    if "," in name:
        name, extra = name.split(",", 1)
        name, extra = name.strip(), extra.strip()
        note = f"{note}; {extra}" if note else extra

    return Ingredient(
        raw=cleaned,
        name=name.strip(),
        quantity=quantity,
        quantity_text=quantity_text,
        unit=unit,
        note=note,
    )


def parse_ingredients(text: str) -> list[Ingredient]:
    return [parse_ingredient(line) for line in clean_lines(text)]


def format_quantity(value: float | None) -> str:
    """Format a number for display (whole numbers, common fractions, else 2 dp)."""
    if value is None:
        return ""
    whole = int(value)
    fraction = value - whole
    for target, glyph in _FRACTION_DISPLAY:
        if abs(fraction - target) < 0.01:
            return f"{whole}{glyph}" if whole else glyph
    if abs(fraction) < 1e-9:
        return str(whole)
    return f"{value:.2f}".rstrip("0").rstrip(".")
