"""Duplicate recipe detection when adding a recipe."""

from __future__ import annotations

from sqlalchemy import func, select

from app.duplicates import find_duplicates, normalize_name, normalize_url
from app.models import Recipe

IMPORT_HTML = (
    '<script type="application/ld+json">'
    '{"@type": "Recipe", "name": "Banana Bread", "recipeIngredient": ["bananas"]}'
    "</script>"
)


def test_normalize_helpers():
    assert normalize_name("  Spaghetti   Bolognese! ") == "spaghetti bolognese"
    assert normalize_url("HTTPS://Example.com/Recipe/") == "example.com/recipe"
    assert normalize_url("") == ""


def test_find_duplicates_by_exact_and_similar_name(client, app, make_recipe):
    make_recipe("Spaghetti Bolognese")
    with app.state.db.session() as session:
        exact = find_duplicates(session, "spaghetti bolognese")
        assert len(exact) == 1 and exact[0].same_name
        similar = find_duplicates(session, "Spagetti Bolognese")
        assert len(similar) == 1
        assert similar[0].similarity is not None and similar[0].similarity >= 0.85


def test_find_duplicates_by_source_url(client, app, make_recipe):
    make_recipe("Alpha", source_url="https://example.com/alpha")
    with app.state.db.session() as session:
        found = find_duplicates(session, "Something else", "https://example.com/alpha/")
        assert len(found) == 1
        assert found[0].same_link


def test_create_warns_then_saves_on_confirm(client, app, make_recipe):
    make_recipe("Chicken Curry")

    response = client.post(
        "/recipes", data={"name": "chicken curry", "ingredients": "x"}, follow_redirects=False
    )
    assert response.status_code == 200
    assert "Possible duplicate" in response.text
    assert "Add anyway" in response.text
    assert "/recipes/" in response.text  # links to the existing recipe

    with app.state.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Recipe)) == 1

    response = client.post(
        "/recipes",
        data={"name": "chicken curry", "ingredients": "x", "confirm_duplicate": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with app.state.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Recipe)) == 2


def test_create_no_warning_for_distinct_name(client, make_recipe):
    make_recipe("Chicken Curry")
    response = client.post("/recipes", data={"name": "Beef Stew"}, follow_redirects=False)
    assert response.status_code == 303


def test_import_warns_on_duplicate_then_confirms(client, app, monkeypatch, make_recipe):
    import app.routers.recipes as recipes_router

    make_recipe("Banana Bread", source_url="https://example.com/banana")
    monkeypatch.setattr(recipes_router, "fetch_html", lambda url: (IMPORT_HTML, url, None))
    monkeypatch.setattr(recipes_router, "fetch_recipe_image", lambda url: None)

    response = client.post(
        "/recipes/import", data={"url": "https://example.com/banana"}, follow_redirects=False
    )
    assert response.status_code == 200
    assert "Possible duplicate" in response.text

    with app.state.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Recipe)) == 1

    response = client.post(
        "/recipes/import",
        data={"url": "https://example.com/banana", "confirm_duplicate": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with app.state.db.session() as session:
        assert session.scalar(select(func.count()).select_from(Recipe)) == 2
