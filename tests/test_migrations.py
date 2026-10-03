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
