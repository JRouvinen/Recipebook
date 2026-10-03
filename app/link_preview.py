"""Fetch a representative image for a recipe from its source link.

Given a recipe URL, this downloads the page and looks for a preview image, in
priority order:

1. ``og:image`` / ``og:image:url`` / ``og:image:secure_url``
2. ``twitter:image`` / ``twitter:image:src``
3. the first ``<img>`` on the page

The image URL is resolved relative to the page and then downloaded. If the link
itself points directly at an image, that image is used. All network access is
best-effort: on any error or oversized response, ``None`` is returned.
"""

from __future__ import annotations

import mimetypes
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

USER_AGENT = "Recipebook/1.0 (+https://github.com/JRouvinen/Recipebook)"
MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
TIMEOUT = 15.0


class _ImageMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.og_image: str | None = None
        self.twitter_image: str | None = None
        self.first_img: str | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if tag == "meta":
            prop = (attributes.get("property") or attributes.get("name") or "").lower()
            content = attributes.get("content", "").strip()
            if not content:
                return
            if prop in {"og:image", "og:image:url", "og:image:secure_url"} and not self.og_image:
                self.og_image = content
            elif prop in {"twitter:image", "twitter:image:src"} and not self.twitter_image:
                self.twitter_image = content
        elif tag == "img" and not self.first_img:
            src = attributes.get("src", "").strip()
            if src:
                self.first_img = src


def _is_http(url: str) -> bool:
    return urlparse(url).scheme in {"http", "https"}


def find_image_url(html: str, base_url: str) -> str | None:
    """Return the best absolute image URL found in an HTML document."""
    parser = _ImageMetaParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - malformed HTML should never crash a request
        pass
    for candidate in (parser.og_image, parser.twitter_image, parser.first_img):
        if candidate:
            absolute = urljoin(base_url, candidate)
            if _is_http(absolute):
                return absolute
    return None


def _filename_for(image_url: str, content_type: str) -> str:
    name = urlparse(image_url).path.rsplit("/", 1)[-1] or "image"
    if "." not in name:
        extension = mimetypes.guess_extension((content_type or "").split(";")[0].strip())
        name += extension or ".jpg"
    return name


def fetch_recipe_image(url: str) -> tuple[str, bytes, str] | None:
    """Return ``(filename, data, content_type)`` for an image found at ``url``."""
    if not _is_http(url):
        return None

    try:
        with httpx.Client(
            follow_redirects=True, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";")[0].strip()

            if content_type.startswith("image/"):
                data = response.content
                image_url = str(response.url)
                image_type = content_type
            else:
                if len(response.content) > MAX_PAGE_BYTES:
                    return None
                image_url = find_image_url(response.text, str(response.url))
                if not image_url:
                    return None
                image_response = client.get(image_url)
                image_response.raise_for_status()
                data = image_response.content
                image_type = (
                    image_response.headers.get("content-type", "").split(";")[0].strip()
                    or "image/jpeg"
                )
    except (httpx.HTTPError, ValueError):
        return None

    if not data or len(data) > MAX_IMAGE_BYTES or not image_type.startswith("image/"):
        return None
    return _filename_for(image_url, image_type), data, image_type
