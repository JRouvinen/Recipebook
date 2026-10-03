"""Importing recipes from a URL (schema.org JSON-LD)."""

from __future__ import annotations

from sqlalchemy import select

from app.models import Attachment, Recipe
from app.recipe_import import extract_recipe

JSON_LD_HTML = """
<html><head>
<title>Banana Bread Recipe</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Banana Bread",
  "description": "Moist and easy.",
  "recipeIngredient": ["3 bananas", "200 g flour", "100 g sugar"],
  "recipeInstructions": [
    {"@type": "HowToStep", "text": "Mash the bananas."},
    {"@type": "HowToStep", "text": "Mix everything and bake."}
  ],
  "image": {"@type": "ImageObject", "url": "/images/banana.jpg"},
  "keywords": "Baking, Breakfast",
  "url": "https://example.com/banana-bread"
}
</script>
</head><body></body></html>
"""

GRAPH_HTML = """
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "WebSite", "name": "Food Blog"},
  {"@type": "Recipe", "name": "Graph Soup", "recipeIngredient": ["water"]}
]}
</script>
"""

FALLBACK_HTML = """
<html><head>
<title>Grandma Pie</title>
<meta property="og:description" content="Tasty.">
<meta property="og:image" content="https://example.com/pie.jpg">
</head><body></body></html>
"""


def test_extract_json_ld_recipe():
    data = extract_recipe(JSON_LD_HTML, "https://example.com/banana-bread")
    assert data is not None
    assert data.name == "Banana Bread"
    assert data.source_url == "https://example.com/banana-bread"
    assert data.description == "Moist and easy."
    assert data.ingredients == "3 bananas\n200 g flour\n100 g sugar"
    assert data.instructions == "Mash the bananas.\nMix everything and bake."
    assert data.image_url == "https://example.com/images/banana.jpg"
    assert data.tags == ["Baking", "Breakfast"]


def test_extract_from_graph():
    data = extract_recipe(GRAPH_HTML, "https://example.com/soup")
    assert data is not None
    assert data.name == "Graph Soup"
    assert data.ingredients == "water"


def test_extract_falls_back_to_open_graph():
    data = extract_recipe(FALLBACK_HTML, "https://example.com/pie")
    assert data is not None
    assert data.name == "Grandma Pie"
    assert data.description == "Tasty."
    assert data.image_url == "https://example.com/pie.jpg"


def test_extract_returns_none_without_data():
    assert extract_recipe("<html><head><title></title></head></html>", "https://example.com") is None


def test_extract_decodes_html_entities_in_json_ld():
    html = '<script type="application/ld+json">{"@type": "Recipe", "name": "World&#39;s &amp; Best"}</script>'
    data = extract_recipe(html, "https://example.com")
    assert data is not None
    assert data.name == "World's & Best"


def test_import_form_is_available(client):
    assert "Import from URL" in client.get("/recipes/new").text
    assert "Import from URL" in client.get("/").text


def test_import_route_creates_recipe(client, app, monkeypatch):
    import app.routers.recipes as recipes_router

    monkeypatch.setattr(recipes_router, "fetch_html", lambda url: (JSON_LD_HTML, url))
    monkeypatch.setattr(
        recipes_router,
        "fetch_recipe_image",
        lambda url: ("banana.jpg", b"\xff\xd8\xffimage", "image/jpeg"),
    )

    response = client.post(
        "/recipes/import", data={"url": "https://example.com/banana-bread"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("?created=1")

    page = client.get(response.headers["location"]).text
    assert "Banana Bread" in page
    assert "3 bananas" in page
    assert "Baking" in page

    with app.state.db.session() as session:
        recipe = session.execute(select(Recipe)).scalars().one()
        assert recipe.name == "Banana Bread"
        assert recipe.source_url == "https://example.com/banana-bread"
        assert len(session.execute(select(Attachment)).scalars().all()) == 1


def test_import_route_handles_fetch_failure(client, monkeypatch):
    import app.routers.recipes as recipes_router

    monkeypatch.setattr(recipes_router, "fetch_html", lambda url: None)
    response = client.post(
        "/recipes/import", data={"url": "https://example.com/nope"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert "Could not fetch" in client.get("/recipes/new").text


def test_import_route_handles_missing_recipe_data(client, monkeypatch):
    import app.routers.recipes as recipes_router

    monkeypatch.setattr(
        recipes_router, "fetch_html", lambda url: ("<html><head><title></title></head></html>", url)
    )
    response = client.post(
        "/recipes/import", data={"url": "https://example.com/plain"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert "No recipe information" in client.get("/recipes/new").text
