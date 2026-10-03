"""SQLAlchemy engine / session management."""

from __future__ import annotations

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def create_db_engine(database_url: str) -> Engine:
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(database_url, connect_args=connect_args, future=True)

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record) -> None:  # pragma: no cover - driver hook
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


class Database:
    """Small holder around the engine + session factory attached to ``app.state``."""

    def __init__(self, database_url: str):
        self.url = database_url
        self.engine = create_db_engine(database_url)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False, future=True
        )

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)
        apply_migrations(self.engine)

    def session(self) -> Session:
        return self.session_factory()

    def reload(self) -> None:
        """Rebuild the engine after the underlying SQLite file was replaced."""
        self.engine.dispose()
        self.engine = create_db_engine(self.url)
        self.session_factory.configure(bind=self.engine)
        self.create_all()

    def dispose(self) -> None:
        self.engine.dispose()


# ---------------------------------------------------------------------------
# Lightweight additive migrations
#
# ``Base.metadata.create_all`` only creates missing tables - it never alters an
# existing one. For the small additive changes this project needs, we add the
# missing columns by hand. Each entry is ``table -> {column: column DDL}`` and
# the operation is idempotent, so it is safe to run on every startup.
# ---------------------------------------------------------------------------
ADDITIVE_COLUMNS: dict[str, dict[str, str]] = {
    "rotation_plans": {
        "spacing": "INTEGER NOT NULL DEFAULT 1",
        "meals": "VARCHAR(255) NOT NULL DEFAULT ''",
    },
}

# New shape of calendar_entries (adds ``meal`` and a per-meal unique constraint).
CALENDAR_ENTRIES_DDL = """
CREATE TABLE calendar_entries (
    id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    entry_date DATE NOT NULL,
    meal VARCHAR(50) NOT NULL,
    recipe_id INTEGER,
    status VARCHAR(20) NOT NULL,
    note TEXT NOT NULL,
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_entry_plan_date_meal UNIQUE (plan_id, entry_date, meal),
    FOREIGN KEY(plan_id) REFERENCES rotation_plans (id) ON DELETE CASCADE,
    FOREIGN KEY(recipe_id) REFERENCES recipes (id) ON DELETE SET NULL
)
"""


def _migrate_calendar_entries_meals(engine: Engine) -> None:
    """Rebuild ``calendar_entries`` to add ``meal`` and its unique constraint.

    SQLite cannot alter table constraints, and the old table's
    ``UNIQUE(plan_id, entry_date)`` would block multiple meals on the same day, so the
    table is recreated (existing rows become the single unnamed meal, ``meal = ''``).
    """
    inspector = inspect(engine)
    if "calendar_entries" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("calendar_entries")}
    if "meal" in columns:
        return

    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE calendar_entries RENAME TO calendar_entries_old")
        connection.exec_driver_sql(CALENDAR_ENTRIES_DDL)
        connection.exec_driver_sql(
            "INSERT INTO calendar_entries "
            "(id, plan_id, entry_date, meal, recipe_id, status, note, created_at) "
            "SELECT id, plan_id, entry_date, '', recipe_id, status, note, created_at "
            "FROM calendar_entries_old"
        )
        connection.exec_driver_sql("DROP TABLE calendar_entries_old")
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_calendar_entries_plan_id "
            "ON calendar_entries (plan_id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_calendar_entries_entry_date "
            "ON calendar_entries (entry_date)"
        )


def apply_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    for table, columns in ADDITIVE_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {column["name"] for column in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name not in present:
                with engine.begin() as connection:
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    _migrate_calendar_entries_meals(engine)
