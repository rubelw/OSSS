# src/OSSS/tests/conftest.py
from __future__ import annotations

import os
import time
import base64
from typing import List, Optional
import sys
import logging
import pytest
import requests
from httpx import AsyncClient, ASGITransport
from fastapi.routing import APIRoute

@pytest.fixture(scope="session", autouse=True)
def _tests_log_to_stdout():
    """
    Ensure test logs go to stdout so they show up under pytest -s or log_cli=true.
    Avoid duplicates if handler is already present.
    """
    root = logging.getLogger()
    want = None
    for h in root.handlers:
        if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout:
            want = h
            break
    if want is None:
        want = logging.StreamHandler(sys.stdout)
        want.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root.addHandler(want)

    # Let the user override via TEST_LOG_LEVEL=DEBUG/INFO/WARNING...
    root.setLevel(os.getenv("TEST_LOG_LEVEL", "INFO").upper())

# ==============================================================
# Session-wide env bootstrap (runs before we create the app)
# ==============================================================

@pytest.fixture(scope="session", autouse=True)
def _env_bootstrap():
    # Default Keycloak-ish config for local dev
    os.environ.setdefault("KEYCLOAK_BASE_URL", "http://localhost:8085")
    os.environ.setdefault("KEYCLOAK_REALM", "OSSS")
    os.environ.setdefault("KEYCLOAK_CLIENT_ID", "osss-api")
    os.environ.setdefault("KEYCLOAK_CLIENT_SECRET", "password")  # override in CI/local

    issuer = os.environ.get("KEYCLOAK_ISSUER")
    if not issuer:
        issuer = f"{os.environ['KEYCLOAK_BASE_URL'].rstrip('/')}/realms/{os.environ['KEYCLOAK_REALM']}"
        os.environ["KEYCLOAK_ISSUER"] = issuer
    os.environ.setdefault("OIDC_ISSUER", issuer)
    os.environ.setdefault("OIDC_JWKS_URL", f"{issuer}/protocol/openid-connect/certs")
    os.environ.setdefault("JWT_ALLOWED_ALGS", "RS256")
    yield

# ==============================================================
# Live-mode detection and helpers
# ==============================================================

LIVE_BASE: Optional[str] = os.getenv("APP_BASE_URL", "").rstrip("/") or None
LIVE_MODE = bool(LIVE_BASE)
REAL_AUTH = os.getenv("INTEGRATION_AUTH", "0") == "1"  # use real Keycloak

def _issuer() -> Optional[str]:
    return (
        os.getenv("KEYCLOAK_ISSUER")
        or (
            os.getenv("KEYCLOAK_BASE_URL") and os.getenv("KEYCLOAK_REALM")
            and f"{os.getenv('KEYCLOAK_BASE_URL').rstrip('/')}/realms/{os.getenv('KEYCLOAK_REALM')}"
        )
    )

def _token_endpoint(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/protocol/openid-connect/token"

def _basic_auth_header(cid: str, secret: str) -> dict:
    raw = f"{cid}:{secret}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}

def _fmt_body(resp: requests.Response) -> str:
    try:
        return str(resp.json())
    except Exception:
        return (resp.text or "")[:800]

def _wait_for(url: str, timeout: float = 30.0, interval: float = 0.5):
    """Poll a URL until it returns 2xx–4xx (service up) or timeout."""
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3)
            if 200 <= r.status_code < 500:
                return
        except Exception as e:
            last_err = e
        time.sleep(interval)
    raise RuntimeError(f"Service not ready: {url} ({last_err})")

@pytest.fixture(scope="session", autouse=True)
def _ensure_services_ready():
    """When in LIVE_MODE, wait for the running app and (optionally) Keycloak."""
    if not LIVE_MODE:
        return
    _wait_for(f"{LIVE_BASE}/openapi.json", timeout=40)
    if REAL_AUTH:
        iss = _issuer()
        if iss:
            _wait_for(f"{iss}/.well-known/openid-configuration", timeout=40)

# ==============================================================
# Live-mode auth fixtures (real Keycloak only when INTEGRATION_AUTH=1)
# ==============================================================

@pytest.fixture(scope="session")
def base_url() -> Optional[str]:
    return LIVE_BASE

@pytest.fixture(scope="session")
def keycloak_token() -> str:
    """Real user token via password grant (integration-only)."""
    if not (LIVE_MODE and REAL_AUTH):
        pytest.skip("Not in live real-auth mode (APP_BASE_URL + INTEGRATION_AUTH=1 required).")
    issuer = _issuer()
    if not issuer:
        pytest.skip("KEYCLOAK_ISSUER or KEYCLOAK_BASE_URL/REALM not set.")

    client_id = os.getenv("KEYCLOAK_CLIENT_ID") or "osss-api"
    client_secret = os.getenv("KEYCLOAK_CLIENT_SECRET")
    if not client_secret:
        pytest.skip("KEYCLOAK_CLIENT_SECRET not set (confidential client required).")

    url = _token_endpoint(issuer)
    data = {
        "grant_type": "password",
        "username": os.getenv("OSSS_TEST_USER", "board_chair@osss.local"),
        "password": os.getenv("OSSS_TEST_PASS", "password"),
        "scope": "openid profile email",
    }

    # client_secret_basic
    r = requests.post(url, data=data, headers=_basic_auth_header(client_id, client_secret), timeout=15)
    if r.status_code == 200:
        return r.json()["access_token"]

    # fallback: client_secret_post
    r2 = requests.post(url, data={**data, "client_id": client_id, "client_secret": client_secret}, timeout=15)
    if r2.status_code == 200:
        return r2.json()["access_token"]

    pytest.fail(
        "[Keycloak] token fetch failed.\n"
        f"  basic={r.status_code} body={_fmt_body(r)}\n"
        f"  post ={r2.status_code} body={_fmt_body(r2)}"
    )

@pytest.fixture(scope="session")
def auth_headers(keycloak_token) -> dict:
    return {"Authorization": f"Bearer {keycloak_token}", "Accept": "application/json"}

# ==============================================================
# Client fixture (live vs in-process)
# ==============================================================

# In-process app factory (import after env is primed)
from OSSS.main import create_app  # noqa: E402

@pytest.fixture
async def client():
    """
    - LIVE_MODE: returns a requests.Session hitting APP_BASE_URL
    - Else: returns an httpx.AsyncClient against an in-process app, with fake auth
            unless INTEGRATION_AUTH=1 (REAL_AUTH)
    """
    if LIVE_MODE:
        s = requests.Session()
        s.headers.update({"Accept": "application/json"})
        try:
            yield s
        finally:
            s.close()
        return

    # In-process mode
    app = create_app()
    overrides: List[object] = []

    # Only apply fake auth when not explicitly using real auth
    if not REAL_AUTH:
        issuer = os.environ["KEYCLOAK_ISSUER"]

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

        # Override selected legacy guards (do NOT override get_current_user)
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

        # Only fake /debug/me explicitly
        for r in app.routes:
            if isinstance(r, APIRoute) and r.path == "/debug/me" and "GET" in (r.methods or []):
                for d in r.dependant.dependencies:
                    if d.call is not None:
                        app.dependency_overrides[d.call] = allow_all_security
                        overrides.append(d.call)

    transport = ASGITransport(app=app, lifespan="on")
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    for dep in overrides:
        app.dependency_overrides.pop(dep, None)
