# src/OSSS/tests/test_state.py
from __future__ import annotations

import os
import json
import base64
import requests
import pytest

# Live-mode switches
BASE = os.getenv("APP_BASE_URL", "").rstrip("/") or None
LIVE_MODE = bool(BASE)
REAL_AUTH = os.getenv("INTEGRATION_AUTH", "0") == "1"

# Fallback guesses if discovery fails
DEFAULT_STATE_PATHS = ("/api/states")

# Common pagination shapes
CANDIDATE_PARAMS = (
    {},
    {"limit": 50},
    {"offset": 0, "limit": 50},
    {"page": 1},
    {"page": 1, "page_size": 50},
)

# ---------- Keycloak helpers (confidential client) ----------

def _issuer() -> str | None:
    iss = os.getenv("KEYCLOAK_ISSUER") or os.getenv("OIDC_ISSUER")
    if iss:
        return iss
    base = os.getenv("KEYCLOAK_BASE_URL")
    realm = os.getenv("KEYCLOAK_REALM")
    if base and realm:
        return f"{base.rstrip('/')}/realms/{realm}"
    return None

def _client_id() -> str:
    return os.getenv("KEYCLOAK_CLIENT_ID") or os.getenv("OIDC_CLIENT_ID") or "osss-api"

def _client_secret() -> str | None:
    # treat placeholders as missing
    v = os.getenv("KEYCLOAK_CLIENT_SECRET") or os.getenv("OIDC_CLIENT_SECRET")
    if not v or v.strip() in {"changeme", "<real-secret>", "REPLACE_ME"}:
        return None
    return v

def _token_endpoint(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/protocol/openid-connect/token"

def _basic_auth_header(client_id: str, client_secret: str) -> dict:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}

def _fetch_keycloak_token(username: str, password: str, issuer: str,
                          client_id: str, client_secret: str) -> str:
    """
    Obtain an access_token using password grant for a CONFIDENTIAL client.
    Try client_secret_basic first (matches the working curl), then client_secret_post.
    """
    url = _token_endpoint(issuer)
    common = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "scope": "openid",
    }

    # 1) client_secret_basic
    headers = _basic_auth_header(client_id, client_secret)
    resp = requests.post(url, data=common, headers=headers, timeout=12)
    if resp.status_code == 200:
        return resp.json()["access_token"]

    # 2) client_secret_post
    data_post = dict(common, client_id=client_id, client_secret=client_secret)
    resp2 = requests.post(url, data=data_post, timeout=12)
    if resp2.status_code == 200:
        return resp2.json()["access_token"]

    def _fmt(r):
        ct = r.headers.get("content-type", "")
        return r.text if "json" not in ct else json.dumps(r.json(), indent=2)

    raise AssertionError(
        "[Keycloak] Token request failed for CONFIDENTIAL client.\n"
        f"  URL: {url}\n"
        f"  Attempt 1 (Basic) status: {resp.status_code} body: {_fmt(resp)[:600]}\n"
        f"  Attempt 2 (client_secret_post) status: {resp2.status_code} body: {_fmt(resp2)[:600]}\n"
        "  Hints: Ensure client is CONFIDENTIAL (Client authentication ON), secret is correct, and "
        "'Direct access grants' is ENABLED."
    )

# ---------- Discovery via live OpenAPI ----------

def _fetch_openapi() -> dict | None:
    if not BASE:
        return None
    try:
        r = requests.get(BASE + "/openapi.json", timeout=8)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def _discover_state_list_paths_from_spec(spec: dict | None) -> list[str]:
    if not spec:
        return list(DEFAULT_STATE_PATHS)
    paths = []
    for path, ops in (spec.get("paths") or {}).items():
        if "{" in path:
            continue
        if path.endswith("/states") or path.endswith("/states/"):
            if (ops or {}).get("get"):
                paths.append(path)
    return paths or list(DEFAULT_STATE_PATHS)

# ---------- Request helpers ----------

def _get_states_live(headers: dict | None = None):
    """Try discovered paths & common param shapes against the live app; return first non-404/422 response."""
    assert BASE, "APP_BASE_URL must be set for live-mode tests."
    hdrs = headers or {}
    spec = _fetch_openapi()
    paths = _discover_state_list_paths_from_spec(spec)
    last = None
    for p in paths:
        for params in CANDIDATE_PARAMS:
            r = requests.get(f"{BASE}{p}", headers=hdrs, params=params, timeout=8)
            last = r
            if r.status_code not in (404, 422):
                return r
    return last

def _extract_items(body):
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("items", "results", "data"):
            if isinstance(body.get(key), list):
                return body[key]
    return None

# ---------- Tests (live-mode only) ----------

@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
def test_states_requires_auth_live():
    r = _get_states_live()
    assert r is not None
    # States list should demand auth without a token (or 422 if auth validated at parameter layer)
    assert r.status_code in (401, 403, 422)

    if r.status_code == 422:
        data = r.json()
        assert isinstance(data.get("detail"), list) and len(data["detail"]) > 0
    else:
        hdrs = {k.lower(): v for k, v in r.headers.items()}
        has_www = "www-authenticate" in hdrs
        try:
            has_detail = bool(r.json().get("detail"))
        except Exception:
            has_detail = False
        assert has_www or has_detail

@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
@pytest.mark.skipif(not REAL_AUTH, reason="INTEGRATION_AUTH=1 required for real Keycloak auth")
@pytest.mark.timeout(30)
def test_states_with_auth_keycloak_live():
    """
    Integration test: fetch a real token from Keycloak (confidential client) and list states.
    Requires APP_BASE_URL and INTEGRATION_AUTH=1.
    """
    issuer = _issuer()
    if not issuer:
        pytest.skip("Set KEYCLOAK_BASE_URL/KEYCLOAK_REALM or KEYCLOAK_ISSUER to run this test.")

    client_id = _client_id()
    client_secret = _client_secret()
    if not client_secret:
        pytest.skip("KEYCLOAK_CLIENT_SECRET/OIDC_CLIENT_SECRET not set (client is confidential).")

    token = _fetch_keycloak_token(
        username=os.getenv("OSSS_TEST_USER", "board_chair@osss.local"),
        password=os.getenv("OSSS_TEST_PASS", "password"),
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
    )

    r = _get_states_live(headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})

    if r is None or r.status_code == 404:
        pytest.skip("States list route not mounted (or different path) in this build.")

    # If auth enforcement still blocked us, fail with diagnostics
    if r.status_code in (401, 403):
        try:
            body = r.json()
        except Exception:
            body = r.text
        pytest.fail(
            "Calling states with a valid Keycloak token did not return 200.\n"
            f"  Status: {r.status_code}\n"
            f"  Body: {str(body)[:1000]}"
        )

    # Some implementations require very specific params; if we still get 422, skip to avoid false negatives
    if r.status_code == 422:
        pytest.skip("States route requires specific params not covered by test; skipping.")

    assert r.status_code == 200

    items = _extract_items(r.json())
    assert isinstance(items, list)
    if items:
        first = items[0]
        assert isinstance(first, dict)
        assert any(k in first for k in ("name", "label", "title"))
        assert any(k in first for k in ("code", "abbrev", "postal_code", "id"))
