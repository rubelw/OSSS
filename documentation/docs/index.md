# Open Source School Software (OSSS)

[![CodeFactor](https://www.codefactor.io/repository/github/rubelw/OSSS/badge)](https://www.codefactor.io/repository/github/rubelw/OSSS)
[![codecov](https://codecov.io/gh/rubelw/OSSS/branch/main/graph/badge.svg)](https://codecov.io/gh/rubelw/OSSS)

---

## Introduction

Welcome to **OSSS (Open Source School Software)** — a polyglot monorepo of apps and shared packages for K-12 districts.  
This package provides a **FastAPI + Keycloak** integration used across OSSS apps (e.g., the School Board Management suite).  
It supports the **password** and **authorization_code** flows, and `get_current_user()` accepts any JWT signed by your Keycloak.

> Built for reuse inside this monorepo, but totally fine to use as a standalone package in your own FastAPI projects.

---

## Installation

From PyPI (when published):

```bash
pip install OSSS
```

From source (inside this repo):

```bash
pip install -e .
```

Optional server extras (Gunicorn):

```bash
pip install "OSSS[server]"
```

---

## TL;DR

With this package you can:

- Verify user identities and realm roles via Keycloak
- List configured identity providers
- Create / read / delete **users**, **groups**, and **roles**
- Assign/remove **roles** from users; assign/remove **users** from groups
- Implement **password** or **authorization_code** flows (login/callback/logout)
- (Optional) Use Redis-backed caching to speed up OIDC discovery/JWKS fetches

---

## Quickstart (minimal FastAPI app)

```python
from fastapi import FastAPI, Depends, HTTPException
from OSSS.api import FastAPIKeycloak, OIDCUser

app = FastAPI(title="OSSS Auth Example")

idp = FastAPIKeycloak(
    server_url="http://localhost:8085",         # Keycloak base URL (no trailing /auth)
    realm="Test",
    client_id="test-client",
    client_secret="...client-secret...",
    admin_client_secret="...admin-cli-secret...",
    callback_uri="http://localhost:8081/callback",
)

# Make OAuth client config available in Swagger UI
idp.add_swagger_config(app)

@app.get("/protected")
def protected(user: OIDCUser = Depends(idp.get_current_user())):
    return {"sub": user.sub, "email": user.email, "roles": user.roles}

@app.get("/login-link")
def login_link():
    return {"auth_url": idp.login_uri}

@app.get("/callback")
def callback(session_state: str, code: str):
    return idp.exchange_authorization_code(session_state=session_state, code=code)
```

**Typical environment variables (dev/CI):**

- `KEYCLOAK_URL` (e.g., `http://localhost:8085`)
- `KEYCLOAK_REALM` (e.g., `Test`)
- `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`
- `KEYCLOAK_ADMIN_CLIENT_SECRET` (service account for admin-cli)
- `CALLBACK_URI` (e.g., `http://localhost:8081/callback`)

In the OSSS monorepo, a local `docker compose` stack brings up Keycloak and Postgres; see `infra/docker` for dev configs.

---

## Redis Caching (optional)

Speed up OIDC discovery & JWKS retrieval with Redis by setting:

```bash
export OSSS_CACHE_REDIS_URL=redis://redis:6379/0
```

When this variable is present, the library will cache:

- OIDC discovery document (`/.well-known/openid-configuration`)
- JWKS (public keys)
- Token validation helpers

---

## Where this fits in the monorepo

- Used by apps like **School Board Management Software** to provide SSO, roles, and protected APIs.
- Lives alongside other shared packages under `src/` and is shipped as a Python package named **OSSS**.

---
