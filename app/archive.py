"""Portable archive (zip) export/import: the SQLite database plus all media files.

Archive layout::

    recipebook.db          # the SQLite database
    manifest.json          # format/version/counts metadata
    media/<stored_name>    # every uploaded attachment, by stored filename

The archive is what makes backups truly portable: the existing ``.sqlite`` export
captures the database but not the image/text files those rows point at.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import __version__

ARCHIVE_DB_NAME = "recipebook.db"
ARCHIVE_MANIFEST = "manifest.json"
ARCHIVE_MEDIA_DIR = "media"
ARCHIVE_MEDIA_PREFIX = "media/"
ARCHIVE_FORMAT = "recipebook-archive"
ARCHIVE_VERSION = 1

SQLITE_MAGIC = b"SQLite format 3\x00"
EXPECTED_TABLES = {"recipes", "tags", "attachments"}


@dataclass
class ArchiveContents:
    """A validated archive extracted into ``tmpdir``."""

    tmpdir: Path
    db_path: Path
    media_dir: Path
    manifest: dict


def build_archive(db_path: Path, media_dir: Path, counts: dict, destination: Path) -> Path:
    """Write a portable archive of ``db_path`` + ``media_dir`` to ``destination``."""
    media_files = (
        sorted(p for p in media_dir.glob("*") if p.is_file()) if media_dir.exists() else []
    )
    manifest = {
        "format": ARCHIVE_FORMAT,
        "version": ARCHIVE_VERSION,
        "app_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "media_files": len(media_files),
    }
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(db_path, ARCHIVE_DB_NAME)
        for media in media_files:
            archive.write(media, f"{ARCHIVE_MEDIA_PREFIX}{media.name}")
        archive.writestr(ARCHIVE_MANIFEST, json.dumps(manifest, indent=2))
    return destination


def _is_safe_member(name: str) -> bool:
    """Reject absolute paths and directory traversal (``../``)."""
    if not name or name.startswith(("/", "\\")):
        return False
    if len(name) > 1 and name[1] == ":":  # Windows drive letter
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _database_is_valid(db_path: Path) -> bool:
    with db_path.open("rb") as handle:
        if handle.read(16) != SQLITE_MAGIC:
            return False
    try:
        connection = sqlite3.connect(db_path)
        try:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        finally:
            connection.close()
    except sqlite3.DatabaseError:
        return False
    return EXPECTED_TABLES.issubset(tables)


def inspect_archive(fileobj) -> tuple[ArchiveContents | None, str | None]:
    """Validate an uploaded archive and extract it to a temp dir.

    Returns ``(contents, error)``. On any error the temp dir is cleaned up.
    """
    try:
        archive = zipfile.ZipFile(fileobj)
    except zipfile.BadZipFile:
        return None, "flash.archive_bad_zip"

    with archive:
        names = archive.namelist()
        if any(not _is_safe_member(name) for name in names):
            return None, "flash.archive_unsafe"
        if ARCHIVE_DB_NAME not in names:
            return None, "flash.archive_no_db"

        tmpdir = Path(tempfile.mkdtemp(prefix="recipebook-import-"))
        archive.extractall(tmpdir)

    db_path = tmpdir / ARCHIVE_DB_NAME
    if not _database_is_valid(db_path):
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, "flash.archive_bad_db"

    manifest: dict = {}
    manifest_path = tmpdir / ARCHIVE_MANIFEST
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            manifest = {}

    return (
        ArchiveContents(
            tmpdir=tmpdir, db_path=db_path, media_dir=tmpdir / ARCHIVE_MEDIA_DIR, manifest=manifest
        ),
        None,
    )


def discard_archive(contents: ArchiveContents) -> None:
    shutil.rmtree(contents.tmpdir, ignore_errors=True)
