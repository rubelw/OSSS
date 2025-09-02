# src/OSSS/tests/conftest.py
import os
import pytest

# conftest.py (add this near the top)
import os
import pytest

@pytest.fixture(scope="session", autouse=True)
def _env_bootstrap():
    # Default Keycloak config for local dev
    os.environ.setdefault("KEYCLOAK_BASE_URL", "http://localhost:8085")
    os.environ.setdefault("KEYCLOAK_REALM", "OSSS")
    os.environ.setdefault("KEYCLOAK_CLIENT_ID", "osss-api")
    os.environ.setdefault("KEYCLOAK_CLIENT_SECRET", "password")  # <-- your real secret

    # Ensure issuer & JWKS for the app so it can validate tokens
    issuer = os.environ.get("KEYCLOAK_ISSUER")
    if not issuer:
        issuer = f"{os.environ['KEYCLOAK_BASE_URL'].rstrip('/')}/realms/{os.environ['KEYCLOAK_REALM']}"
        os.environ["KEYCLOAK_ISSUER"] = issuer

    os.environ.setdefault("OIDC_ISSUER", issuer)
    os.environ.setdefault("OIDC_JWKS_URL", f"{issuer}/protocol/openid-connect/certs")

    # When you want real auth in tests, export INTEGRATION_AUTH=1 in your shell
    # (we don't force it here)
    yield

# --- Make sure OIDC/Keycloak env is set BEFORE importing the app/auth ----
os.environ.setdefault("KEYCLOAK_BASE_URL", "http://localhost:8085")
os.environ.setdefault("KEYCLOAK_REALM", "OSSS")
os.environ.setdefault("KEYCLOAK_CLIENT_ID", "osss-api")
# Only set this if your client is Confidential and this is the real secret.
# Do NOT set it for a Public client.
# os.environ.setdefault("KEYCLOAK_CLIENT_SECRET", "<real-secret>")

issuer = f"{os.environ['KEYCLOAK_BASE_URL'].rstrip('/')}/realms/{os.environ['KEYCLOAK_REALM']}"
os.environ.setdefault("OIDC_ISSUER", issuer)
os.environ.setdefault("KEYCLOAK_ISSUER", issuer)  # for code that reads KEYCLOAK_ISSUER
os.environ.setdefault("OIDC_JWKS_URL", f"{issuer}/protocol/openid-connect/certs")
os.environ.setdefault("JWT_ALLOWED_ALGS", "RS256")

# Disable test-time auth overrides when running real integration auth
# (set INTEGRATION_AUTH=1 in your shell to use real Keycloak)
USE_FAKE_AUTH = os.getenv("INTEGRATION_AUTH", "0") != "1"

import pytest
from starlette.testclient import TestClient
from fastapi.routing import APIRoute

# Import AFTER env is set so deps.py picks up the right values
from OSSS.main import app

@pytest.fixture()
def client():
    overrides = []

    if USE_FAKE_AUTH:
        async def allow_all_security():
            return {
                "active": True,
                "sub": "user-123",
                "preferred_username": "tester",
                "email": "tester@example.com",
                "aud": ["osss-api"],
                "azp": "osss-web",
                "iss": issuer,
                "realm_access": {"roles": ["user"]},
            }

        # optional: override ONLY legacy guards; do NOT override get_current_user
        for mod_path, name in (
            ("OSSS.auth.deps", "oauth2"),
            ("OSSS.api.security", "oauth2"),
            ("OSSS.api.security", "require_auth"),
            ("OSSS.api.auth", "require_auth"),
        ):
            try:
                mod = __import__(mod_path, fromlist=[name])
                dep = getattr(mod, name, None)
                if dep is not None:
                    app.dependency_overrides[dep] = allow_all_security
                    overrides.append(dep)
            except Exception:
                pass

        # only /debug/me should be faked
        for r in app.routes:
            if isinstance(r, APIRoute) and r.path == "/debug/me" and "GET" in (r.methods or []):
                for d in r.dependant.dependencies:
                    if d.call is not None:
                        app.dependency_overrides[d.call] = allow_all_security
                        overrides.append(d.call)

    with TestClient(app) as c:
        yield c

    for dep in overrides:
        app.dependency_overrides.pop(dep, None)
