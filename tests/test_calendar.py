"""Rotation calendar behaviour."""

from __future__ import annotations

from sqlalchemy import select

from app.models import CalendarEntry


def _plan(client, **data) -> int:
    response = client.post("/calendar", data=data, follow_redirects=False)
    assert response.status_code == 303, response.text
    return int(response.headers["location"].rstrip("/").rsplit("/", 1)[-1])


def test_fixed_weekly_plan_wraps(client, app, make_recipe):
    alpha = make_recipe("Alpha")
    beta = make_recipe("Beta")

    plan_id = _plan(
        client,
        name="Fixed week",
        mode="fixed",
        interval="weekly",
        start_date="2026-01-05",
        recipes=[alpha, beta],
    )

    assert client.get(f"/calendar/{plan_id}?view=week&day=2026-01-05").status_code == 200

    with app.state.db.session() as session:
        entries = (
            session.execute(
                select(CalendarEntry)
                .where(CalendarEntry.plan_id == plan_id)
                .order_by(CalendarEntry.entry_date)
            )
            .scalars()
            .all()
        )

    # Two recipes over a 7 day week repeat: A B A B A B A
    assert [entry.recipe_id for entry in entries] == [alpha, beta, alpha, beta, alpha, beta, alpha]


def test_random_plan_avoids_immediate_repeats(client, app, make_recipe):
    for name in ("A", "B", "C"):
        make_recipe(name)

    plan_id = _plan(
        client,
        name="Random",
        mode="random",
        interval="monthly",
        start_date="2026-02-01",
        recipes=[],
    )
    assert client.get(f"/calendar/{plan_id}?view=month&day=2026-02-15").status_code == 200

    with app.state.db.session() as session:
        entries = (
            session.execute(
                select(CalendarEntry)
                .where(CalendarEntry.plan_id == plan_id)
                .order_by(CalendarEntry.entry_date)
            )
            .scalars()
            .all()
        )

    assert entries
    assert all(
        entries[i].recipe_id != entries[i + 1].recipe_id for i in range(len(entries) - 1)
    )


def test_mark_cooked_and_swap(client, app, make_recipe):
    make_recipe("Alpha")
    make_recipe("Beta")
    plan_id = _plan(
        client,
        name="Marks",
        mode="fixed",
        interval="weekly",
        start_date="2026-01-05",
        recipes=[],
    )
    client.get(f"/calendar/{plan_id}?view=week&day=2026-01-05")

    with app.state.db.session() as session:
        entry = (
            session.execute(
                select(CalendarEntry)
                .where(CalendarEntry.plan_id == plan_id)
                .order_by(CalendarEntry.entry_date)
            )
            .scalars()
            .first()
        )
        entry_id = entry.id

    response = client.post(
        f"/calendar/entries/{entry_id}/status",
        data={"status": "cooked", "next": f"/calendar/{plan_id}"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    with app.state.db.session() as session:
        assert session.get(CalendarEntry, entry_id).status == "cooked"

    original_recipe = entry.recipe_id
    response = client.post(
        f"/calendar/entries/{entry_id}/swap",
        data={"next": f"/calendar/{plan_id}"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    with app.state.db.session() as session:
        swapped = session.get(CalendarEntry, entry_id)
        assert swapped.recipe_id != original_recipe
        assert swapped.status == "planned"


def test_spacing_every_other_day(client, app, make_recipe):
    alpha = make_recipe("Alpha")
    beta = make_recipe("Beta")
    plan_id = _plan(
        client,
        name="Every other day",
        mode="fixed",
        interval="weekly",
        start_date="2026-01-05",
        spacing=2,
        recipes=[alpha, beta],
    )
    assert client.get(f"/calendar/{plan_id}?view=week&day=2026-01-05").status_code == 200

    with app.state.db.session() as session:
        entries = (
            session.execute(
                select(CalendarEntry)
                .where(CalendarEntry.plan_id == plan_id)
                .order_by(CalendarEntry.entry_date)
            )
            .scalars()
            .all()
        )

    # Recipes only on Jan 5, 7, 9, 11 (every other day) and they keep advancing.
    assert [entry.entry_date.isoformat() for entry in entries] == [
        "2026-01-05",
        "2026-01-07",
        "2026-01-09",
        "2026-01-11",
    ]
    assert [entry.recipe_id for entry in entries] == [alpha, beta, alpha, beta]


def test_spacing_skips_days_before_start(client, app, make_recipe):
    alpha = make_recipe("Alpha")
    beta = make_recipe("Beta")
    # Start mid-week (Wed 2026-01-07); Mon/Tue must stay empty.
    plan_id = _plan(
        client,
        name="Mid-week start",
        mode="fixed",
        interval="weekly",
        start_date="2026-01-07",
        spacing=2,
        recipes=[alpha, beta],
    )
    assert client.get(f"/calendar/{plan_id}?view=week&day=2026-01-07").status_code == 200

    with app.state.db.session() as session:
        entries = (
            session.execute(
                select(CalendarEntry)
                .where(CalendarEntry.plan_id == plan_id)
                .order_by(CalendarEntry.entry_date)
            )
            .scalars()
            .all()
        )

    assert [entry.entry_date.isoformat() for entry in entries] == [
        "2026-01-07",
        "2026-01-09",
        "2026-01-11",
    ]
    assert [entry.recipe_id for entry in entries] == [alpha, beta, alpha]
