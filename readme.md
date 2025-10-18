# Study Hub
The code here is intentionally lightweight: Flask + SQLite on the server, Jinja2 templates, and a bit of JavaScript for interactivity on the dashboard and game pages.

## Contributors / Roles
- Michael Charlie Pingol — Frontend / UI
- Adrian De Vera — Backend / API
- Francis Ryan Cajucom — Game logic / Bot
- Mark Arcel Flores — Testing / QA
- Mark Angelo Nakamura — DevOps / Packaging
- Prince Jay Pestano — Product / UX

## Quickstart (development)

Requirements
- Python 3.10+
- See `requirements.txt` for Python packages

Install dependencies (recommended in a virtual environment):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Initialize the database: the app will create `study_hub.db` automatically on first run.

Start the development server:

```powershell
python app.py
```

Open http://127.0.0.1:5000 in your browser.

## Running tests

Tests use pytest. To run the test suite:

```powershell
python -m pytest -q
```

Notes:
- The current tests use the repository's database file; I recommend switching tests to an in-memory SQLite DB for isolation.

## Project structure (important files)
- `app.py` — Flask application and API routes (primary backend file)
- `templates/` — Jinja2 templates for pages
- `static/` — CSS and static assets
- `study_hub.db` — SQLite DB file (created at runtime)
- `tests/` — pytest test files

## Cleanup & maintenance
- To clear development data: remove `study_hub.db` or use the admin clear endpoint (if enabled): `POST /admin/clear`.

## Security & production notes
- This is a demo. For production, use a real database, secure secrets via environment variables, enable CSRF protection, and harden authentication.