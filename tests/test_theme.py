"""Light/dark theme: palette, toggle and scripts."""

from __future__ import annotations


def test_css_defines_dark_theme(client):
    css = client.get("/static/css/app.css").text
    assert '[data-theme="dark"]' in css
    assert "color-scheme: dark" in css
    assert "--bg:" in css


def test_theme_toggle_and_scripts_present(client):
    page = client.get("/").text
    assert 'id="theme-toggle"' in page
    assert "recipebook-theme" in page  # inline no-flash script key
    assert "/static/js/theme.js" in page


def test_theme_js_is_served(client):
    response = client.get("/static/js/theme.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert "data-theme" in response.text
