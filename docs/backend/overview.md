# OSSS Backend (FastAPI) — Overview

_This page documents the **backend** application located at:_  
`src/OSSS` (commit **e7c3fcf69557527d1c09b9d47096fac63c0af246**).

The backend is built with **FastAPI** and **Python 3.11+**. It exposes REST endpoints with an
OpenAPI schema, integrates with **Keycloak** for authentication (OIDC), and is designed to run in
containers for local and production environments.

---

## Key Features

- **FastAPI** app with typed routers and Pydantic models.
- **OpenAPI** documentation out-of-the-box (`/docs`, `/redoc`).
- **SSO-ready**: hooks for Keycloak / OIDC (token verification and role mapping).
- **Testable**: first-class support for `pytest` and dependency overrides.
- **Container-friendly**: deterministic runtime via Docker/Compose, optional `.env` support.

---

## Project Structure (typical)

> Your exact module names may differ; this reflects a common layout for `src/OSSS`.

```
src/OSSS/
├── __init__.py
├── __main__.py             # CLI entry (menu or helpers) — `python -m OSSS`
├── api/                    # Routers (per feature), dependencies, error handlers
│   ├── routes/             # e.g., behavior codes, admin, health, users
│   ├── deps.py
│   └── errors.py
├── core/                   # App factory, config, logging
│   ├── config.py           # Settings (env-driven)
│   └── security.py         # Auth helpers (JWT/OIDC validation)
├── db/                     # Persistence (SQLAlchemy / async drivers) if used
│   ├── models.py
│   ├── session.py
│   └── migrations/         # Alembic (optional)
├── services/               # Business logic / service layer
├── schemas/                # Pydantic models (request/response/domain)
└── main.py                 # FastAPI app instance (`app = FastAPI(...)`)
```

If your `main.py` lives elsewhere, adjust commands accordingly (see **Run** below).

---

## Running Locally

### 1) Python environment

```bash
# From the repo root
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .\.venv\Scripts\Activate.ps1

# Install backend dependencies (adjust if you use Poetry/UV)
pip install -r requirements.txt  # or: pip install -e ".[dev]"
```

### 2) Environment variables

Create `.env` (or export env vars) with typical settings (examples — tailor to your app):

| Variable | Purpose | Example |
|---|---|---|
| `OSSS_ENV` | runtime profile | `development` |
| `OSSS_LOG_LEVEL` | logging level | `INFO` |
| `DATABASE_URL` | DB connection string | `postgresql+asyncpg://user:pass@localhost:5432/osss` |
| `KEYCLOAK_ISSUER` | OIDC issuer | `https://kc.example.com/realms/OSSS` |
| `KEYCLOAK_AUDIENCE` | API audience/client id | `osss-api` |
| `KEYCLOAK_JWKS_URL` | JWKS endpoint (optional if discoverable) | `https://kc.../protocol/openid-connect/certs` |

> The web frontend (`src/osss-web`) has its own `.env.local` variables; keep secrets server-side.

### 3) Start the API server

Choose one method:

```bash
# (A) If your app exposes `app` in main.py:
uvicorn OSSS.main:app --reload --port 8081

# (B) If your app factory is in OSSS.api (example):
uvicorn OSSS.api.main:app --reload --port 8081

# (C) If you ship a CLI entry and it supports "serve":
python -m OSSS  # see __main__.py (may open menu; pick "serve" if provided)
```

Then open:
- Swagger UI: http://localhost:8081/docs  
- ReDoc: http://localhost:8081/redoc

---

## Authentication & Authorization (Keycloak/OIDC)

- **Incoming requests** present a **Bearer token** (Access Token) issued by Keycloak.
- The API **verifies** token signature and **validates** issuer, audience, expiry, and (optionally) roles.
- Use a dependency (e.g., `get_current_user`) to require auth for protected routes and map roles/groups
  into domain permissions (RBAC/ABAC).

Typical request flow:

```
Client → (Bearer JWT) → OSSS FastAPI → (validate via OIDC/JWKS) → Authorized route
```

> For service-to-service calls, use client credentials with a machine account and a distinct audience.

---

## Development Tips

- **Routers**: Group endpoints by feature (e.g., `api/routes/behavior_codes.py`). Include them in `main.py`.
- **Schemas (Pydantic)**: Keep request/response models small and versionable.
- **Services**: Put business logic in `services/` and call from routers → easier to unit test.
- **Dependencies**: Inject per-request resources (db sessions, current user). Override them in `pytest`.
- **CORS**: If the frontend runs on a different origin, enable CORS for dev (exact origins only).

Example `main.py` skeleton:

```python
from fastapi import FastAPI
from .api.routes import health

app = FastAPI(title="OSSS API", version="0.1.0")
app.include_router(health.router, prefix="/healthz", tags=["health"])
```

---

## Testing

```bash
# Lint & type check (if configured)
ruff check src/OSSS
mypy src/OSSS

# Run unit/integration tests
pytest -q
```

- Prefer **unit tests** for services and dependencies.
- Use **TestClient** (or httpx) for router tests; override deps for auth/db.
- For auth, generate signed test tokens or mock verification step.

---

## OpenAPI & Client SDKs

FastAPI exposes the OpenAPI JSON at `/openapi.json`. You can generate clients:

```bash
# Typescript/axios example via openapi-generator (adjust package)
openapi-generator generate   -i http://localhost:8081/openapi.json   -g typescript-axios   -o client-ts
```

Keep versioning in mind; regenerate clients on breaking changes.

---

## Deployment

- **Container**: Build an image with a non-root user, pinned Python deps, and a healthcheck.
- **Server**: Run with `uvicorn` (or `gunicorn -k uvicorn.workers.UvicornWorker`) behind a reverse proxy.
- **Config**: Inject env vars via secrets manager; never bake secrets into images.
- **Observability**: Structured logs (JSON), request IDs, metrics (Prometheus), tracing (OTel) as needed.

Minimal Dockerfile example (adjust paths):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY src ./src
ENV PYTHONPATH=/app/src
EXPOSE 8081
CMD ["uvicorn", "OSSS.main:app", "--host", "0.0.0.0", "--port", "8081"]
```

---

## Troubleshooting

- **404 /docs**: Check your app entry and router includes; verify `FastAPI()` created.
- **401/403**: Validate Keycloak config (issuer/audience). Check that tokens have the right roles.
- **CORS errors**: Set allowed origins for your dev frontend URL.
- **Import errors**: Run with `PYTHONPATH=src` or install the package in editable mode.

---

## Related Docs

- Frontend overview: `docs/frontend/overview.md`
- Monorepo landing page: `docs/index.md`
- MkDocs + API docs: see `mkdocs.yml`, `docs/api/python/`

---

## Links

- Repo path: https://github.com/rubelw/OSSS/tree/e7c3fcf69557527d1c09b9d47096fac63c0af246/src/OSSS
