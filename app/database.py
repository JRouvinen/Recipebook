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
    },
}


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
                    connection.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}')
