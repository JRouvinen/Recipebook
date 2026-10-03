"""Shopping list generated from the recipes planned in the calendar."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from ..auth import CurrentUser
from ..deps import DbSession
from ..models import CalendarEntry, Recipe
from ..shopping import build_shopping_list
from ..templating import render
from ..utils import month_bounds, parse_date, week_bounds

router = APIRouter()


@router.get("/shopping-list", response_class=HTMLResponse)
def shopping_list(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    start: str = "",
    end: str = "",
    exclude_cooked: bool = False,
):
    today = date.today()
    start_date = parse_date(start, today)
    end_date = parse_date(end, start_date + timedelta(days=6))
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    statement = (
        select(CalendarEntry)
        .where(
            CalendarEntry.entry_date >= start_date,
            CalendarEntry.entry_date <= end_date,
            CalendarEntry.recipe_id.is_not(None),
            CalendarEntry.status != "skipped",
        )
        .order_by(CalendarEntry.entry_date)
    )
    if exclude_cooked:
        statement = statement.where(CalendarEntry.status != "cooked")
    entries = session.execute(statement).scalars().all()

    recipe_ids: list[int] = []
    seen: set[int] = set()
    for entry in entries:
        if entry.recipe_id is not None and entry.recipe_id not in seen:
            seen.add(entry.recipe_id)
            recipe_ids.append(entry.recipe_id)

    recipes: list[Recipe] = []
    if recipe_ids:
        recipes = list(
            session.execute(
                select(Recipe).where(Recipe.id.in_(recipe_ids)).order_by(Recipe.name)
            )
            .scalars()
            .all()
        )

    week_start, week_end = week_bounds(today)
    month_start, month_end = month_bounds(today)

    return render(
        request,
        "shopping_list.html",
        start=start_date,
        end=end_date,
        exclude_cooked=exclude_cooked,
        items=build_shopping_list(recipes),
        recipes=recipes,
        planned_entries=len(entries),
        today=today,
        week_start=week_start,
        week_end=week_end,
        month_start=month_start,
        month_end=month_end,
    )
