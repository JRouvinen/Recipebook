"""Import a recipe from a web page using its schema.org JSON-LD metadata.

Most recipe sites embed a ``<script type="application/ld+json">`` block describing
the recipe with schema.org fields. This module downloads a page and turns the
first ``Recipe`` object it finds into an :class:`ImportedRecipe`. If no JSON-LD
recipe is present it falls back to the page title / Open Graph metadata so the
link is still captured.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from .link_preview import MAX_PAGE_BYTES, new_client


@dataclass
class ImportedRecipe:
    name: str
    source_url: str = ""
    description: str = ""
    ingredients: str = ""
    instructions: str = ""
    image_url: str | None = None
    tags: list[str] = field(default_factory=list)


class _PageParser(HTMLParser):
    """Collect JSON-LD blocks, the <title> and selected Open Graph meta tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_json_ld = False
        self._in_title = False
        self._buffer: list[str] = []
        self._title: list[str] = []
        self.json_ld_blocks: list[str] = []
        self.meta: dict[str, str] = {}

    @property
    def title(self) -> str:
        return "".join(self._title).strip()

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        if tag == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self._in_json_ld = True
            self._buffer = []
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            prop = (attributes.get("property") or attributes.get("name") or "").lower()
            content = attributes.get("content", "").strip()
            if prop and content and prop not in self.meta:
                self.meta[prop] = content

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_json_ld:
            self._in_json_ld = False
            self.json_ld_blocks.append("".join(self._buffer))
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._buffer.append(data)
        elif self._in_title:
            self._title.append(data)


def _iter_objects(data):
    if isinstance(data, list):
        for item in data:
            yield from _iter_objects(item)
    elif isinstance(data, dict):
        yield data
        for value in data.values():
            if isinstance(value, (dict, list)):
                yield from _iter_objects(value)


def _is_recipe(obj: dict) -> bool:
    types = obj.get("@type")
    types = types if isinstance(types, list) else [types]
    if any(isinstance(t, str) and t.lower() == "recipe" for t in types):
        return True
    # Some sites nest recipe fields inside a non-Recipe object (e.g. WebPage.mainEntity).
    return "recipeIngredient" in obj or "recipeInstructions" in obj


def _text(value) -> str:
    if isinstance(value, str):
        # JSON-LD inside a <script> is raw text, so HTML entities are not decoded for us.
        return unescape(value.strip())
    if isinstance(value, dict):
        for key in ("name", "@value", "text"):
            if value.get(key):
                return _text(value[key])
    return ""


def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _join_text(value) -> str:
    return "\n".join(text for text in (_text(item) for item in _as_list(value)) if text)


def _flatten_instructions(value) -> list[str]:
    steps: list[str] = []

    def walk(node) -> None:
        if isinstance(node, str):
            text = node.strip()
            if text:
                steps.append(text)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            if node.get("itemListElement"):
                walk(node["itemListElement"])
            elif node.get("text"):
                walk(node["text"])
            elif node.get("name"):
                walk(node["name"])

    walk(value)
    return steps


def _first_image(value, base_url: str) -> str | None:
    for candidate in _as_list(value):
        if isinstance(candidate, str):
            return urljoin(base_url, candidate)
        if isinstance(candidate, dict):
            url = candidate.get("url") or candidate.get("contentUrl")
            if url:
                return urljoin(base_url, str(url))
    return None


def _collect_tags(obj: dict) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for key in ("recipeCategory", "recipeCuisine", "keywords"):
        for item in _as_list(obj.get(key)):
            for piece in _text(item).split(","):
                piece = piece.strip()
                if piece and piece.lower() not in seen:
                    seen.add(piece.lower())
                    names.append(piece)
    return names


def _recipe_from_json_ld(obj: dict, base_url: str) -> ImportedRecipe:
    return ImportedRecipe(
        name=_text(obj.get("name") or obj.get("headline")) or "Imported recipe",
        source_url=_text(obj.get("url")) or base_url,
        description=_text(obj.get("description")),
        ingredients=_join_text(obj.get("recipeIngredient")),
        instructions="\n".join(_flatten_instructions(obj.get("recipeInstructions"))),
        image_url=_first_image(obj.get("image") or obj.get("thumbnailUrl"), base_url),
        tags=_collect_tags(obj),
    )


def fetch_html(url: str) -> tuple[str | None, str | None, str | None]:
    """Download a page.

    Returns ``(html, final_url, error_key)``. On success ``error_key`` is ``None``;
    otherwise it is a translation key under ``import.error.*``.
    """
    if urlparse(url).scheme not in {"http", "https"}:
        return None, None, "import.error.invalid_url"

    try:
        with new_client() as client:
            response = client.get(url)
    except httpx.TimeoutException:
        return None, None, "import.error.timeout"
    except httpx.HTTPError:
        return None, None, "import.error.unreachable"
    except ValueError:
        return None, None, "import.error.invalid_url"

    if response.status_code == 403:
        return None, None, "import.error.blocked"
    if response.status_code == 404:
        return None, None, "import.error.not_found"
    if response.status_code >= 400:
        return None, None, "import.error.http"
    if len(response.content) > MAX_PAGE_BYTES:
        return None, None, "import.error.too_large"

    return response.text, str(response.url), None


def extract_recipe(html: str, base_url: str) -> ImportedRecipe | None:
    """Parse a recipe out of an HTML document, or ``None`` if nothing usable is found."""
    parser = _PageParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - malformed HTML must not crash the request
        return None

    for block in parser.json_ld_blocks:
        try:
            data = json.loads(block.strip())
        except (json.JSONDecodeError, TypeError):
            continue
        for obj in _iter_objects(data):
            if isinstance(obj, dict) and _is_recipe(obj):
                return _recipe_from_json_ld(obj, base_url)

    # Fallback: capture the link using the page title / Open Graph metadata.
    title = parser.title or parser.meta.get("og:title", "").strip()
    if not title:
        return None
    image = parser.meta.get("og:image") or parser.meta.get("og:image:url")
    return ImportedRecipe(
        name=title,
        source_url=base_url,
        description=parser.meta.get("og:description", "") or parser.meta.get("description", ""),
        image_url=urljoin(base_url, image) if image else None,
    )
