# 🍲 Recipebook

A small, self-hosted recipe manager. Recipes live in a local SQLite database, can carry a
source link plus multiple images/text files, are organised with tags, can be searched and
filtered, and can be scheduled into a weekly or monthly rotating calendar (one recipe per
day, fixed or random rotation).

The whole thing is Docker-deployable and uses no external services — perfect for a homelab.

## Features

- **Recipes** — name, description, source link, ingredients, instructions.
- **Multiple attachments** — images (with optimised thumbnails in cards and galleries), text files (previewed), anything else (download).
- **Tags** — create them inline (with quick-add chips for existing tags), then filter recipes by one or more tags.
- **Search** — across name, description, ingredients and instructions; combine with tag filters and sorting.
- **Rotation calendar** — fixed or random, weekly or monthly; one recipe or several meals per day (breakfast/lunch/dinner/snack); a recipe every day, every other day or weekly; wraps/repeats; mark each meal *cooked* / *skipped* / reset, or swap in another recipe.
- **Shopping list** — generate a merged ingredient list from the recipes planned over any date range, combining quantities for matching items (e.g. "2 tomatoes" + "2 tomatoes" → "4 tomatoes").
- **Import image from link** — fetch a preview image from a recipe's source link (or add one later from the recipe page).
- **Import recipe from a URL** — paste a recipe link and Recipebook fills in the name, ingredients, instructions, tags and image from the page's schema.org data.
- **Export / import** — a portable `.zip` archive (database **and** media) for full backups, a plain `.sqlite` export, and a readable `.json` export; restore from an archive or a database file.
- **Mobile-friendly** UI (responsive, server-rendered, HTMX for smooth filtering).
- **Installable / offline** — a web app manifest + service worker let you install it as an app and keep using previously viewed pages offline.
- **Optional login** — off by default; turn it on with a username and password (PBKDF2-hashed, no extra dependencies) to protect the whole app.

## Stack

| Layer    | Choice                                   |
| -------- | ---------------------------------------- |
| Backend  | FastAPI + Uvicorn                        |
| Database | SQLite via SQLAlchemy 2.0                |
| UI       | Jinja2 templates + HTMX + hand-written CSS |
| Images   | Pillow (thumbnail generation)            |
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

## Data persistence & updating

The database and all uploaded media live in the Docker volume `recipebook-data` (mounted at
`/data`), **not** inside the container image. Updating the app therefore keeps your data:

| Action | Data |
| --- | --- |
| `docker compose up -d --build` (rebuild after code changes) | **kept** |
| `docker compose pull && docker compose up -d` | **kept** |
| `docker compose restart` | **kept** |
| `docker compose down` (container removed, volume kept) | **kept** |
| `docker compose down -v` / `docker volume rm recipebook-data` | **deleted** |
| `docker system prune --volumes` (when the volume is unused) | **possibly deleted** |

Rebuilding only replaces the application code; the `recipebook-data` volume is re-attached to
the new container. On startup the app applies small additive schema migrations, so an existing
database keeps working after an update.

> ⚠️ Avoid `docker compose down -v` unless you intend to wipe everything.

The volume lives on the host at `/var/lib/docker/volumes/recipebook-data/_data`, but prefer
the app's own export instead of editing it directly.

### Backups before updating

Use **Data → Export → Full archive (.zip)** in the app (database + media), or copy the whole
volume:

```bash
docker run --rm -v recipebook-data:/data -v "$PWD":/backup alpine \
  tar czf /backup/recipebook-backup.tgz -C /data .
```

## Configuration

Configuration is via environment variables (see `.env.example`):

| Variable                    | Default                          | Purpose                              |
| --------------------------- | -------------------------------- | ------------------------------------ |
| `RECIPEBOOK_DATA_DIR`       | `./data`                         | Directory for the DB and media       |
| `RECIPEBOOK_DATABASE_URL`   | `sqlite:///<data>/recipebook.db` | Full SQLAlchemy database URL         |
| `RECIPEBOOK_MEDIA_DIR`      | `<data>/media`                   | Where uploaded attachments are stored |
| `RECIPEBOOK_SECRET_KEY`     | `dev-secret-change-me`           | Session signing key — change in prod |
| `RECIPEBOOK_AUTH_ENABLED`   | `false`                          | Require login for the whole app      |
| `RECIPEBOOK_AUTH_USERNAME`  | `admin`                          | Login username                       |
| `RECIPEBOOK_AUTH_PASSWORD_HASH` | –                           | PBKDF2 hash (see below)              |
| `RECIPEBOOK_AUTH_PASSWORD`  | –                                | Plaintext password, hashed at startup (less safe) |

### Optional authentication

Disabled by default. To protect the app, generate a password hash and enable auth:

```bash
.venv/bin/python hash_password.py            # prints pbkdf2_sha256$...
export RECIPEBOOK_AUTH_ENABLED=true
export RECIPEBOOK_AUTH_USERNAME=jane
export RECIPEBOOK_AUTH_PASSWORD_HASH='pbkdf2_sha256$260000$...'
```

Alternatively set `RECIPEBOOK_AUTH_PASSWORD` and it is hashed in memory at startup. With auth
enabled, every request except the login page and static assets requires a session and is
otherwise redirected to `/login` (returning you to the page you asked for afterwards).

## Install as an app (PWA)

Recipebook ships a web app manifest, icons and a service worker. Open it in a supported
browser and use **Install** / **Add to Home Screen** to run it standalone. The service worker
caches the app shell and previously viewed pages, so the app keeps working offline (an offline
page is shown for anything not cached). Logging out clears the cached pages.

## Project layout

```
app/
  factory.py            # create_app() — wires settings, DB, middleware, routers
  main.py               # ASGI app object (uvicorn app.main:app)
  config.py             # Settings from env vars (data dir, auth, secret key)
  database.py           # engine / session factory + additive migrations
  models.py             # Recipe, Tag, Attachment, RotationPlan, RotationItem, CalendarEntry
  calendar_service.py   # fixed/random scheduling with configurable spacing
  shopping.py           # merge planned recipes into a shopping list
  ingredients.py        # parse free-text ingredient lines into quantity/unit/name
  storage.py            # attachment files on disk
  link_preview.py       # find + fetch a page's preview image
  recipe_import.py      # parse schema.org JSON-LD from a recipe URL
  archive.py            # portable .zip backup (database + media)
  security.py           # PBKDF2 password hashing
  middleware.py         # optional login gate
  auth.py               # current-user resolution
  deps.py / templating.py / utils.py
  routers/              # auth, pwa, recipes, tags, attachments, calendar, shopping, data
  templates/            # Jinja2 templates
  static/               # CSS + vendored HTMX + small JS helpers
tests/                  # pytest suite
seed.py                 # sample data
hash_password.py        # generate RECIPEBOOK_AUTH_PASSWORD_HASH
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
