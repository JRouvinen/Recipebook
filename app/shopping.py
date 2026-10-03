"""Build a merged shopping list from the recipes planned in the calendar.

Ingredients are parsed into structured parts (see :mod:`app.ingredients`), so items
that share a name and unit are combined: two recipes needing ``2 tomatoes`` each
produce a single ``4 tomatoes`` line. Items with different units (``200 g flour``
vs ``1 cup flour``) are kept separate because they cannot be added.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ingredients import clean_lines, format_quantity, parse_ingredient


@dataclass
class ShoppingItem:
    key: str
    text: str
    count: int = 1
    quantity: float | None = None
    unit: str = ""


@dataclass
class _Group:
    name: str
    unit: str
    quantities: list[float | None] = field(default_factory=list)
    recipes: set[int] = field(default_factory=set)

    def add(self, quantity: float | None, recipe) -> None:
        self.quantities.append(quantity)
        self.recipes.add(id(recipe))

    def to_item(self, key: str) -> ShoppingItem:
        numeric = [q for q in self.quantities if q is not None]
        all_numeric = bool(self.quantities) and len(numeric) == len(self.quantities)
        if all_numeric:
            total: float | None = sum(numeric)
            text = _format_line(total, self.unit, self.name)
        else:
            total = None
            text = self.name
        return ShoppingItem(
            key=key,
            text=text,
            count=max(len(self.recipes), 1),
            quantity=total,
            unit=self.unit,
        )


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def _format_line(quantity: float | None, unit: str, name: str) -> str:
    if quantity is None:
        return name
    prefix = format_quantity(quantity)
    if unit:
        prefix = f"{prefix} {unit}"
    return f"{prefix} {name}".strip()


def build_shopping_list(recipes) -> list[ShoppingItem]:
    """Merge the ingredients of several recipes into a de-duplicated shopping list."""
    groups: dict[tuple[str, str], _Group] = {}
    for recipe in recipes:
        for line in clean_lines(getattr(recipe, "ingredients", "")):
            ingredient = parse_ingredient(line)
            name = ingredient.name or ingredient.raw
            name_key = _normalize(name)
            key_pair = (name_key, ingredient.unit)
            group = groups.get(key_pair)
            if group is None:
                group = _Group(name=name, unit=ingredient.unit)
                groups[key_pair] = group
            group.add(ingredient.quantity, recipe)

    items = [group.to_item(f"{name_key}|{unit}") for (name_key, unit), group in groups.items()]
    return sorted(items, key=lambda item: item.text.lower())
