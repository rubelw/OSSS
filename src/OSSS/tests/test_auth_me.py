# src/OSSS/tests/test_auth_me.py
import os
import json
import base64
import requests
import pytest

ME_CANDIDATES = ("/me", "/auth/me", "/debug/me")


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


def _app_base_url() -> str | None:
    v = os.getenv("APP_BASE_URL", "").rstrip("/")
    return v or None


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

    # 1) client_secret_basic (no client_id/secret in body; only Authorization header)
    headers = _basic_auth_header(client_id, client_secret)
    resp = requests.post(url, data=common, headers=headers, timeout=12)
    if resp.status_code == 200:
        return resp.json()["access_token"]

    # 2) client_secret_post (put both in the body)
    data_post = dict(common)
    data_post["client_id"] = client_id
    data_post["client_secret"] = client_secret
    resp2 = requests.post(url, data=data_post, timeout=12)
    if resp2.status_code == 200:
        return resp2.json()["access_token"]

    # diagnostics
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


def _call_me_with_token(client_or_base, token: str):
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if isinstance(client_or_base, str):
        last = None
        for path in ME_CANDIDATES:
            r = requests.get(f"{client_or_base}{path}", headers=headers, timeout=8)
            if r.status_code != 404:
                return r
            last = r
        return last
    else:
        client = client_or_base
        last = None
        for path in ME_CANDIDATES:
            r = client.get(path, headers=headers)
            if r.status_code != 404:
                return r
            last = r
        return last


def _call_me_unauth(client_or_base):
    if isinstance(client_or_base, str):
        last = None
        for path in ME_CANDIDATES:
            r = requests.get(f"{client_or_base}{path}", timeout=8)
            if r.status_code != 404:
                return r
            last = r
        return last
    else:
        client = client_or_base
        last = None
        for path in ME_CANDIDATES:
            r = client.get(path)
            if r.status_code != 404:
                return r
            last = r
        return last


# ------------------------ tests ------------------------

def test_me_requires_auth(client):
    """Endpoint should require auth without a token."""
    r = _call_me_unauth(client)
    if r.status_code == 404:
        pytest.skip("No /me route mounted in this build.")
    assert r.status_code in (401, 403, 422)


@pytest.mark.timeout(30)
def test_me_with_keycloak_board_chair(client):
    """
    Integration test against a CONFIDENTIAL Keycloak client.
    Skips only when issuer or client secret is not provided via env.
    """
    issuer = _issuer()
    if not issuer:
        pytest.skip("Set KEYCLOAK_BASE_URL/KEYCLOAK_REALM or KEYCLOAK_ISSUER to run this test.")

    client_id = _client_id()
    client_secret = _client_secret()
    if not client_secret:
        pytest.skip("KEYCLOAK_CLIENT_SECRET/OIDC_CLIENT_SECRET not set (client is confidential).")

    token = _fetch_keycloak_token(
        username="board_chair@osss.local",
        password="password",
        issuer=issuer,
        client_id=client_id,
        client_secret=client_secret,
    )

    target = _app_base_url() or client
    r = _call_me_with_token(target, token)

    if r.status_code != 200:
        try:
            body = r.json()
        except Exception:
            body = r.text
        pytest.fail(
            "Calling /me with a valid Keycloak token did not return 200.\n"
            f"  Status: {r.status_code}\n"
            f"  Body: {str(body)[:1200]}\n"
            f"  Hitting: {'APP_BASE_URL='+_app_base_url() if _app_base_url() else 'TestClient'}\n"
            f"  Issuer: {issuer}\n"
            f"  Client ID: {client_id}\n"
            f"  Client secret provided: True"
        )

    body = r.json()
    assert body.get("preferred_username") or body.get("email") or body.get("sub")
    pu = body.get("preferred_username")
    if pu:
        assert "board" in pu
