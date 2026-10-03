"""Data management: database, portable archive and JSON export/import."""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from .. import __version__
from ..archive import build_archive, discard_archive, inspect_archive
from ..auth import CurrentUser
from ..deps import DbSession, SettingsDep
from ..i18n import translate
from ..models import Attachment, Recipe, Tag
from ..templating import flash, render

router = APIRouter()

SQLITE_MAGIC = b"SQLite format 3\x00"
EXPECTED_TABLES = {"recipes", "tags", "attachments"}


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _counts(session: Session) -> dict:
    return {
        "recipes": session.scalar(select(func.count()).select_from(Recipe)) or 0,
        "tags": session.scalar(select(func.count()).select_from(Tag)) or 0,
        "attachments": session.scalar(select(func.count()).select_from(Attachment)) or 0,
    }


def _checkpoint(request: Request) -> None:
    """Flush the SQLite WAL so the on-disk database file is complete."""
    engine = request.app.state.db.engine
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")


def _recipe_to_dict(recipe: Recipe) -> dict:
    return {
        "id": recipe.id,
        "name": recipe.name,
        "description": recipe.description,
        "source_url": recipe.source_url,
        "ingredients": recipe.ingredients,
        "instructions": recipe.instructions,
        "created_at": recipe.created_at.isoformat() if recipe.created_at else None,
        "updated_at": recipe.updated_at.isoformat() if recipe.updated_at else None,
        "tags": [tag.name for tag in recipe.tags],
        "attachments": [
            {
                "original_name": attachment.original_name,
                "kind": attachment.kind,
                "content_type": attachment.content_type,
                "size": attachment.size,
            }
            for attachment in recipe.attachments
        ],
    }


@router.get("/data", response_class=HTMLResponse)
def data_page(
    request: Request, session: DbSession, user: CurrentUser, settings: SettingsDep
):
    sqlite_path = settings.sqlite_path
    db_size = sqlite_path.stat().st_size if sqlite_path and sqlite_path.exists() else 0
    media_files = (
        [p for p in settings.media_dir.glob("*") if p.is_file()]
        if settings.media_dir.exists()
        else []
    )
    return render(
        request,
        "data/index.html",
        db_size=db_size,
        media_size=sum(p.stat().st_size for p in media_files),
        media_count=len(media_files),
        counts=_counts(session),
        db_path=str(sqlite_path) if sqlite_path else "(not a file-based database)",
    )


@router.get("/data/export")
def export_db(request: Request, user: CurrentUser, settings: SettingsDep):
    path = settings.sqlite_path
    if path is None or not path.exists():
        raise HTTPException(404, "No SQLite database to export")
    _checkpoint(request)
    filename = f"recipebook-{_timestamp()}.sqlite"
    return FileResponse(path, media_type="application/x-sqlite3", filename=filename)


@router.get("/data/export/archive")
def export_archive(
    request: Request, session: DbSession, user: CurrentUser, settings: SettingsDep
):
    path = settings.sqlite_path
    if path is None or not path.exists():
        raise HTTPException(404, "No SQLite database to export")
    _checkpoint(request)

    export_dir = Path(tempfile.mkdtemp(prefix="recipebook-export-"))
    destination = export_dir / "recipebook-archive.zip"
    build_archive(path, settings.media_dir, _counts(session), destination)

    filename = f"recipebook-archive-{_timestamp()}.zip"
    return FileResponse(
        destination,
        media_type="application/zip",
        filename=filename,
        background=BackgroundTask(shutil.rmtree, export_dir, True),
    )


@router.get("/data/export/json")
def export_json(session: DbSession, user: CurrentUser):
    recipes = session.execute(select(Recipe).order_by(Recipe.id)).scalars().all()
    tags = session.execute(select(Tag).order_by(func.lower(Tag.name))).scalars().all()
    payload = {
        "format": "recipebook-json",
        "version": 1,
        "app_version": __version__,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "counts": _counts(session),
        "tags": [{"id": tag.id, "name": tag.name} for tag in tags],
        "recipes": [_recipe_to_dict(recipe) for recipe in recipes],
    }
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    filename = f"recipebook-{_timestamp()}.json"
    return Response(
        body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/data/import/archive")
def import_archive(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    file: UploadFile = File(...),
):
    path = settings.sqlite_path
    if path is None:
        raise HTTPException(400, "Only file-based SQLite databases can be imported")

    contents, error = inspect_archive(file.file)
    if error or contents is None:
        message = translate(request, error) if error else translate(request, "flash.archive_unreadable")
        flash(request, message, "error")
        return RedirectResponse("/data", status_code=303)

    # Close the current session and pooled connections before swapping files.
    session.close()
    request.app.state.db.engine.dispose()

    stamp = _timestamp()

    db_backup = path.with_name(f"{path.stem}.backup-{stamp}{path.suffix}")
    if path.exists():
        shutil.move(str(path), str(db_backup))
    for sidecar in (path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
        sidecar.unlink(missing_ok=True)
    shutil.move(str(contents.db_path), str(path))

    media_backup = settings.media_dir.with_name(f"{settings.media_dir.name}.backup-{stamp}")
    if settings.media_dir.exists():
        shutil.move(str(settings.media_dir), str(media_backup))
    settings.media_dir.mkdir(parents=True, exist_ok=True)
    if contents.media_dir.exists():
        for media in contents.media_dir.iterdir():
            if media.is_file():
                shutil.move(str(media), str(settings.media_dir / media.name))

    discard_archive(contents)
    request.app.state.db.reload()

    flash(
        request,
        translate(
            request, "flash.archive_imported", db=db_backup.name, media=media_backup.name
        ),
    )
    return RedirectResponse("/", status_code=303)


@router.post("/data/import")
def import_db(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    file: UploadFile = File(...),
):
    path = settings.sqlite_path
    if path is None:
        raise HTTPException(400, "Only file-based SQLite databases can be imported")

    data = file.file.read()
    if not data.startswith(SQLITE_MAGIC):
        flash(request, translate(request, "flash.bad_sqlite"), "error")
        return RedirectResponse("/data", status_code=303)

    tmp_path = path.with_name(path.name + ".import.tmp")
    tmp_path.write_bytes(data)

    try:
        connection = sqlite3.connect(tmp_path)
        try:
            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        finally:
            connection.close()
    except sqlite3.DatabaseError:
        tmp_path.unlink(missing_ok=True)
        flash(request, translate(request, "flash.bad_sqlite_file"), "error")
        return RedirectResponse("/data", status_code=303)

    if not EXPECTED_TABLES.issubset(tables):
        tmp_path.unlink(missing_ok=True)
        flash(request, translate(request, "flash.not_recipebook"), "error")
        return RedirectResponse("/data", status_code=303)

    # Close the current session and pooled connections before swapping the file.
    session.close()
    request.app.state.db.engine.dispose()

    backup = path.with_name(
        f"{path.stem}.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}{path.suffix}"
    )
    if path.exists():
        shutil.move(str(path), str(backup))
    for sidecar in (path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
        sidecar.unlink(missing_ok=True)

    shutil.move(str(tmp_path), str(path))
    request.app.state.db.reload()

    flash(request, translate(request, "flash.db_imported", name=backup.name))
    return RedirectResponse("/", status_code=303)
