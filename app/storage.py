"""Attachment storage on the local filesystem (+ image thumbnails)."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from .models import Attachment, Recipe
from .utils import classify_attachment

try:  # Pillow is a dependency, but degrade gracefully if it is ever unavailable
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore[assignment]

THUMBNAIL_SIZE = (480, 480)
THUMBNAIL_QUALITY = 82


def make_thumbnail(source: Path, destination: Path, size: tuple[int, int] = THUMBNAIL_SIZE) -> bool:
    """Write a downscaled JPEG thumbnail of ``source`` to ``destination``."""
    if Image is None:
        return False
    try:
        with Image.open(source) as image:
            image.thumbnail(size, Image.Resampling.LANCZOS)
            if image.mode in ("RGBA", "LA") or (
                image.mode == "P" and "transparency" in image.info
            ):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, (255, 255, 255))
                background.paste(rgba, mask=rgba.split()[-1])
                image = background
            else:
                image = image.convert("RGB")
            image.save(destination, "JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
        return True
    except Exception:  # noqa: BLE001 - any decode/encode error just skips the thumbnail
        destination.unlink(missing_ok=True)
        return False


def ensure_thumbnail(media_dir: Path, attachment: Attachment) -> str | None:
    """Return the thumbnail filename for an image attachment, creating it if needed."""
    if attachment.kind != "image":
        return None
    if attachment.thumbnail_name and (media_dir / attachment.thumbnail_name).exists():
        return attachment.thumbnail_name

    source = media_dir / attachment.stored_name
    if not source.exists():
        return None

    name = f"{Path(attachment.stored_name).stem}_thumb.jpg"
    if make_thumbnail(source, media_dir / name):
        attachment.thumbnail_name = name
        return name
    return None


def save_bytes(
    session: Session,
    recipe: Recipe,
    filename: str,
    data: bytes,
    content_type: str,
    media_dir: Path,
) -> Attachment | None:
    """Persist raw bytes to ``media_dir`` and register them as an attachment."""
    original_name = Path(filename or "").name
    if not original_name or not data:
        return None

    suffix = Path(original_name).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    (media_dir / stored_name).write_bytes(data)

    content_type = content_type or "application/octet-stream"
    attachment = Attachment(
        recipe=recipe,
        original_name=original_name,
        stored_name=stored_name,
        content_type=content_type,
        kind=classify_attachment(original_name, content_type),
        size=len(data),
    )
    session.add(attachment)
    if attachment.kind == "image":
        ensure_thumbnail(media_dir, attachment)
    return attachment


def save_upload(
    session: Session, recipe: Recipe, upload: UploadFile, media_dir: Path
) -> Attachment | None:
    """Persist an uploaded file to ``media_dir`` and register it in the DB."""
    filename = Path(upload.filename or "").name
    if not filename:
        return None
    data = upload.file.read()
    return save_bytes(session, recipe, filename, data, upload.content_type or "", media_dir)


def delete_upload(media_dir: Path, attachment: Attachment) -> None:
    """Remove the backing file (and thumbnail) for an attachment (best effort)."""
    (media_dir / attachment.stored_name).unlink(missing_ok=True)
    if attachment.thumbnail_name:
        (media_dir / attachment.thumbnail_name).unlink(missing_ok=True)


def read_text(media_dir: Path, attachment: Attachment, limit: int = 200_000) -> str | None:
    """Return the text content of a text attachment, or ``None`` if unavailable."""
    path = media_dir / attachment.stored_name
    if not path.exists() or attachment.size > limit:
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
