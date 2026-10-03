"""Tag management."""

from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select

from ..auth import CurrentUser
from ..deps import DbSession
from ..i18n import translate
from ..models import Tag, recipe_tags
from ..templating import flash, render

router = APIRouter()


@router.get("/tags", response_class=HTMLResponse)
def list_tags(request: Request, session: DbSession, user: CurrentUser):
    rows = session.execute(
        select(Tag, func.count(recipe_tags.c.recipe_id))
        .outerjoin(recipe_tags, Tag.id == recipe_tags.c.tag_id)
        .group_by(Tag.id)
        .order_by(func.lower(Tag.name))
    ).all()
    return render(request, "tags/list.html", tag_rows=rows)


@router.post("/tags/{tag_id}/rename")
def rename_tag(request: Request, session: DbSession, user: CurrentUser, tag_id: int, name: str = Form(...)):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404, "Tag not found")
    new_name = " ".join(name.split())
    if new_name:
        existing = session.execute(
            select(Tag).where(func.lower(Tag.name) == new_name.lower(), Tag.id != tag.id)
        ).scalar_one_or_none()
        if existing is not None:
            flash(request, translate(request, "flash.tag_exists", name=new_name), "error")
        else:
            tag.name = new_name
            session.commit()
            flash(request, translate(request, "flash.tag_renamed", name=new_name))
    return RedirectResponse("/tags", status_code=303)


@router.post("/tags/{tag_id}/delete")
def delete_tag(request: Request, session: DbSession, user: CurrentUser, tag_id: int):
    tag = session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(404, "Tag not found")
    name = tag.name
    session.delete(tag)
    session.commit()
    flash(request, translate(request, "flash.tag_deleted", name=name), "info")
    return RedirectResponse("/tags", status_code=303)
