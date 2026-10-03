"""Attachment upload, serving and deletion."""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse

from ..auth import CurrentUser
from ..deps import DbSession, SettingsDep
from ..i18n import translate
from ..models import Attachment, Recipe
from ..storage import delete_upload, ensure_thumbnail, save_upload
from ..templating import flash

router = APIRouter()


@router.post("/recipes/{recipe_id}/attachments")
def upload_attachments(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    recipe_id: int,
    files: list[UploadFile] = File(default=[]),
):
    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(404, "Recipe not found")
    saved = 0
    for upload in files:
        if upload and upload.filename and save_upload(session, recipe, upload, settings.media_dir):
            saved += 1
    session.commit()
    if saved:
        flash(request, translate(request, "flash.attachments_added", count=saved))
    else:
        flash(request, translate(request, "flash.no_files"), "error")
    return RedirectResponse(f"/recipes/{recipe_id}", status_code=303)


@router.get("/attachments/{attachment_id}")
def serve_attachment(
    session: DbSession,
    settings: SettingsDep,
    user: CurrentUser,
    attachment_id: int,
):
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(404, "Attachment not found")
    path = settings.media_dir / attachment.stored_name
    if not path.exists():
        raise HTTPException(404, "File is missing on disk")
    return FileResponse(path, media_type=attachment.content_type)


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    session: DbSession,
    settings: SettingsDep,
    user: CurrentUser,
    attachment_id: int,
):
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(404, "Attachment not found")
    path = settings.media_dir / attachment.stored_name
    if not path.exists():
        raise HTTPException(404, "File is missing on disk")
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.original_name,
        content_disposition_type="attachment",
    )


@router.get("/attachments/{attachment_id}/thumbnail")
def serve_thumbnail(
    session: DbSession,
    settings: SettingsDep,
    user: CurrentUser,
    attachment_id: int,
):
    attachment = session.get(Attachment, attachment_id)
    if attachment is None or attachment.kind != "image":
        raise HTTPException(404, "No thumbnail for this attachment")

    source = settings.media_dir / attachment.stored_name
    if not source.exists():
        raise HTTPException(404, "File is missing on disk")

    name = ensure_thumbnail(settings.media_dir, attachment)
    if name:
        session.commit()
        return FileResponse(settings.media_dir / name, media_type="image/jpeg")

    # If a thumbnail could not be produced, fall back to the original image.
    return FileResponse(source, media_type=attachment.content_type)


@router.post("/attachments/{attachment_id}/delete")
def delete_attachment(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    attachment_id: int,
):
    attachment = session.get(Attachment, attachment_id)
    if attachment is None:
        raise HTTPException(404, "Attachment not found")
    recipe_id = attachment.recipe_id
    name = attachment.original_name
    delete_upload(settings.media_dir, attachment)
    session.delete(attachment)
    session.commit()
    flash(request, translate(request, "flash.attachment_removed", name=name), "info")
    return RedirectResponse(f"/recipes/{recipe_id}", status_code=303)
