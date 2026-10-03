"""Recipe CRUD, search and filtering."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..auth import CurrentUser
from ..config import Settings
from ..deps import DbSession, SettingsDep
from ..link_preview import fetch_recipe_image
from ..models import Recipe, Tag
from ..recipe_import import extract_recipe, fetch_html
from ..storage import delete_upload, read_text, save_bytes, save_upload
from ..templating import flash, render
from ..utils import parse_tag_names

router = APIRouter()


def _resolve_tags(session: Session, raw: str) -> list[Tag]:
    tags: list[Tag] = []
    for name in parse_tag_names(raw):
        tag = session.execute(
            select(Tag).where(func.lower(Tag.name) == name.lower())
        ).scalar_one_or_none()
        if tag is None:
            tag = Tag(name=name)
            session.add(tag)
            session.flush()
        tags.append(tag)
    return tags


def _get_recipe(session: Session, recipe_id: int) -> Recipe:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


def _all_tags(session: Session) -> list[Tag]:
    return list(session.execute(select(Tag).order_by(func.lower(Tag.name))).scalars().all())


def _form_context(session: Session, recipe: Recipe | None, form_tags: str) -> dict:
    return {"recipe": recipe, "all_tags": _all_tags(session), "form_tags": form_tags}


def _import_image_from_link(session: Session, recipe: Recipe, settings: Settings) -> bool:
    """Try to download a preview image from the recipe's source link."""
    if not recipe.source_url:
        return False
    result = fetch_recipe_image(recipe.source_url)
    if result is None:
        return False
    filename, data, content_type = result
    save_bytes(session, recipe, filename, data, content_type, settings.media_dir)
    return True


@router.get("/", response_class=HTMLResponse)
def list_recipes(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    q: str = "",
    tag: list[str] = Query(default=[]),
    sort: str = "name",
):
    stmt = select(Recipe)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Recipe.name.ilike(like),
                Recipe.description.ilike(like),
                Recipe.ingredients.ilike(like),
                Recipe.instructions.ilike(like),
            )
        )
    for tag_name in [t for t in tag if t.strip()]:
        stmt = stmt.where(Recipe.tags.any(func.lower(Tag.name) == tag_name.lower()))

    if sort == "newest":
        stmt = stmt.order_by(Recipe.created_at.desc())
    elif sort == "oldest":
        stmt = stmt.order_by(Recipe.created_at.asc())
    else:
        stmt = stmt.order_by(func.lower(Recipe.name))

    recipes = list(session.execute(stmt).scalars().all())
    context = {
        "recipes": recipes,
        "q": q,
        "selected_tags": [t for t in tag if t.strip()],
        "sort": sort,
        "all_tags": _all_tags(session),
    }
    if request.headers.get("HX-Request"):
        return render(request, "recipes/_results.html", **context)
    return render(request, "recipes/list.html", **context)


@router.get("/recipes/new", response_class=HTMLResponse)
def new_recipe(request: Request, session: DbSession, user: CurrentUser):
    return render(request, "recipes/form.html", **_form_context(session, None, ""))


@router.post("/recipes")
def create_recipe(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    name: str = Form(...),
    description: str = Form(""),
    source_url: str = Form(""),
    ingredients: str = Form(""),
    instructions: str = Form(""),
    tags: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    import_image: bool = Form(False),
):
    recipe = Recipe(
        name=name.strip(),
        description=description.strip(),
        source_url=source_url.strip(),
        ingredients=ingredients.strip(),
        instructions=instructions.strip(),
    )
    recipe.tags = _resolve_tags(session, tags)
    session.add(recipe)
    session.flush()
    for upload in files:
        if upload and upload.filename:
            save_upload(session, recipe, upload, settings.media_dir)
    imported = _import_image_from_link(session, recipe, settings) if import_image else False
    session.commit()
    flash(request, f'Recipe "{recipe.name}" created.')
    if import_image and not imported:
        flash(request, "Could not import an image from the source link.", "error")
    return RedirectResponse(f"/recipes/{recipe.id}?created=1", status_code=303)


