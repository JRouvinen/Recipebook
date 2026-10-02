"""Populate the database with a few sample recipes.

Usage::

    .venv/bin/python seed.py

Skips seeding if the database already contains recipes.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.config import get_settings
from app.database import Database
from app.models import Recipe, Tag

SAMPLE_RECIPES = [
    {
        "name": "Spaghetti Bolognese",
        "description": "Weeknight classic, freezes well.",
        "ingredients": "500 g beef mince\n1 onion\n2 garlic cloves\n400 g chopped tomatoes\nSpaghetti",
        "instructions": "Brown the mince.\nAdd onion and garlic.\nSimmer with tomatoes for 20 min.\nServe over spaghetti.",
        "tags": "Beef, Pasta, Dinner",
    },
    {
        "name": "Chickpea Curry",
        "description": "Fast vegetarian curry from the cupboard.",
        "ingredients": "1 tin chickpeas\n1 tin coconut milk\nCurry paste\nSpinach\nRice",
        "instructions": "Fry the curry paste.\nAdd coconut milk and chickpeas.\nSimmer 15 min.\nWilt in spinach, serve with rice.",
        "tags": "Vegetarian, Curry, Dinner",
    },
    {
        "name": "Overnight Oats",
        "description": "Breakfast ready when you wake up.",
        "ingredients": "50 g oats\n150 ml milk\n1 tbsp yoghurt\nBerries\nHoney",
        "instructions": "Mix oats, milk and yoghurt.\nRefrigerate overnight.\nTop with berries and honey.",
        "tags": "Breakfast, Vegetarian, Quick",
    },
    {
        "name": "Chicken Stir Fry",
        "description": "Use whatever vegetables are in the fridge.",
        "ingredients": "2 chicken breasts\nMixed peppers\nSoy sauce\nGinger\nNoodles",
        "instructions": "Slice and fry the chicken.\nAdd vegetables, ginger and soy.\nToss with cooked noodles.",
        "tags": "Chicken, Quick, Dinner",
    },
    {
        "name": "Tomato Soup",
        "description": "Great with a grilled cheese.",
        "ingredients": "1 kg tomatoes\n1 onion\nStock\nBasil\nCream",
        "instructions": "Soften onion.\nAdd tomatoes and stock, simmer 25 min.\nBlend, finish with cream and basil.",
        "tags": "Vegetarian, Soup, Lunch",
    },
]


def main() -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    database.create_all()
    session = database.session()
    try:
        existing = session.scalar(select(func.count()).select_from(Recipe)) or 0
        if existing:
            print(f"Database already contains {existing} recipe(s); nothing to do.")
            return

        tag_cache: dict[str, Tag] = {}

        def get_tag(name: str) -> Tag:
            key = name.lower()
            if key not in tag_cache:
                tag = session.scalar(select(Tag).where(func.lower(Tag.name) == key))
                if tag is None:
                    tag = Tag(name=name)
                    session.add(tag)
                    session.flush()
                tag_cache[key] = tag
            return tag_cache[key]

        for sample in SAMPLE_RECIPES:
            data = dict(sample)
            tag_names = [t.strip() for t in data.pop("tags", "").split(",") if t.strip()]
            recipe = Recipe(**data)
            session.add(recipe)
            for name in tag_names:
                recipe.tags.append(get_tag(name))

        session.commit()
        print(f"Seeded {len(SAMPLE_RECIPES)} recipes into {settings.database_url}.")
    finally:
        session.close()
        database.dispose()


if __name__ == "__main__":
    main()
