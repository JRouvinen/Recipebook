"""Recipe CRUD, search, filtering, tags and attachments."""

from __future__ import annotations

from sqlalchemy import select

from app.models import Attachment, Tag


def test_index_empty(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "No recipes found" in response.text


def test_create_and_view(client):
    response = client.post(
        "/recipes",
        data={
            "name": "Pancakes",
            "description": "Fluffy",
            "ingredients": "flour\nmilk",
            "instructions": "mix\nfry",
            "tags": "Breakfast, Sweet",
            "source_url": "https://example.com/pancakes",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = client.get(response.headers["location"])
    assert "Pancakes" in detail.text
    assert "Breakfast" in detail.text
    assert "flour" in detail.text
    assert "https://example.com/pancakes" in detail.text


def test_search_and_tag_filter(client, make_recipe):
    make_recipe("Chicken Curry", ingredients="chicken\nrice", tags="Dinner, Chicken")
    make_recipe("Veggie Soup", ingredients="carrot\nstock", tags="Dinner, Vegetarian")

    assert "Chicken Curry" in client.get("/?q=rice").text
    assert "Veggie Soup" not in client.get("/?q=rice").text

    assert "Chicken Curry" in client.get("/?tag=Chicken").text
    assert "Veggie Soup" not in client.get("/?tag=Chicken").text

    # Searching instructions/description works too
    assert "Veggie Soup" in client.get("/?q=carrot").text


def test_edit_and_delete(client, make_recipe):
    recipe_id = make_recipe("Toast")

    response = client.post(
        f"/recipes/{recipe_id}",
        data={"name": "Cheesy Toast", "tags": "Snack"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "Cheesy Toast" in client.get(f"/recipes/{recipe_id}").text

    response = client.post(f"/recipes/{recipe_id}/delete", follow_redirects=False)
    assert response.status_code == 303
    assert f'href="/recipes/{recipe_id}"' not in client.get("/").text


def test_attachment_upload_preview_download_and_delete(client, app, make_recipe):
    recipe_id = make_recipe("With file")

    response = client.post(
        f"/recipes/{recipe_id}/attachments",
        files={"files": ("recipe.txt", b"secret ingredient", "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = client.get(f"/recipes/{recipe_id}")
    assert "secret ingredient" in detail.text

    with app.state.db.session() as session:
        attachment = session.execute(select(Attachment)).scalar_one()
        attachment_id = attachment.id

    download = client.get(f"/attachments/{attachment_id}/download")
    assert download.status_code == 200
    assert download.content == b"secret ingredient"

    client.post(f"/attachments/{attachment_id}/delete", follow_redirects=False)
    with app.state.db.session() as session:
        assert session.execute(select(Attachment)).scalars().all() == []


def test_tag_management(client, make_recipe, app):
    make_recipe("Tagine", tags="Moroccan, Dinner")

    with app.state.db.session() as session:
        tag = session.execute(select(Tag).where(Tag.name == "Moroccan")).scalar_one()

    response = client.post(f"/tags/{tag.id}/rename", data={"name": "North African"}, follow_redirects=False)
    assert response.status_code == 303

    with app.state.db.session() as session:
        assert session.execute(select(Tag).where(Tag.name == "North African")).scalar_one()

    response = client.post(f"/tags/{tag.id}/delete", follow_redirects=False)
    assert response.status_code == 303
