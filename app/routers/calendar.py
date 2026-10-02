"""Rotation calendar: plans, generation and marking entries."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from ..auth import CurrentUser
from ..calendar_service import entries_for_range, swap_entry
from ..deps import DbSession
from ..models import CalendarEntry, Recipe, RotationItem, RotationPlan
from ..templating import flash, render
from ..utils import month_bounds, parse_date, week_bounds

router = APIRouter()


def _shift_month(day: date, delta: int) -> date:
    month_index = day.month - 1 + delta
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(day.day, 28))


def _plans(session) -> list[RotationPlan]:
    return list(session.execute(select(RotationPlan).order_by(RotationPlan.id)).scalars().all())


@router.get("/calendar", response_class=HTMLResponse)
def calendar_index(request: Request, session: DbSession, user: CurrentUser):
    return render(request, "calendar/index.html", plans=_plans(session))


@router.get("/calendar/new", response_class=HTMLResponse)
def new_plan(request: Request, session: DbSession, user: CurrentUser):
    recipes = list(
        session.execute(select(Recipe).order_by(func.lower(Recipe.name))).scalars().all()
    )
    return render(request, "calendar/form.html", recipes=recipes, today=date.today())


@router.post("/calendar")
def create_plan(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    name: str = Form(...),
    mode: str = Form("fixed"),
    interval: str = Form("weekly"),
    start_date: str = Form(""),
    recipes: list[int] = Form(default=[]),
):
    plan = RotationPlan(
        name=name.strip() or "My plan",
        mode=mode if mode in {"fixed", "random"} else "fixed",
        interval=interval if interval in {"weekly", "monthly"} else "weekly",
        start_date=parse_date(start_date),
        active=True,
    )
    session.add(plan)
    session.flush()
    for position, recipe_id in enumerate(recipes):
        if session.get(Recipe, recipe_id) is not None:
            session.add(RotationItem(plan_id=plan.id, recipe_id=recipe_id, position=position))
    session.commit()
    flash(request, f'Plan "{plan.name}" created.')
    return RedirectResponse(f"/calendar/{plan.id}", status_code=303)


@router.get("/calendar/{plan_id}", response_class=HTMLResponse)
def view_plan(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    plan_id: int,
    view: str = "week",
    day: str = "",
):
    plan = session.get(RotationPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")

    anchor = parse_date(day)
    if view == "month":
        start, end = month_bounds(anchor)
        prev_anchor = _shift_month(anchor, -1)
        next_anchor = _shift_month(anchor, 1)
    else:
        view = "week"
        start, end = week_bounds(anchor)
        prev_anchor = anchor - timedelta(days=7)
        next_anchor = anchor + timedelta(days=7)

    entries = entries_for_range(session, plan, start, end)
    entries_by_date = {entry.entry_date: entry for entry in entries}
    today = date.today()

    days = [
        {"date": start + timedelta(days=i), "entry": entries_by_date.get(start + timedelta(days=i))}
        for i in range((end - start).days + 1)
    ]

    weeks = None
    if view == "month":
        grid_start = start - timedelta(days=start.weekday())
        grid_end = end + timedelta(days=(6 - end.weekday()))
        weeks = []
        week: list[dict] = []
        cursor = grid_start
        while cursor <= grid_end:
            week.append(
                {
                    "date": cursor,
                    "entry": entries_by_date.get(cursor),
                    "in_period": start <= cursor <= end,
                }
            )
            if len(week) == 7:
                weeks.append(week)
                week = []
            cursor += timedelta(days=1)

    return render(
        request,
        "calendar/view.html",
        plan=plan,
        view=view,
        start=start,
        end=end,
        anchor=anchor,
        prev_anchor=prev_anchor,
        next_anchor=next_anchor,
        days=days,
        weeks=weeks,
        today=today,
    )


@router.post("/calendar/{plan_id}/toggle")
def toggle_plan(request: Request, session: DbSession, user: CurrentUser, plan_id: int):
    plan = session.get(RotationPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    plan.active = not plan.active
    session.commit()
    flash(request, f'Plan "{plan.name}" is now {"active" if plan.active else "inactive"}.')
    return RedirectResponse("/calendar", status_code=303)


@router.post("/calendar/{plan_id}/delete")
def delete_plan(request: Request, session: DbSession, user: CurrentUser, plan_id: int):
    plan = session.get(RotationPlan, plan_id)
    if plan is None:
        raise HTTPException(404, "Plan not found")
    name = plan.name
    session.delete(plan)
    session.commit()
    flash(request, f'Plan "{name}" deleted.', "info")
    return RedirectResponse("/calendar", status_code=303)


@router.post("/calendar/entries/{entry_id}/status")
def set_entry_status(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    entry_id: int,
    status: str = Form(...),
    next: str = Form(""),
):
    entry = session.get(CalendarEntry, entry_id)
    if entry is None:
        raise HTTPException(404, "Entry not found")
    if status in {"planned", "cooked", "skipped"}:
        entry.status = status
        session.commit()
    return RedirectResponse(next or f"/calendar/{entry.plan_id}", status_code=303)


@router.post("/calendar/entries/{entry_id}/swap")
def swap_entry_route(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    entry_id: int,
    next: str = Form(""),
):
    entry = session.get(CalendarEntry, entry_id)
    if entry is None:
        raise HTTPException(404, "Entry not found")
    swap_entry(session, entry)
    flash(request, "Swapped in a different recipe.", "info")
    return RedirectResponse(next or f"/calendar/{entry.plan_id}", status_code=303)
