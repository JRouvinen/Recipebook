"""Shared pytest fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.factory import create_app


@pytest.fixture()
def settings(tmp_path):
    data_dir = tmp_path / "data"
    return Settings(
        data_dir=data_dir,
        media_dir=data_dir / "media",
        database_url=f"sqlite:///{data_dir / 'test.db'}",
        secret_key="test-secret",
    )


@pytest.fixture()
def app(settings):
    return create_app(settings)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def make_recipe(client):
    """Create a recipe through the HTTP API and return its id."""

    def _make(name: str, **fields) -> int:
        response = client.post(
            "/recipes", data={"name": name, **fields}, follow_redirects=False
        )
        assert response.status_code == 303, response.text
        location = response.headers["location"].split("?")[0]
        return int(location.rstrip("/").rsplit("/", 1)[-1])

    return _make
