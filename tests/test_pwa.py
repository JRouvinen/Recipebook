"""PWA endpoints: service worker, manifest and offline page."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.factory import create_app
from app.security import hash_password


def test_service_worker_is_served(client):
    response = client.get("/sw.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "addEventListener" in response.text
    assert response.headers.get("cache-control") == "no-cache"


def test_manifest_is_served_and_valid(client):
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Recipebook"
    assert data["display"] == "standalone"
    assert data["start_url"] == "/"
    sizes = {icon["sizes"] for icon in data["icons"]}
    assert "192x192" in sizes and "512x512" in sizes


def test_offline_page_is_served(client):
    response = client.get("/offline")
    assert response.status_code == 200
    assert "offline" in response.text.lower()


def test_pages_link_manifest_and_register_service_worker(client):
    page = client.get("/").text
    assert 'rel="manifest"' in page
    assert "/manifest.webmanifest" in page
    assert "serviceWorker" in page
    assert "/sw.js" in page


def test_icons_are_served(client):
    for path in ("/static/icons/icon-192.png", "/static/icons/icon-512.png"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"


def test_pwa_assets_are_public_when_auth_enabled(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{tmp_path / 'data' / 'pwa.db'}",
        secret_key="test",
        auth_enabled=True,
        auth_username="alice",
        auth_password_hash=hash_password("s3cret", iterations=1000),
    )
    app = create_app(settings)
    with TestClient(app) as client:
        for path in ("/sw.js", "/manifest.webmanifest", "/offline", "/static/css/app.css"):
            assert client.get(path, follow_redirects=False).status_code == 200
        # normal pages still require login
        assert client.get("/", follow_redirects=False).status_code == 303
