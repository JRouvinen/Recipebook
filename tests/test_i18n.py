"""Localization: catalogs, cookie/config language resolution and switching."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import Settings
from app.factory import create_app
from app.i18n import CATALOG_DIR


def _catalog(language: str) -> dict:
    return json.loads((CATALOG_DIR / f"{language}.json").read_text(encoding="utf-8"))


def test_catalogs_have_matching_keys():
    english = _catalog("en")
    finnish = _catalog("fi")
    assert set(english) == set(finnish), set(english) ^ set(finnish)
    assert all(english.values()) and all(finnish.values())


def test_english_by_default(client):
    page = client.get("/").text
    assert "Recipes" in page
    assert "Reseptit" not in page


def test_finnish_via_cookie(client):
    client.cookies.set("recipebook-lang", "fi")
    page = client.get("/").text
    assert "Reseptit" in page
    assert ">Recipes<" not in page


def test_language_switch_route_sets_cookie(client):
    response = client.get("/language/fi?next=/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "recipebook-lang=fi" in response.headers.get("set-cookie", "")


def test_language_switch_rejects_external_redirect(client):
    response = client.get("/language/fi?next=//evil.example.com", follow_redirects=False)
    assert response.headers["location"] == "/"


def test_unsupported_language_falls_back_to_english(client):
    client.cookies.set("recipebook-lang", "xx")
    assert "Recipes" in client.get("/").text


def test_config_default_language(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{tmp_path / 'data' / 'lang.db'}",
        secret_key="test",
        language="fi",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        assert "Reseptit" in client.get("/").text


def test_flash_message_is_translated(client):
    client.cookies.set("recipebook-lang", "fi")
    response = client.post("/recipes", data={"name": "Testi"}, follow_redirects=True)
    assert "Resepti" in response.text
    assert "luotu" in response.text


def test_language_links_present(client):
    page = client.get("/").text
    assert "/language/fi?next=" in page
    assert "/language/en?next=" in page