@router.post("/recipes/import")
def import_recipe_from_url(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    url: str = Form(...),
):
    target = url.strip()
    fetched = fetch_html(target)
    if fetched is None:
        flash(request, "Could not fetch that URL.", "error")
        return RedirectResponse("/recipes/new", status_code=303)

    html, final_url = fetched
    data = extract_recipe(html, final_url)
    if data is None:
        flash(request, "No recipe information was found on that page.", "error")
        return RedirectResponse("/recipes/new", status_code=303)

    recipe = Recipe(
        name=data.name[:255],
        description=data.description,
        source_url=(data.source_url or final_url)[:2048],
        ingredients=data.ingredients,
        instructions=data.instructions,
    )
    recipe.tags = _resolve_tags(session, ", ".join(data.tags))
    session.add(recipe)
    session.flush()

    imported_image = False
    if data.image_url:
        result = fetch_recipe_image(data.image_url)
        if result is not None:
            filename, image_data, content_type = result
            save_bytes(session, recipe, filename, image_data, content_type, settings.media_dir)
            imported_image = True

    session.commit()
    flash(request, f'Imported "{recipe.name}".')
    if data.image_url and not imported_image:
        flash(request, "Could not download the recipe image.", "error")
    return RedirectResponse(f"/recipes/{recipe.id}?created=1", status_code=303)


@router.get("/recipes/{recipe_id}/edit", response_class=HTMLResponse)
def edit_recipe(request: Request, session: DbSession, user: CurrentUser, recipe_id: int):
    recipe = _get_recipe(session, recipe_id)
    form_tags = ", ".join(tag.name for tag in recipe.tags)
    return render(request, "recipes/form.html", **_form_context(session, recipe, form_tags))


@router.post("/recipes/{recipe_id}")
def update_recipe(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    recipe_id: int,
    name: str = Form(...),
    description: str = Form(""),
    source_url: str = Form(""),
    ingredients: str = Form(""),
    instructions: str = Form(""),
    tags: str = Form(""),
    files: list[UploadFile] = File(default=[]),
    import_image: bool = Form(False),
):
    recipe = _get_recipe(session, recipe_id)
    recipe.name = name.strip()
    recipe.description = description.strip()
    recipe.source_url = source_url.strip()
    recipe.ingredients = ingredients.strip()
    recipe.instructions = instructions.strip()
    recipe.tags = _resolve_tags(session, tags)
    for upload in files:
        if upload and upload.filename:
            save_upload(session, recipe, upload, settings.media_dir)
    imported = _import_image_from_link(session, recipe, settings) if import_image else False
    session.commit()
    flash(request, f'Recipe "{recipe.name}" updated.')
    if import_image and not imported:
        flash(request, "Could not import an image from the source link.", "error")
    return RedirectResponse(f"/recipes/{recipe.id}", status_code=303)


@router.get("/recipes/{recipe_id}", response_class=HTMLResponse)
def recipe_detail(
    request: Request, session: DbSession, user: CurrentUser, settings: SettingsDep, recipe_id: int
):
    recipe = _get_recipe(session, recipe_id)
    text_previews = {a.id: read_text(settings.media_dir, a) for a in recipe.text_attachments}
    return render(request, "recipes/detail.html", recipe=recipe, text_previews=text_previews)


@router.post("/recipes/{recipe_id}/delete")
def delete_recipe(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    recipe_id: int,
):
    recipe = _get_recipe(session, recipe_id)
    name = recipe.name
    for attachment in list(recipe.attachments):
        delete_upload(settings.media_dir, attachment)
    session.delete(recipe)
    session.commit()
    flash(request, f'Recipe "{name}" deleted.', "info")
    return RedirectResponse("/", status_code=303)


@router.post("/recipes/{recipe_id}/import-image")
def import_image_from_link(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    settings: SettingsDep,
    recipe_id: int,
):
    recipe = _get_recipe(session, recipe_id)
    if not recipe.source_url:
        flash(request, "This recipe has no source link to import from.", "error")
    elif _import_image_from_link(session, recipe, settings):
        session.commit()
        flash(request, "Image imported from the source link.")
    else:
        flash(request, "Could not find an image at the source link.", "error")
    return RedirectResponse(f"/recipes/{recipe_id}", status_code=303)
