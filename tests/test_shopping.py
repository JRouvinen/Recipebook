"""Shopping list generation from planned recipes (with quantity combining)."""

from __future__ import annotations

from sqlalchemy import select

from app.ingredients import clean_lines
from app.models import CalendarEntry
from app.shopping import build_shopping_list


class _Recipe:
    def __init__(self, ingredients):
        self.ingredients = ingredients


def test_clean_lines_strips_markers_and_blank_lines():
    text = "- 200 g pasta\n* 2 tomatoes\n1. onion\n\n  salt  \n"
    assert clean_lines(text) == ["200 g pasta", "2 tomatoes", "onion", "salt"]


def test_build_shopping_list_combines_matching_ingredients():
    items = build_shopping_list(
        [
            _Recipe("- 2 tomatoes\n200 g flour\n1 tsp salt"),
            _Recipe("2 tomatoes\n1 cucumber\n1 tsp salt"),
        ]
    )
    by_text = {item.text: item for item in items}
    assert "4 tomatoes" in by_text
    assert "2 tsp salt" in by_text
    assert "200 g flour" in by_text
    assert "1 cucumber" in by_text
    assert by_text["4 tomatoes"].count == 2
    assert by_text["200 g flour"].count == 1


def test_build_shopping_list_keeps_different_units_separate():
    items = build_shopping_list([_Recipe("200 g flour"), _Recipe("1 cup flour")])
    assert {item.text for item in items} == {"200 g flour", "1 cup flour"}


def test_build_shopping_list_keeps_unquantified_items():
    items = build_shopping_list([_Recipe("Salt and pepper to taste")])
    assert items[0].text == "Salt and pepper to taste"
    assert items[0].quantity is None


def test_build_shopping_list_handles_missing_ingredients():
    assert build_shopping_list([_Recipe(""), _Recipe(None)]) == []


def test_shopping_list_from_plan(client, make_recipe):
    pasta = make_recipe("Pasta", ingredients="- 200 g pasta\n2 tomatoes")
    salad = make_recipe("Salad", ingredients="2 tomatoes\n1 cucumber")

    response = client.post(
        "/calendar",
        data={
            "name": "Week",
            "mode": "fixed",
            "interval": "weekly",
            "start_date": "2026-01-05",
            "recipes": [pasta, salad],
        },
        follow_redirects=False,
    )
    plan_id = response.headers["location"].rstrip("/").rsplit("/", 1)[-1]
    client.get(f"/calendar/{plan_id}?view=week&day=2026-01-05")

    page = client.get("/shopping-list?start=2026-01-05&end=2026-01-11").text
    assert "200 g pasta" in page
    assert "1 cucumber" in page
    # "2 tomatoes" from both recipes is combined into a single line
    assert page.count('<span class="item-text">4 tomatoes</span>') == 1
    assert "2&times;" in page  # used by 2 recipes


def test_shopping_list_empty_range(client):
    page = client.get("/shopping-list?start=2030-01-01&end=2030-01-07").text
    assert "No recipes are planned" in page


def test_shopping_list_exclude_cooked(client, app, make_recipe):
    recipe_id = make_recipe("Soup", ingredients="carrot\nstock")
    response = client.post(
        "/calendar",
        data={
            "name": "Soup week",
            "mode": "fixed",
            "interval": "weekly",
            "start_date": "2026-03-02",
            "spacing": 7,
            "recipes": [recipe_id],
        },
        follow_redirects=False,
    )
    plan_id = int(response.headers["location"].rstrip("/").rsplit("/", 1)[-1])
    client.get(f"/calendar/{plan_id}?view=week&day=2026-03-02")

    with app.state.db.session() as session:
        entry_id = (
            session.execute(select(CalendarEntry).where(CalendarEntry.plan_id == plan_id))
            .scalars()
            .first()
            .id
        )

    assert "carrot" in client.get("/shopping-list?start=2026-03-02&end=2026-03-08").text

    client.post(
        f"/calendar/entries/{entry_id}/status",
        data={"status": "cooked"},
        follow_redirects=False,
    )
    excluded = client.get("/shopping-list?start=2026-03-02&end=2026-03-08&exclude_cooked=true").text
    assert "carrot" not in excluded
    assert "carrot" in client.get("/shopping-list?start=2026-03-02&end=2026-03-08").text


def test_calendar_links_to_shopping_list(client, make_recipe):
    recipe_id = make_recipe("Pasta")
    response = client.post(
        "/calendar",
        data={
            "name": "Week",
            "mode": "fixed",
            "interval": "weekly",
            "start_date": "2026-01-05",
            "recipes": [recipe_id],
        },
        follow_redirects=False,
    )
    plan_id = response.headers["location"].rstrip("/").rsplit("/", 1)[-1]
    page = client.get(f"/calendar/{plan_id}?view=week&day=2026-01-05").text
    assert "/shopping-list?start=" in page
