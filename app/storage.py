"""Attachment storage on the local filesystem."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from .models import Attachment, Recipe
from .utils import classify_attachment


def save_upload(
    session: Session, recipe: Recipe, upload: UploadFile, media_dir: Path
) -> Attachment | None:
    """Persist an uploaded file to ``media_dir`` and register it in the DB."""
    original_name = Path(upload.filename or "").name
    if not original_name:
        return None

    data = upload.file.read()
    if not data:
        return None

    suffix = Path(original_name).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    (media_dir / stored_name).write_bytes(data)

    content_type = upload.content_type or "application/octet-stream"
    attachment = Attachment(
        recipe=recipe,
        original_name=original_name,
        stored_name=stored_name,
        content_type=content_type,
        kind=classify_attachment(original_name, content_type),
        size=len(data),
    )
    session.add(attachment)
    return attachment


def delete_upload(media_dir: Path, attachment: Attachment) -> None:
    """Remove the backing file for an attachment (best effort)."""
    (media_dir / attachment.stored_name).unlink(missing_ok=True)


def read_text(media_dir: Path, attachment: Attachment, limit: int = 200_000) -> str | None:
    """Return the text content of a text attachment, or ``None`` if unavailable."""
    path = media_dir / attachment.stored_name
    if not path.exists() or attachment.size > limit:
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
