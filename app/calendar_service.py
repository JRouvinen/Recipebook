"""Rotation-calendar logic.

A plan assigns a recipe on a repeating schedule:

* ``interval`` controls the repeating cycle length in days (weekly = 7, monthly = 30).
* ``spacing`` is the number of days between planned recipes (1 = every day,
  2 = every other day, ...). Gap days have no entry.
* ``fixed``  – recipes from the plan (ordered) advance one per planned day and repeat.
* ``random`` – a random recipe is chosen for each planned day, avoiding an immediate
  repeat.

Choices are persisted as ``CalendarEntry`` rows, so the schedule is stable and can be
marked cooked/skipped or swapped.
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CalendarEntry, Recipe, RotationItem, RotationPlan

CYCLE_LENGTHS = {"weekly": 7, "monthly": 30}


def cycle_length(plan: RotationPlan) -> int:
    return CYCLE_LENGTHS.get(plan.interval, 7)


def plan_spacing(plan: RotationPlan) -> int:
    return max(int(plan.spacing or 1), 1)


def plan_pool(session: Session, plan: RotationPlan) -> list[int]:
    """Ordered recipe ids for a plan; falls back to all recipes if none chosen."""
    items = (
        session.execute(
            select(RotationItem)
            .where(RotationItem.plan_id == plan.id)
            .order_by(RotationItem.position, RotationItem.id)
        )
        .scalars()
        .all()
    )
    recipe_ids = [item.recipe_id for item in items]
    if recipe_ids:
        return recipe_ids
    return [r.id for r in session.execute(select(Recipe).order_by(Recipe.name)).scalars().all()]


def recipe_slot(plan: RotationPlan, offset_days: int) -> int:
    """Index (in planned days) of a day, accounting for the plan's spacing and cycle.

    Because only every ``spacing``-th day gets a recipe, the slot advances once per
    planned day and the whole pattern repeats every ``interval`` days.
    """
    spacing = plan_spacing(plan)
    cycle = cycle_length(plan)
    slots_per_cycle = math.ceil(cycle / spacing)
    return (offset_days // cycle) * slots_per_cycle + (offset_days % cycle) // spacing


def _pick_random(pool: list[int], last_recipe_id: int | None, rng: random.Random) -> int:
    candidates = [rid for rid in pool if rid != last_recipe_id] or pool
    return rng.choice(candidates)


def generate_entries(
    session: Session,
    plan: RotationPlan,
    start: date,
    end: date,
    rng: random.Random | None = None,
) -> int:
    """Create any missing ``CalendarEntry`` rows for ``plan`` between two dates.

    Gap days (when ``spacing`` > 1) intentionally get no entry.
    """
    if end < start:
        start, end = end, start
    rng = rng or random.Random()

    existing = {
        entry.entry_date: entry
        for entry in session.execute(
            select(CalendarEntry).where(
                CalendarEntry.plan_id == plan.id,
                CalendarEntry.entry_date >= start,
                CalendarEntry.entry_date <= end,
            )
        )
        .scalars()
        .all()
    }

    previous = session.execute(
        select(CalendarEntry)
        .where(CalendarEntry.plan_id == plan.id, CalendarEntry.entry_date < start)
        .order_by(CalendarEntry.entry_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    last_recipe_id = previous.recipe_id if previous else None

    spacing = plan_spacing(plan)
    pool = plan_pool(session, plan)
    created = 0
    day = start
    while day <= end:
        entry = existing.get(day)
        if entry is not None:
            if entry.recipe_id is not None:
                last_recipe_id = entry.recipe_id
            day += timedelta(days=1)
            continue

        offset = max((day - plan.start_date).days, 0)
        if spacing > 1 and offset % spacing != 0:
            day += timedelta(days=1)
            continue

        if pool:
            if plan.mode == "random":
                recipe_id = _pick_random(pool, last_recipe_id, rng)
            else:
                recipe_id = pool[recipe_slot(plan, offset) % len(pool)]
        else:
            recipe_id = None

        entry = CalendarEntry(
            plan_id=plan.id, entry_date=day, recipe_id=recipe_id, status="planned"
        )
        session.add(entry)
        created += 1
        last_recipe_id = recipe_id
        day += timedelta(days=1)

    if created:
        session.commit()
    return created


def entries_for_range(
    session: Session, plan: RotationPlan, start: date, end: date
) -> list[CalendarEntry]:
    generate_entries(session, plan, start, end)
    return list(
        session.execute(
            select(CalendarEntry)
            .where(
                CalendarEntry.plan_id == plan.id,
                CalendarEntry.entry_date >= start,
                CalendarEntry.entry_date <= end,
            )
            .order_by(CalendarEntry.entry_date)
        )
        .scalars()
        .all()
    )


def swap_entry(session: Session, entry: CalendarEntry) -> None:
    """Replace the recipe on an entry with a different one from the plan pool."""
    pool = plan_pool(session, entry.plan)
    if not pool:
        return
    candidates = [rid for rid in pool if rid != entry.recipe_id] or pool
    entry.recipe_id = random.choice(candidates)
    entry.status = "planned"
    session.commit()
