"""Runtime configuration.

Everything can be overridden with environment variables so the same image can run
locally and in Docker:

* ``RECIPEBOOK_DATA_DIR``   – directory holding the SQLite DB and media (default ``./data``)
* ``RECIPEBOOK_DATABASE_URL`` – full SQLAlchemy URL (default: SQLite in the data dir)
* ``RECIPEBOOK_MEDIA_DIR``  – directory for uploaded attachments (default: ``<data>/media``)
* ``RECIPEBOOK_SECRET_KEY`` – session signing key
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

APP_NAME = "Recipebook"
APP_VERSION = "1.0.0"


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


@dataclass
class Settings:
    app_name: str = APP_NAME
    app_version: str = APP_VERSION
    data_dir: Path = field(
        default_factory=lambda: _env_path("RECIPEBOOK_DATA_DIR", PROJECT_ROOT / "data")
    )
    media_dir: Path | None = None
    database_url: str | None = None
    secret_key: str = field(
        default_factory=lambda: os.environ.get("RECIPEBOOK_SECRET_KEY", "dev-secret-change-me")
    )
    max_upload_mb: int = 200

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir).expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)

        if self.media_dir is None:
            self.media_dir = _env_path("RECIPEBOOK_MEDIA_DIR", self.data_dir / "media")
        self.media_dir = Path(self.media_dir).expanduser()
        self.media_dir.mkdir(parents=True, exist_ok=True)

        if self.database_url is None:
            self.database_url = (
                os.environ.get("RECIPEBOOK_DATABASE_URL")
                or f"sqlite:///{self.data_dir / 'recipebook.db'}"
            )

    @property
    def sqlite_path(self) -> Path | None:
        """Filesystem path of the SQLite database, if this is a file-based SQLite DB."""
        url = self.database_url or ""
        if url.startswith("sqlite:///") and ":memory:" not in url:
            return Path(url[len("sqlite:///") :])
        return None


def get_settings() -> Settings:
    return Settings()
