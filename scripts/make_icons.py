"""Generate the PWA icons (a simple bowl-and-steam mark) with Pillow.

Run from the project root::

    .venv/bin/python scripts/make_icons.py

Outputs ``app/static/icons/icon-192.png``, ``icon-512.png`` and
``apple-touch-icon.png``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "icons"

BACKGROUND = (63, 125, 58, 255)  # --accent
FOREGROUND = (255, 255, 255, 255)


def make_icon(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = size * 0.06
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=size * 0.2,
        fill=BACKGROUND,
    )

    centre_x = size / 2
    radius = size * 0.26
    centre_y = size * 0.60

    # Bowl (lower half of a circle) plus a rim.
    draw.pieslice(
        [centre_x - radius, centre_y - radius, centre_x + radius, centre_y + radius],
        start=0,
        end=180,
        fill=FOREGROUND,
    )
    draw.rectangle(
        [centre_x - radius, centre_y - size * 0.02, centre_x + radius, centre_y + size * 0.02],
        fill=FOREGROUND,
    )

    # Steam lines.
    width = max(2, int(size * 0.02))
    for offset in (-0.12, 0.0, 0.12):
        x = centre_x + size * offset
        draw.line([x, size * 0.30, x, size * 0.43], fill=FOREGROUND, width=width)

    return image


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        make_icon(size).save(OUTPUT_DIR / f"icon-{size}.png")
    make_icon(180).save(OUTPUT_DIR / "apple-touch-icon.png")
    print(f"Wrote icons to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
