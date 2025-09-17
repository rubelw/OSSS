# src/OSSS/tests/conftest.py
from __future__ import annotations

import os
import time
import base64
from typing import List, Optional, Callable, Awaitable
import sys
import logging
import pytest
import requests

# NEW: async/network helpers
import asyncio
import random
import httpx
from httpx import AsyncClient, ASGITransport

from fastapi.routing import APIRoute

# =========================
# Logging -> stdout
# =========================
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


# Make anyio run on asyncio (so our async fixtures work everywhere)
@pytest.fixture(scope="session", autouse=True)
def anyio_backend():
    return "asyncio"


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
    """
    When in LIVE_MODE, wait for the running app and (optionally) Keycloak.
    Prefer /healthz (faster), then fall back to /openapi.json.
    Controlled by env:
      TEST_HEALTHZ_TIMEOUT (default 60)
      TEST_HEALTHZ_INTERVAL (default 0.5)
    """
    if not LIVE_MODE:
        return
    timeout = float(os.getenv("TEST_HEALTHZ_TIMEOUT", "60"))
    interval = float(os.getenv("TEST_HEALTHZ_INTERVAL", "0.5"))

    # First try /healthz (if present)
    try:
        _wait_for(f"{LIVE_BASE}/healthz", timeout=timeout, interval=interval)
    except Exception:
        _wait_for(f"{LIVE_BASE}/openapi.json", timeout=timeout, interval=interval)

    if REAL_AUTH:
        iss = _issuer()
        if iss:
            _wait_for(f"{iss}/.well-known/openid-configuration", timeout=timeout, interval=interval)


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
# Throttle + Retry (politeness under load)
# ==============================================================

# Tunables via env (no code changes later)
_TEST_QPS = float(os.getenv("TEST_QPS", "5"))                   # requests per second (global)
_TEST_MAX_INFLIGHT = int(os.getenv("TEST_MAX_INFLIGHT", "4"))   # concurrent in-flight requests
_TEST_HTTP_MAX = int(os.getenv("TEST_HTTP_MAX", "20"))          # httpx connection pool size
_TEST_PER_CASE_DELAY = float(os.getenv("TEST_PER_CASE_DELAY", "0.05"))  # seconds

class _RateLimiter:
    def __init__(self, qps: float, max_inflight: int):
        self.min_interval = 1.0 / qps if qps > 0 else 0.0
        self._next_ok_at = 0.0
        self._lock = asyncio.Lock()
        self._sema = asyncio.Semaphore(max_inflight)

    async def __aenter__(self):
        await self._sema.acquire()
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait = max(0.0, self._next_ok_at - now)
            if wait:
                await asyncio.sleep(wait)
            self._next_ok_at = asyncio.get_event_loop().time() + self.min_interval
        return self

    async def __aexit__(self, *exc):
        self._sema.release()


@pytest.fixture(scope="session")
def request_limits():
    return _RateLimiter(_TEST_QPS, _TEST_MAX_INFLIGHT)


RETRY_STATUS = {429, 500, 502, 503, 504}

async def _aget_with_retry(client: httpx.AsyncClient, url: str, **kw):
    """
    GET with retries/backoff on transient status codes and network hiccups.
    Accepts optional kwargs:
      retries (int), backoff_base (float), backoff_max (float)
    """
    retries = int(kw.pop("retries", 5))
    base = float(kw.pop("backoff_base", 0.25))
    max_backoff = float(kw.pop("backoff_max", 3.0))
    for attempt in range(retries + 1):
        try:
            r = await client.get(url, **kw)
            if r.status_code in RETRY_STATUS and attempt < retries:
                await asyncio.sleep(min(max_backoff, base * (2 ** attempt)) + random.random() * 0.2)
                continue
            return r
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError):
            if attempt >= retries:
                raise
            await asyncio.sleep(min(max_backoff, base * (2 ** attempt)) + random.random() * 0.2)


# A tiny yield per parametrized test to avoid stampedes
@pytest.fixture(autouse=True)
async def _polite_delay():
    await asyncio.sleep(_TEST_PER_CASE_DELAY)


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
                    # FastAPI dependency override
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


# ==============================================================
# aget fixture: polite, retried GET for both live & in-process
# ==============================================================

@pytest.fixture
async def aget(request_limits, base_url, client) -> Callable[[str], Awaitable[httpx.Response]]:
    """
    Usage in tests:
        r = await aget("/api/work_orders", headers=auth_headers, timeout=12)
    This wraps requests through a limiter and adds retries/backoff.

    - In LIVE_MODE, uses a shared httpx.AsyncClient to talk to APP_BASE_URL.
    - In in-process mode, reuses the AsyncClient created by the `client` fixture.
    """
    # Connection pool + timeout sane defaults
    limits = httpx.Limits(max_connections=_TEST_HTTP_MAX, max_keepalive_connections=10)
    timeout = httpx.Timeout(connect=5, read=20, write=10, pool=5)

    live_client: Optional[httpx.AsyncClient] = None

    if LIVE_MODE:
        live_client = httpx.AsyncClient(base_url=base_url, limits=limits, timeout=timeout)

    async def _call(path: str, **kw):
        # Normalize to absolute URL or /relative under base_url
        if path.startswith("http://") or path.startswith("https://"):
            url = path
        elif path.startswith("/"):
            url = (base_url or "http://testserver") + path
        else:
            # treat as-is; tests often pass full URL already
            url = path

        async with request_limits:
            if LIVE_MODE:
                assert live_client is not None
                return await _aget_with_retry(live_client, url, **kw)
            else:
                # 'client' is AsyncClient in in-process mode
                assert isinstance(client, AsyncClient), "Expected AsyncClient in in-process mode"
                return await _aget_with_retry(client, url, **kw)

    try:
        yield _call
    finally:
        if live_client is not None:
            await live_client.aclose()
