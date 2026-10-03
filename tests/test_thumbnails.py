"""Image thumbnails: generation, serving and lazy backfill."""

from __future__ import annotations

import io

from PIL import Image
from sqlalchemy import select

from app.models import Attachment
from app.storage import make_thumbnail


def _png_bytes(size=(1200, 800), color=(200, 100, 50)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "PNG")
    return buffer.getvalue()


def test_make_thumbnail_downscales_to_jpeg(tmp_path):
    source = tmp_path / "big.png"
    source.write_bytes(_png_bytes((1200, 800)))
    destination = tmp_path / "small.jpg"

    assert make_thumbnail(source, destination) is True
    assert destination.exists()
    with Image.open(destination) as image:
        assert max(image.size) <= 480
        assert image.format == "JPEG"
    assert destination.stat().st_size < source.stat().st_size


def test_make_thumbnail_handles_transparency(tmp_path):
    buffer = io.BytesIO()
    Image.new("RGBA", (600, 600), (0, 0, 0, 0)).save(buffer, "PNG")
    source = tmp_path / "transparent.png"
    source.write_bytes(buffer.getvalue())

    destination = tmp_path / "thumb.jpg"
    assert make_thumbnail(source, destination) is True
    with Image.open(destination) as image:
        assert image.mode == "RGB"


def test_upload_creates_thumbnail(client, app, make_recipe):
    recipe_id = make_recipe("With photo")
    response = client.post(
        f"/recipes/{recipe_id}/attachments",
        files={"files": ("photo.png", _png_bytes(), "image/png")},
        follow_redirects=False,
    )
    assert response.status_code == 303

    media_dir = app.state.settings.media_dir
    with app.state.db.session() as session:
        attachment = session.execute(select(Attachment)).scalar_one()
        attachment_id = attachment.id
        assert attachment.kind == "image"
        assert attachment.thumbnail_name
        assert (media_dir / attachment.thumbnail_name).exists()

    response = client.get(f"/attachments/{attachment_id}/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content


def test_thumbnail_generated_lazily_for_existing_images(client, app, make_recipe):
    recipe_id = make_recipe("Lazy")
    client.post(
        f"/recipes/{recipe_id}/attachments",
        files={"files": ("photo.png", _png_bytes(), "image/png")},
        follow_redirects=False,
    )

    media_dir = app.state.settings.media_dir
    with app.state.db.session() as session:
        attachment = session.execute(select(Attachment)).scalar_one()
        attachment_id = attachment.id
        (media_dir / attachment.thumbnail_name).unlink()
        attachment.thumbnail_name = None
        session.commit()

    response = client.get(f"/attachments/{attachment_id}/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"

    with app.state.db.session() as session:
        assert session.get(Attachment, attachment_id).thumbnail_name is not None


def test_thumbnail_404_for_non_image(client, app, make_recipe):
    recipe_id = make_recipe("Text only")
    client.post(
        f"/recipes/{recipe_id}/attachments",
        files={"files": ("note.txt", b"hello", "text/plain")},
        follow_redirects=False,
    )
    with app.state.db.session() as session:
        attachment_id = session.execute(select(Attachment)).scalar_one().id
    assert client.get(f"/attachments/{attachment_id}/thumbnail").status_code == 404


def test_recipe_card_uses_thumbnail(client, make_recipe):
    recipe_id = make_recipe("Card")
    client.post(
        f"/recipes/{recipe_id}/attachments",
        files={"files": ("photo.png", _png_bytes(), "image/png")},
        follow_redirects=False,
    )
    page = client.get("/").text
    assert "/thumbnail" in page
