# FastAPI + Keycloak (minimal)

A tiny FastAPI app that validates Keycloak access tokens (via JWKS), exposes an unprotected `/healthz`, plus two protected endpoints:
- `GET /me` — requires a valid bearer token
- `GET /admin` — requires a realm role (defaults to `admin`, configurable)

## 1) Configure environment

```bash
export KEYCLOAK_BASE_URL="http://localhost:8085"   # no trailing /auth
export KEYCLOAK_REALM="myrealm"
export KEYCLOAK_CLIENT_ID="my-fastapi"
export KEYCLOAK_CLIENT_SECRET="your-client-secret-if-confidential"
export CALLBACK_URL="http://localhost:8081/callback"
export REQUIRED_ADMIN_ROLE="admin"  # change if you like
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
