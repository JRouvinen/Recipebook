"""Portable archive (zip) and JSON export/import."""

from __future__ import annotations

import io
import json
import zipfile

from sqlalchemy import select

from app.archive import ARCHIVE_FORMAT
from app.models import Attachment


def _add_attachment(client, recipe_id, name="note.txt", payload=b"hello"):
    return client.post(
        f"/recipes/{recipe_id}/attachments",
        files={"files": (name, payload, "text/plain")},
        follow_redirects=False,
    )


def test_export_archive_contains_db_media_and_manifest(client, make_recipe):
    recipe_id = make_recipe("Archived")
    _add_attachment(client, recipe_id)

    response = client.get("/data/export/archive")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = archive.namelist()
    assert "recipebook.db" in names
    assert "manifest.json" in names
    assert any(name.startswith("media/") for name in names)

    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["format"] == ARCHIVE_FORMAT
    assert manifest["counts"]["recipes"] == 1
    assert manifest["media_files"] == 1


def test_archive_roundtrip_restores_recipes_and_media(client, app, make_recipe):
    keep = make_recipe("Keep me", tags="Dinner")
    _add_attachment(client, keep, payload=b"payload")
    archive_bytes = client.get("/data/export/archive").content

    # Mutate state so we can prove the restore rolls it back.
    make_recipe("Should disappear")
    assert "Should disappear" in client.get("/").text

    response = client.post(
        "/data/import/archive",
        files={"file": ("backup.zip", archive_bytes, "application/zip")},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/").text
    assert "Keep me" in page
    assert "Should disappear" not in page

    media_dir = app.state.settings.media_dir
    with app.state.db.session() as session:
        attachment = session.execute(select(Attachment)).scalars().one()
    assert (media_dir / attachment.stored_name).exists()


def test_import_archive_rejects_invalid_zip(client):
    response = client.post(
        "/data/import/archive",
        files={"file": ("bad.zip", b"definitely not a zip", "application/zip")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "not a valid zip" in client.get("/data").text


def test_import_archive_requires_database(client):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "hello")
    response = client.post(
        "/data/import/archive",
        files={"file": ("x.zip", buffer.getvalue(), "application/zip")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "does not contain a recipebook.db" in client.get("/data").text


def test_import_archive_rejects_unsafe_paths(client):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("recipebook.db", b"SQLite format 3\x00")
        archive.writestr("../evil.txt", "nope")
    response = client.post(
        "/data/import/archive",
        files={"file": ("evil.zip", buffer.getvalue(), "application/zip")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "unsafe file path" in client.get("/data").text


def test_json_export(client, make_recipe):
    make_recipe("JSON recipe", tags="Test, Dinner", ingredients="a\nb", instructions="c")
    response = client.get("/data/export/json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == "recipebook-json"
    assert payload["counts"]["recipes"] == 1
    recipe = payload["recipes"][0]
    assert recipe["name"] == "JSON recipe"
    assert set(recipe["tags"]) == {"Test", "Dinner"}
    assert recipe["ingredients"] == "a\nb"
    assert recipe["instructions"] == "c"


def test_data_page_offers_all_formats(client):
    page = client.get("/data").text
    assert "/data/export/archive" in page
    assert "/data/export/json" in page
    assert "/data/import/archive" in page
