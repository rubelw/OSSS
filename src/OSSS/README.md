# FastAPI + Keycloak (minimal)

A tiny FastAPI app that validates Keycloak access tokens (via JWKS), exposes an unprotected `/healthz`, plus two protected endpoints:
- `GET /me` — requires a valid bearer token
- `GET /admin` — requires a realm role (defaults to `admin`, configurable)

## 1) Configure environment

```bash
export KEYCLOAK_BASE_URL="http://localhost:8080"   # no trailing /auth
export KEYCLOAK_REALM="myrealm"
export KEYCLOAK_CLIENT_ID="my-fastapi"
export KEYCLOAK_CLIENT_SECRET="your-client-secret-if-confidential"
export CALLBACK_URL="http://localhost:8081/callback"
export REQUIRED_ADMIN_ROLE="admin"  # change if you like# OSSS Backend — FastAPI Core & Keycloak Integration (High‑Level Overview)

The **OSSS backend** under `src/OSSS` is the central FastAPI‑based service powering
Open Source School Software (OSSS).  
It provides API endpoints, authentication, orchestration hooks, and integrates with identity services
such as **Keycloak** for secure authorization.

This module is responsible for:
- exposing REST/JSON APIs for frontend and internal systems
- validating users, roles, and permissions via Keycloak
- serving operational endpoints for automation and orchestration workflows
- providing service‑level logic shared by OSSS components

> This is a **high‑level conceptual overview** for developers exploring the OSSS backend.
> Behavior and module layout may evolve as OSSS grows.

---

## 🧠 What the Backend Does

The OSSS backend provides:
- **Authenticated API access** via Keycloak
- **Role‑based access control (RBAC)** for administrative endpoints
- **OpenAPI schema exposure** for documentation & client generation
- **Health & readiness endpoints** for orchestration / containers
- **Integration points** for agent workflows and orchestration engines

It is not a monolithic app — the backend exposes endpoints and building blocks that other
services (like `a2a_agent`, orchestration, or UI app) rely upon.

---

## 🗂 Directory Purpose

`src/OSSS/` typically contains:
- FastAPI app wiring
- authentication middleware
- settings & environment configuration
- service logic and reusable backend components

The exact module list may vary, but patterns follow:
```
src/OSSS/
├── main.py              # FastAPI app instantiation + routes
├── config/              # settings & configuration
├── auth/                # Keycloak token validation & role logic
├── api/                 # API router entry points
└── utils/               # shared helpers
```

---

## 🔐 FastAPI + Keycloak Integration (minimal example)

The OSSS backend uses Keycloak to validate user access tokens and enforce audience + role checks.

The following minimal example demonstrates how OSSS integrates with Keycloak at runtime:

> <small>(This aligns with how the OSSS backend performs authentication.)</small>

### 1) Configure environment

```bash
export KEYCLOAK_BASE_URL="http://localhost:8080"   # no trailing /auth
export KEYCLOAK_REALM="myrealm"
export KEYCLOAK_CLIENT_ID="my-fastapi"
export KEYCLOAK_CLIENT_SECRET="your-client-secret-if-confidential"
export CALLBACK_URL="http://localhost:8081/callback"
export REQUIRED_ADMIN_ROLE="admin"  # change if you like
```

> For a public client, leave `KEYCLOAK_CLIENT_SECRET` empty and make the client **Public** in Keycloak UI.

### 2) Install & run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scriptsctivate
pip install -r requirements.txt
uvicorn main:app --reload --port 8081
```

Open: http://localhost:8081/docs

Click **Authorize** and log in via Keycloak.  
Try `/me` and `/admin` — the latter requires a realm role controlled by `REQUIRED_ADMIN_ROLE`.

### 3) Handy helpers

| Endpoint | Purpose |
|----------|---------|
| `GET /healthz` | always 200 OK |
| `GET /login-link` | prints authorization URL for quick tests |
| `GET /callback?code=...` | exchanges auth code + redirects with tokens for frontends |

### Notes

- Token verification uses **realm JWKS**
- **Audience** is enforced to `KEYCLOAK_CLIENT_ID`
- Swagger UI configured for **PKCE (`usePkceWithAuthorizationCodeGrant`)**

---

## 🚀 Relation to Other OSSS Components

Services that rely on this backend include:
- `a2a_server` — agent execution service
- frontend UI — Web app using backend APIs
- orchestration/graph runners — internal agent workflow logic

The backend is the **identity, request validation, and routing foundation** for OSSS.

---

## 🧾 License

This module is part of OSSS and is covered under the root project license located at:
`LICENSE` in the repository root.

---

```

> For a public client, leave `KEYCLOAK_CLIENT_SECRET` empty and make sure the client is set to "Public" in Keycloak.

## 2) Install & run

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8081
```

Open: http://localhost:8081/docs

Click "Authorize" and use your Keycloak user to try `/me`. For `/admin` your user must have the realm role set by `REQUIRED_ADMIN_ROLE` (default: `admin`).

## 3) Handy helpers

- `GET /healthz` — always 200 OK
- `GET /login-link` — shows the authorization URL (useful for quick tests)
- `GET /callback?code=...` — exchanges the auth code and redirects with tokens in the URL fragment (handy for a local SPA).

## Notes

- Token verification uses the realm JWKS. Audience is enforced to `KEYCLOAK_CLIENT_ID`.
- Swagger UI is configured for PKCE (`usePkceWithAuthorizationCodeGrant`).
