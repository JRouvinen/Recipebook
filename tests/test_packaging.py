"""Packaging guard rails.

The Docker build copies ``app/`` into the image; ``.dockerignore`` must not exclude
template directories. A bare ``data`` pattern once matched ``app/templates/data/`` at any
depth, so the built image was missing the Data page template.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _patterns() -> list[str]:
    lines = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def test_dockerignore_has_no_bare_data_pattern():
    patterns = _patterns()
    assert "data" not in patterns
    assert "/data" in patterns


def test_all_template_directories_exist_in_repo():
    template_dirs = {path.name for path in (ROOT / "app" / "templates").iterdir() if path.is_dir()}
    # These directories are referenced by name and must never be ignored.
    assert {"data", "recipes", "calendar", "tags", "auth", "errors"} <= template_dirs
