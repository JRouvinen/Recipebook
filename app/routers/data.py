"""Database export and import (SQLite file download / upload)."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from ..auth import CurrentUser
from ..deps import DbSession, SettingsDep
from ..models import Attachment, Recipe, Tag
from ..templating import flash, render

router = APIRouter()

SQLITE_MAGIC = b"SQLite format 3\x00"
EXPECTED_TABLES = {"recipes", "tags", "attachments"}


@router.get("/data", response_class=HTMLResponse)
def data_page(request: Request, session: DbSession, user: CurrentUser, settings: SettingsDep):
    sqlite_path = settings.sqlite_path
    db_size = sqlite_path.stat().st_size if sqlite_path and sqlite_path.exists() else 0
    counts = {
        "recipes": session.scalar(select(func.count()).select_from(Recipe)) or 0,
        "tags": session.scalar(select(func.count()).select_from(Tag)) or 0,
        "attachments": session.scalar(select(func.count()).select_from(Attachment)) or 0,
    }
    media_size = sum(p.stat().st_size for p in settings.media_dir.glob("*") if p.is_file())
    return render(
        request,
        "data/index.html",
        db_size=db_size,
        media_size=media_size,
        counts=counts,
        db_path=str(sqlite_path) if sqlite_path else "(not a file-based database)",
    )


@router.get("/data/export")
def export_db(request: Request, user: CurrentUser, settings: SettingsDep):
    path = settings.sqlite_path
    if path is None or not path.exists():
        raise HTTPException(404, "No SQLite database to export")
    engine = request.app.state.db.engine
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")
    filename = f"recipebook-{datetime.now().strftime('%Y%m%d-%H%M%S')}.sqlite"
    return FileResponse(path, media_type="application/x-sqlite3", filename=filename)


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
        flash(request, "That file is not a SQLite database.", "error")
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
        flash(request, "The uploaded file is not a valid SQLite database.", "error")
        return RedirectResponse("/data", status_code=303)

    if not EXPECTED_TABLES.issubset(tables):
        tmp_path.unlink(missing_ok=True)
        flash(request, "That database does not look like a Recipebook export.", "error")
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

    flash(request, f"Database imported. Previous database backed up as {backup.name}.")
    return RedirectResponse("/", status_code=303)
