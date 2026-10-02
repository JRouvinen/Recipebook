"""Rotation-calendar logic.

A plan assigns **one recipe per day**. ``interval`` controls the repeating cycle
length (weekly = 7 days, monthly = 30 days); the chosen recipes wrap/repeat:

* ``fixed``  – recipes from the plan (ordered) are laid out one per day and repeat
  every cycle.
* ``random`` – a random recipe is chosen for each day, avoiding an immediate repeat.
  Choices are persisted as ``CalendarEntry`` rows, so the schedule is stable and can
  be marked cooked/skipped or swapped.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CalendarEntry, Recipe, RotationItem, RotationPlan

CYCLE_LENGTHS = {"weekly": 7, "monthly": 30}


def cycle_length(plan: RotationPlan) -> int:
    return CYCLE_LENGTHS.get(plan.interval, 7)


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


def _pick_fixed(pool: list[int], plan: RotationPlan, day: date) -> int:
    offset = max((day - plan.start_date).days, 0)
    index = (offset % cycle_length(plan)) % len(pool)
    return pool[index]


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
    """Create any missing ``CalendarEntry`` rows for ``plan`` between two dates."""
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

    pool = plan_pool(session, plan)
    created = 0
    day = start
    while day <= end:
        entry = existing.get(day)
        if entry is None:
            if not pool:
                recipe_id = None
            elif plan.mode == "random":
                recipe_id = _pick_random(pool, last_recipe_id, rng)
            else:
                recipe_id = _pick_fixed(pool, plan, day)
            entry = CalendarEntry(
                plan_id=plan.id, entry_date=day, recipe_id=recipe_id, status="planned"
            )
            session.add(entry)
            created += 1
        last_recipe_id = entry.recipe_id
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
