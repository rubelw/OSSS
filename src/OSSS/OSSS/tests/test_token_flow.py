# src/OSSS/tests/test_token_flow.py
from __future__ import annotations

import os
import json
import requests
import pytest

# Live-mode switches
BASE = os.getenv("APP_BASE_URL", "").rstrip("/") or None
LIVE_MODE = bool(BASE)
REAL_AUTH = os.getenv("INTEGRATION_AUTH", "0") == "1"

# Try these in order if OpenAPI discovery doesn't find a token path
TOKEN_PATH_CANDIDATES = ("/token", "/auth/token", "/api/token", "/v1/token")


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


def _discover_token_paths_from_spec(spec: dict | None) -> list[str]:
    """Find POST operations that look like a token endpoint."""
    if not spec:
        return list(TOKEN_PATH_CANDIDATES)
    paths = []
    for path, ops in (spec.get("paths") or {}).items():
        post_op = (ops or {}).get("post")
        if not post_op:
            continue
        if path.endswith("/token") or path.endswith("/token/"):
            paths.append(path)
    return paths or list(TOKEN_PATH_CANDIDATES)


def _post_token_live(payload: dict) -> requests.Response | None:
    """
    Try POSTing as form first, then JSON, across discovered candidate paths.
    Returns the first non-404 response (or the last tried response).
    """
    assert BASE, "APP_BASE_URL must be set for live-mode tests."
    spec = _fetch_openapi()
    candidates = _discover_token_paths_from_spec(spec)
    last = None

    # form-encoded
    for p in candidates:
        try:
            resp = requests.post(BASE + p, data=payload, timeout=12)
        except Exception:
            continue
        last = resp
        if resp.status_code != 404:
            return resp

    # json
    for p in candidates:
        try:
            resp = requests.post(BASE + p, json=payload, timeout=12)
        except Exception:
            continue
        last = resp
        if resp.status_code != 404:
            return resp

    return last


def _extract_access_token(data):
    if not isinstance(data, dict):
        return None
    if "access_token" in data:
        return data["access_token"]
    tok = data.get("token")
    if isinstance(tok, dict):
        return tok.get("access_token")
    return None


# --------------------------- tests (live-mode only) ---------------------------

@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
def test_password_grant_failure_live():
    """
    Negative test without monkeypatching: bad credentials should NOT yield 200.
    Accept common API mappings: 400 (from IdP), 401/403 (gateway mapping).
    """
    payload = {"username": "bad_user@example.com", "password": "totally-wrong", "grant_type": "password"}
    # Optional extras if your token route expects them:
    if os.getenv("TOKEN_SCOPE"):
        payload["scope"] = os.getenv("TOKEN_SCOPE")
    if os.getenv("TOKEN_CLIENT_ID"):
        payload["client_id"] = os.getenv("TOKEN_CLIENT_ID")

    r = _post_token_live(payload)
    if r is None or r.status_code == 404:
        pytest.skip("No token endpoint found on live app.")
    assert r.status_code in (400, 401, 403)


@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
@pytest.mark.skipif(not REAL_AUTH, reason="INTEGRATION_AUTH=1 required for real auth success flow")
@pytest.mark.timeout(45)
def test_password_grant_success_live():
    """
    Success path against the live app & real IdP.
    Uses OSSS_TEST_USER/OSSS_TEST_PASS if set; otherwise falls back to
    'board_chair@osss.local' / 'password'.
    """
    username = os.getenv("OSSS_TEST_USER", "board_chair@osss.local")
    password = os.getenv("OSSS_TEST_PASS", "password")

    payload = {"username": username, "password": password, "grant_type": "password"}
    # Optional extras if your token route expects them:
    if os.getenv("TOKEN_SCOPE"):
        payload["scope"] = os.getenv("TOKEN_SCOPE")
    if os.getenv("TOKEN_CLIENT_ID"):
        payload["client_id"] = os.getenv("TOKEN_CLIENT_ID")

    r = _post_token_live(payload)
    if r is None or r.status_code == 404:
        pytest.skip("No token endpoint found on live app.")

    assert 200 <= r.status_code < 300, f"Unexpected status {r.status_code}: {(r.text or '')[:400]}"

    try:
        body = r.json()
    except Exception:
        pytest.fail(f"Expected JSON body with token, got: {(r.text or '')[:400]}")

    token = _extract_access_token(body)
    assert token, f"No access_token in response: {json.dumps(body)[:800]}"
    if isinstance(body, dict):
        assert "token_type" in body or "access_token" in body
