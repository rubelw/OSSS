# FastAPI Smoke Tests

These smoke tests are designed for the OSSS FastAPI backend at:
`backend/fastapi-backend/app`

## What these tests do

- **Disable auth** by overriding the `require_realm_roles` dependency.
- **Swap DB** to an in-memory SQLite database by overriding `get_db` and auto-creating tables via `Base.metadata.create_all(...)`.
- **Verify OpenAPI** is served.
- **Ensure routes exist** (especially the CIC endpoints if you registered them).
- **Exercise collection GETs** to ensure they don't 500.
- **Try a tiny CRUD** on `/districts` if the path exists and is not blocked by auth.

> If POST/DELETE are protected by auth, the test accepts `401/403` as a *pass* for the CRUD portion.

## How to run

From the repository root (same folder where `app/` lives):

```bash
python -m pip install -r requirements-test.txt
pytest
```

If your project uses a different imports layout, tweak the imports in `tests/conftest.py` that bring in `app.main:app` and `get_db`.

## Notes

- These tests assume your models are bound to a single `Base` in `app.models.base` (or `app.models.Base`) and that creating all tables on SQLite is okay for smoke purposes.
- If some models are strictly Postgres (e.g., `UUID(as_uuid=True)` or `JSONB`), SQLite will emulate enough to create tables for smoke tests, but you may need to adapt for full integration tests.
