"""Unit tests for extracting a preview image URL from a page."""

from __future__ import annotations

from app.link_preview import find_image_url


def test_finds_og_image():
    html = '<html><head><meta property="og:image" content="https://cdn.example.com/food.jpg"></head></html>'
    assert find_image_url(html, "https://example.com/recipe") == "https://cdn.example.com/food.jpg"


def test_resolves_relative_twitter_image():
    html = '<meta name="twitter:image" content="/img/food.png">'
    assert (
        find_image_url(html, "https://example.com/recipe/steps")
        == "https://example.com/img/food.png"
    )


def test_falls_back_to_first_img():
    html = '<html><body><img src="pics/one.jpg"><img src="pics/two.jpg"></body></html>'
    assert find_image_url(html, "https://example.com/a/b") == "https://example.com/a/pics/one.jpg"


def test_og_image_wins_over_img():
    html = (
        '<meta property="og:image" content="https://cdn.example.com/hero.jpg">'
        '<img src="https://example.com/other.jpg">'
    )
    assert find_image_url(html, "https://example.com") == "https://cdn.example.com/hero.jpg"


def test_returns_none_without_image():
    assert find_image_url("<html><body>no pictures</body></html>", "https://example.com") is None


def test_ignores_non_http_schemes():
    html = '<meta property="og:image" content="data:image/png;base64,AAAA">'
    assert find_image_url(html, "https://example.com") is None
