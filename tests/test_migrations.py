"""Tests for the lightweight additive schema migrations."""

from __future__ import annotations

import sqlite3

from sqlalchemy import inspect

from app.database import Database


def test_spacing_column_added_to_legacy_database(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    db_path = data_dir / "legacy.db"

    # A pre-spacing rotation_plans table.
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE rotation_plans ("
        "id INTEGER PRIMARY KEY, name TEXT, mode TEXT, interval TEXT, "
        "active BOOLEAN, start_date DATE, created_at DATETIME)"
    )
    connection.commit()
    connection.close()

    database = Database(f"sqlite:///{db_path}")
    try:
        database.create_all()
        columns = {column["name"] for column in inspect(database.engine).get_columns("rotation_plans")}
        assert "spacing" in columns

        # Running again must be a no-op (idempotent).
        database.create_all()
    finally:
        database.dispose()


def test_calendar_entries_rebuilt_for_meals(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    db_path = data_dir / "legacy_entries.db"

    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE rotation_plans (
            id INTEGER PRIMARY KEY, name TEXT, mode TEXT, interval TEXT,
            active BOOLEAN, start_date DATE, created_at DATETIME);
        CREATE TABLE recipes (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, description TEXT, source_url TEXT,
            ingredients TEXT, instructions TEXT, created_at DATETIME, updated_at DATETIME);
        CREATE TABLE calendar_entries (
            id INTEGER PRIMARY KEY, plan_id INTEGER NOT NULL, entry_date DATE NOT NULL,
            recipe_id INTEGER, status VARCHAR(20) NOT NULL, note TEXT NOT NULL,
            created_at DATETIME NOT NULL,
            CONSTRAINT uq_entry_plan_date UNIQUE (plan_id, entry_date));
        INSERT INTO rotation_plans (id, name, mode, interval, active, start_date, created_at)
            VALUES (1, 'Old', 'fixed', 'weekly', 1, '2026-01-05', '2026-01-01');
        INSERT INTO recipes (id, name) VALUES (1, 'Old recipe');
        INSERT INTO calendar_entries (id, plan_id, entry_date, recipe_id, status, note, created_at)
            VALUES (1, 1, '2026-01-05', 1, 'cooked', '', '2026-01-01');
        """
    )
    connection.commit()
    connection.close()

    database = Database(f"sqlite:///{db_path}")
    try:
        database.create_all()
        columns = {
            column["name"] for column in inspect(database.engine).get_columns("calendar_entries")
        }
        assert "meal" in columns

        with database.engine.connect() as connection:
            rows = list(
                connection.exec_driver_sql("SELECT id, meal, status FROM calendar_entries")
            )
        assert rows == [(1, "", "cooked")]  # existing row preserved as the single meal

        # A second meal on the same day is now allowed (old constraint dropped).
        with database.engine.begin() as connection:
            connection.exec_driver_sql(
                "INSERT INTO calendar_entries "
                "(plan_id, entry_date, meal, recipe_id, status, note, created_at) "
                "VALUES (1, '2026-01-05', 'Dinner', 1, 'planned', '', '2026-01-01')"
            )
    finally:
        database.dispose()
