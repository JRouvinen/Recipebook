# Recipebook — Project Backlog

## Vision
A self-hosted, Docker-deployable recipe book with a simple, mobile-friendly web UI.
Recipes live in a local database, can carry a link plus multiple text/image attachments,
are organised with tags, can be searched/filtered, and can be scheduled into a weekly or
monthly rotating calendar (one recipe per day, fixed or random rotation).

## Decided stack
- **Backend:** FastAPI + Uvicorn
- **Database:** SQLite via SQLAlchemy 2.0 (local file, exportable/importable)
- **UI:** Jinja2 server-rendered templates + HTMX + hand-written responsive CSS
- **Deploy:** Docker + docker-compose, persistent volume for the DB and media
- **Auth:** none in v1, but all request handling goes through an auth hook so it can be
  added later without rework.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Milestone v1.0 — Core Recipebook  ✅ *(complete)*

### EPIC 1 — Project & infrastructure
- [x] Initialise git repo, `.gitignore`, `.dockerignore`
- [x] Python venv + `requirements.txt`
- [x] App factory, settings, SQLite engine/session
- [x] Base template, responsive CSS, vendored HTMX
- [x] `Dockerfile` + `docker-compose.yml` + persistent volume
- [x] `README.md` with local run + Docker instructions

### EPIC 2 — Recipes (CRUD)
- [x] Model: `Recipe` (name, description, source_url, ingredients, instructions, timestamps)
- [x] Create recipe
- [x] Recipe detail view
- [x] Edit recipe
- [x] Delete recipe (with confirmation)
- [x] Form validation + user feedback (flash messages)

### EPIC 3 — Attachments (multiple per recipe)
- [x] Model: `Attachment` (original name, stored name, content type, kind, size)
- [x] Upload image / text / other files
- [x] Store files on disk under `data/media`, metadata in DB
- [x] Serve attachments: inline image preview, text preview, download
- [x] Delete attachment

### EPIC 4 — Tags
- [x] Model: `Tag` + `recipe_tag` many-to-many association
- [x] Add/remove tags from the recipe form
- [x] Tag management page (rename, delete)
- [x] Filter recipes by one or more tags

### EPIC 5 — Search & filtering
- [x] Search by recipe name
- [x] Text search across description, ingredients and instructions
- [x] Combine search text + tag filters
- [x] Sort options (name, newest, oldest)

### EPIC 6 — Rotation calendar
- [x] Models: `RotationPlan`, `RotationItem`, `CalendarEntry`
- [x] Create a plan: mode = fixed (ordered) or random; interval = weekly or monthly
- [x] One recipe per day
- [x] Generate schedule for a week/month with wrap/repeat
- [x] Random mode avoids immediate repeats
- [x] Mark an entry as *cooked*
- [x] Mark an entry as *skipped* (optionally reassign another recipe)
- [x] Week + month calendar views
- [x] Activate/deactivate a plan

### EPIC 7 — Export / import
- [x] Export: download the SQLite database file
- [x] Import: upload a `.sqlite` file (validate, back up current, replace)
- [x] Confirmation + safety guards

### EPIC 8 — Quality
- [x] Basic pytest suite (models, rotation logic, HTTP smoke tests)
- [x] Sample-data seed script
- [x] Friendly 404 / 500 pages

---

## Enhancements (v1.1)  ✅ *(complete)*
- [x] Possibility to quick add tags instead of writing them
- [x] After adding a new recipe -> the page could have "Add another recipe" button
- [x] In calendar creation, there could be way to have new recipe every other day instead of every day
- [x] Possibility to import image of the food from recipe link

## Future (post-v1.0)
- [x] Optional user accounts / login behind the existing auth hook
- [x] Portable archive export (DB + media as a zip) and JSON export
- [x] Shopping list generated from planned recipes
- [ ] Structured ingredients + unit parsing
- [x] Import recipe from a URL (schema.org / JSON-LD)
- [ ] Image thumbnails + optimisation
- [ ] Multiple meals/recipes per day (breakfast/lunch/dinner slots)
- [ ] Drag-and-drop ordering of recipes in a fixed plan
- [ ] PWA / offline support
- [ ] "What's for dinner" notifications


