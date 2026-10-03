# Change log

All notable changes to Recipebook are documented in this file.
The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to semantic versioning.

## [Unreleased]

### Documentation
- README: added an "HTTPS (via Caddy)" section with a ready-to-use `deploy/Caddyfile` and
  `docker-compose.caddy.yml` overlay (for PWA/offline over the LAN), plus how to trust
  Caddy's internal CA.

## [1.4.0] — 2026-10-03

### Added
- **Structured ingredients + unit parsing:** ingredient lines are parsed into quantity, unit,
  name and note (decimals, fractions, mixed numbers, unicode fractions, ranges, and a broad
  set of units including Finnish ones). The shopping list now **combines quantities** for
  matching ingredients (two recipes using "2 tomatoes" each become one "4 tomatoes" line)
  instead of only counting occurrences.
- **PWA / offline support:** a web app manifest and icons make Recipebook installable as a
  standalone app, and a service worker caches the app shell and previously viewed pages so it
  keeps working offline (with an offline fallback page). The runtime cache is cleared on logout.

## [1.3.0] — 2026-10-03

### Added
- **Multiple meals per day:** calendar plans can schedule separate recipes for breakfast,
  lunch, dinner and snack slots, each tracked (cooked / skipped / swap) independently. Plans
  without meals behave as before, and existing databases are migrated automatically (the
  `calendar_entries` table is rebuilt to allow one entry per meal, preserving existing rows).
- **Image thumbnails:** uploaded and imported images get a downscaled JPEG thumbnail that the
  recipe cards and galleries use, cutting page weight. Existing images are backfilled lazily
  on first view. Adds Pillow as a dependency (optional at runtime - falls back to the original
  image if unavailable).

## [1.2.0] — 2026-10-03

### Added
- **Import recipe from a URL:** paste a recipe link and Recipebook reads the page's
  schema.org JSON-LD (name, ingredients, instructions, tags, image) and creates the recipe.
  Falls back to the page title / Open Graph metadata when no JSON-LD recipe is present.
- **Portable archive export/import:** a `.zip` containing the SQLite database, every media
  file and a manifest — for complete backups and moving between machines. Import validates
  the archive, backs up the current database and media, then restores.
- **JSON export:** a readable export of all recipes, their tags and attachment metadata.
- **Optional login:** disabled by default; enable with `RECIPEBOOK_AUTH_ENABLED=true` and a
  username/password (PBKDF2-hashed, standard library only). When on, all pages except the
  login screen and static assets require a session.
- **Shopping list:** generate a merged, de-duplicated ingredient list from the recipes
  planned in the calendar over any date range, with per-item "used by N recipes" counts and
  tick-off state remembered in the browser.

### Fixed
- **Recipe import from bot-protected sites:** pages behind Cloudflare bot protection (e.g.
  `k-ruoka.fi`) returned 403 to plain requests. Fetches now send a realistic browser header
  set, so the public page is served; error messages also describe the real problem (blocked /
  not found / timeout / too large) instead of a generic failure.
- **Nested JSON-LD recipes:** the parser now searches JSON-LD recursively, so recipes nested
  inside another object (e.g. `WebPage.mainEntity`, as on `k-ruoka.fi`) are found.

### Documentation
- README: added a "Data persistence & updating" section explaining that the database and
  media live in the `recipebook-data` volume (kept across container updates) and how to back
  them up, including the `docker compose down -v` caveat.

## [1.1.0] — 2026-10-03

### Added
- **Quick-add tags:** the recipe form now shows existing tags as clickable chips that
  append to the tag field, alongside free-text entry.
- **"Add another recipe"** shortcut shown after saving a new recipe.
- **Calendar recipe spacing:** plans can place a recipe every day, every other day, every
  3/4 days or weekly, leaving gap days empty.
- **Import food image from the recipe link:** fetch the page at the recipe's source link
  and attach the best preview image (`og:image`, `twitter:image` or the first `<img>`),
  via a checkbox when saving or a button on the recipe page.

### Fixed
- Flash messages queued while another flash was already pending were silently dropped
  (Starlette's session only persists explicit assignments).
- Calendar plans showed a recipe on days *before* the plan's start date (they were clamped
  to day 0), which made an "every other day" plan look like it ran every day when the start
  date fell mid-week. Pre-start days are now left empty, and any stale entries are cleaned
  up automatically on the next calendar view.

## [1.0.0] — 2026-10-02

Initial release: a self-hosted, Docker-deployable recipe book.

### Added
- **Project scaffolding:** application factory, environment-based settings, SQLite
  engine/session with foreign-key and WAL pragmas, git repository, `.gitignore`,
  `.dockerignore`, `requirements.txt` / `requirements-dev.txt`.
- **Recipes:** create, view, edit and delete recipes with name, description, source
  link, ingredients and instructions.
- **Attachments:** upload multiple files per recipe (images, text files and other
  documents), stored on disk with metadata in the database; inline image gallery, text
  previews, downloads and deletion.
- **Tags:** many-to-many tags created inline from the recipe form, a tag management page
  (rename/delete) and multi-tag filtering.
- **Search & filtering:** free-text search across name, description, ingredients and
  instructions, combined with tag filters and name/newest/oldest sorting, delivered with
  HTMX for live updates.
- **Rotation calendar:** fixed-ordered or random plans, weekly or monthly cycles, one
  recipe per day with wrap/repeat, week and month views, marking entries as
  cooked/skipped/planned and swapping in a different recipe. Activate/deactivate plans.
- **Export / import:** download the entire database as a `.sqlite` file and restore it by
  upload, with validation and automatic backup of the previous database.
- **UI:** responsive server-rendered Jinja2 templates, hand-written CSS and a vendored copy
  of HTMX (works fully offline), plus friendly 404 page.
- **Auth hook:** `app/auth.py` resolves a single local user for now, so real
  authentication can be added later in one place.
- **Quality:** pytest suite covering recipe CRUD/search, attachments, tags, calendar
  scheduling and database export/import; a `seed.py` sample-data script.
- **Deployment:** `Dockerfile`, `docker-compose.yml` with a persistent `recipebook-data`
  volume, healthcheck and `README.md`.
