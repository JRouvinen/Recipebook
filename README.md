# 🍲 Recipebook

A small, self-hosted recipe manager. Recipes live in a local SQLite database, can carry a
source link plus multiple images/text files, are organised with tags, can be searched and
filtered, and can be scheduled into a weekly or monthly rotating calendar (one recipe per
day, fixed or random rotation).

The whole thing is Docker-deployable and uses no external services — perfect for a homelab.

## Features

- **Recipes** — name, description, source link, ingredients, instructions.
- **Multiple attachments** — images (shown inline), text files (previewed), anything else (download).
- **Tags** — create them inline (with quick-add chips for existing tags), then filter recipes by one or more tags.
- **Search** — across name, description, ingredients and instructions; combine with tag filters and sorting.
- **Rotation calendar** — fixed or random, weekly or monthly; one recipe every day, every other day or weekly; wraps/repeats; mark days *cooked* / *skipped* / reset, or swap in another recipe.
- **Import image from link** — fetch a preview image from a recipe's source link (or add one later from the recipe page).
- **Import recipe from a URL** — paste a recipe link and Recipebook fills in the name, ingredients, instructions, tags and image from the page's schema.org data.
- **Export / import** — a portable `.zip` archive (database **and** media) for full backups, a plain `.sqlite` export, and a readable `.json` export; restore from an archive or a database file.
- **Mobile-friendly** UI (responsive, server-rendered, HTMX for smooth filtering).
- **No auth in v1**, but every request flows through an auth hook so it can be added later.

## Stack

| Layer    | Choice                                   |
| -------- | ---------------------------------------- |
| Backend  | FastAPI + Uvicorn                        |
| Database | SQLite via SQLAlchemy 2.0                |
| UI       | Jinja2 templates + HTMX + hand-written CSS |
| Deploy   | Docker + docker-compose, persistent volume |

## Quick start (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# run the dev server (auto-reload) on http://localhost:8000
python main.py
# or: uvicorn app.main:app --reload
```

Optional sample data:

```bash
python seed.py
```

## Quick start (Docker)

```bash
docker compose up -d --build
# → http://localhost:8000
```

The database and uploaded media are stored in the `recipebook-data` volume
(mounted at `/data` inside the container), so they survive rebuilds.

## Configuration

Configuration is via environment variables (see `.env.example`):

| Variable                    | Default                          | Purpose                              |
| --------------------------- | -------------------------------- | ------------------------------------ |
| `RECIPEBOOK_DATA_DIR`       | `./data`                         | Directory for the DB and media       |
| `RECIPEBOOK_DATABASE_URL`   | `sqlite:///<data>/recipebook.db` | Full SQLAlchemy database URL         |
| `RECIPEBOOK_MEDIA_DIR`      | `<data>/media`                   | Where uploaded attachments are stored |
| `RECIPEBOOK_SECRET_KEY`     | `dev-secret-change-me`           | Session signing key — change in prod |

## Project layout

```
app/
  factory.py            # create_app() — wires settings, DB, middleware, routers
  main.py               # ASGI app object (uvicorn app.main:app)
  config.py             # Settings from env vars
  database.py           # engine / session factory
  models.py             # Recipe, Tag, Attachment, RotationPlan, RotationItem, CalendarEntry
  calendar_service.py   # deterministic fixed rotation + random scheduling
  storage.py            # attachment files on disk
  auth.py               # no-op auth hook (future users)
  deps.py / templating.py / utils.py
  routers/              # recipes, tags, attachments, calendar, data
  templates/            # Jinja2 templates
  static/               # CSS + vendored HTMX
tests/                  # pytest suite
seed.py                 # sample data
Backlog.md              # project plan
Requirements.md         # original requirements
Change_log.md           # changelog
```

## Development

```bash
.venv/bin/python -m pytest
```

The tests use FastAPI's `TestClient` against a throwaway SQLite database, covering recipe
CRUD/search, attachments, tags, the rotation calendar and database export/import.

## Notes & limitations (v1)

- Single user, no login. Keep it on your LAN or behind your own reverse proxy/auth.
- Attachments are stored as-is on disk; no image resizing/thumbnails yet.
- Backups: use the **full archive (.zip)** to move or restore the database *and* media; the
  plain `.sqlite` export is database-only and the `.json` export is for reading/interop.
- SQLite in WAL mode; fine for a household, not for high write concurrency.
