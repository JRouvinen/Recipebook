"""Optional authentication: hashing, login/logout and route protection."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.factory import create_app
from app.security import hash_password, verify_password


@pytest.fixture()
def auth_client(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{tmp_path / 'data' / 'auth.db'}",
        secret_key="test-secret",
        auth_enabled=True,
        auth_username="alice",
        auth_password_hash=hash_password("s3cret", iterations=1000),
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


def test_hash_and_verify():
    stored = hash_password("hunter2", iterations=1000)
    assert stored.startswith("pbkdf2_sha256$1000$")
    assert verify_password("hunter2", stored)
    assert not verify_password("wrong", stored)
    assert not verify_password("hunter2", None)
    assert not verify_password("hunter2", "not-a-valid-hash")


def test_protected_page_redirects_to_login(auth_client):
    response = auth_client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_static_assets_are_public(auth_client):
    assert auth_client.get("/static/css/app.css").status_code == 200


def test_login_flow(auth_client):
    assert auth_client.get("/login").status_code == 200

    bad = auth_client.post(
        "/login",
        data={"username": "alice", "password": "nope", "next": "/"},
        follow_redirects=False,
    )
    assert bad.status_code == 401

    ok = auth_client.post(
        "/login",
        data={"username": "alice", "password": "s3cret", "next": "/"},
        follow_redirects=False,
    )
    assert ok.status_code == 303
    assert ok.headers["location"] == "/"
    assert "Recipes" in auth_client.get("/").text
    assert auth_client.get("/data").status_code == 200

    out = auth_client.post("/logout", follow_redirects=False)
    assert out.status_code == 303
    assert auth_client.get("/", follow_redirects=False).status_code == 303


def test_login_redirects_back_to_requested_page(auth_client):
    response = auth_client.get("/calendar", follow_redirects=False)
    location = response.headers["location"]
    assert location.startswith("/login?next=")
    assert "%2Fcalendar" in location

    ok = auth_client.post(
        "/login",
        data={"username": "alice", "password": "s3cret", "next": "/calendar"},
        follow_redirects=False,
    )
    assert ok.headers["location"] == "/calendar"


def test_login_rejects_external_redirect(auth_client):
    ok = auth_client.post(
        "/login",
        data={"username": "alice", "password": "s3cret", "next": "//evil.example.com"},
        follow_redirects=False,
    )
    assert ok.headers["location"] == "/"


def test_auth_disabled_by_default(client):
    assert client.get("/", follow_redirects=False).status_code == 200
    # hits the login route, which immediately redirects home when auth is off
    assert client.get("/login", follow_redirects=False).status_code == 303


def test_plaintext_password_is_hashed_on_settings(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        database_url=f"sqlite:///{tmp_path / 'data' / 'x.db'}",
        auth_enabled=True,
        auth_username="bob",
        auth_password="plaintext",
    )
    assert settings.auth_password_hash is not None
    assert settings.auth_password_hash.startswith("pbkdf2_sha256$")
    assert verify_password("plaintext", settings.auth_password_hash)
