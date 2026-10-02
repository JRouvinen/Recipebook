"""Database export / import."""

from __future__ import annotations


def test_export_is_sqlite(client, make_recipe):
    make_recipe("Roundtrip")
    response = client.get("/data/export")
    assert response.status_code == 200
    assert response.content.startswith(b"SQLite format 3\x00")


def test_import_roundtrip(client, make_recipe):
    make_recipe("Roundtrip")
    exported = client.get("/data/export").content

    response = client.post(
        "/data/import",
        files={"file": ("backup.sqlite", exported, "application/x-sqlite3")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "Roundtrip" in client.get("/").text


def test_import_rejects_non_sqlite(client):
    response = client.post(
        "/data/import",
        files={"file": ("garbage.sqlite", b"this is not a database", "application/octet-stream")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    # still able to render the data page
    assert client.get("/data").status_code == 200
