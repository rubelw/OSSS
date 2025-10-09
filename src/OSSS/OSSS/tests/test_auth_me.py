# src/OSSS/tests/test_auth_me.py
from __future__ import annotations

import os
import json
import base64
import requests
import pytest

ME_CANDIDATES = ("/me", "/auth/me", "/debug/me")

# -------- live-mode switches --------
BASE = os.getenv("APP_BASE_URL", "").rstrip("/") or None
LIVE_MODE = bool(BASE)
REAL_AUTH = os.getenv("INTEGRATION_AUTH", "0") == "1"


# ------------------------ helpers ------------------------

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
    return os.getenv("KEYCLOAK_CLIENT_SECRET") or os.getenv("OIDC_CLIENT_SECRET")


def _token_endpoint(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/protocol/openid-connect/token"


def _basic_auth_header(client_id: str, client_secret: str) -> dict:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def _fetch_keycloak_token(username: str, password: str, issuer: str,
                          client_id: str, client_secret: str) -> str:
    """
    Obtain an access_token using password grant for a CONFIDENTIAL client.
    Tries client_secret_basic (matches your working curl) then client_secret_post.
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
        f"  Attempt 2 (client_secret_post) status: {resp2.status_code} body: {_fmt(resp2)[:600]}"
    )


def _get_full(path: str, **kwargs):
    """Always build an absolute URL against the live app."""
    if not BASE:
        raise RuntimeError("APP_BASE_URL not set; this test runs only in live mode.")
    return requests.get(f"{BASE}{path}", **kwargs)


def _call_me_with_token(token: str):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    last = None
    for path in ME_CANDIDATES:
        r = _get_full(path, headers=headers, timeout=8)
        if r.status_code != 404:
            return r
        last = r
    return last


def _call_me_unauth():
    last = None
    for path in ME_CANDIDATES:
        r = _get_full(path, timeout=8)
        if r.status_code != 404:
            return r
        last = r
    return last


# ------------------------ tests (live-mode integration) ------------------------

@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
def test_me_requires_auth_live():
    """Endpoint should require auth without a token (live app)."""
    r = _call_me_unauth()
    if r.status_code == 404:
        pytest.skip("No /me route mounted in this build.")
    assert r.status_code in (401, 403, 422)


@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
@pytest.mark.skipif(not REAL_AUTH, reason="INTEGRATION_AUTH=1 required for real Keycloak auth")
@pytest.mark.timeout(30)
def test_me_with_keycloak_board_chair_live():
    """
    Live integration test against a CONFIDENTIAL Keycloak client.
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

    r = _call_me_with_token(token)

    if r.status_code != 200:
        try:
            body = r.json()
        except Exception:
            body = r.text
        pytest.fail(
            "Calling /me with a valid Keycloak token did not return 200.\n"
            f"  Status: {r.status_code}\n"
            f"  Body: {str(body)[:1200]}\n"
            f"  APP_BASE_URL: {BASE}\n"
            f"  Issuer: {issuer}\n"
            f"  Client ID: {client_id}\n"
            f"  Client secret provided: True"
        )

    body = r.json()
    assert body.get("preferred_username") or body.get("email") or body.get("sub")
    pu = body.get("preferred_username")
    if pu:
        assert "board" in pu
