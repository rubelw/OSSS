# src/OSSS/tests/users/test_board_chair.py

import os
import json
import base64
import requests
import pytest

# If APP_BASE_URL is set, we hit the running server; otherwise we use TestClient(app)
BASE_URL = os.getenv("APP_BASE_URL", "").rstrip("/") or None
STRICT = os.getenv("STRICT_ENDPOINTS", "0") == "1"  # fail on 401/403/404/422 if True

# ---------- Keycloak helpers ----------

def _issuer() -> str | None:
    return (
        os.getenv("KEYCLOAK_ISSUER")
        or (
            os.getenv("KEYCLOAK_BASE_URL") and os.getenv("KEYCLOAK_REALM")
            and f"{os.getenv('KEYCLOAK_BASE_URL').rstrip('/')}/realms/{os.getenv('KEYCLOAK_REALM')}"
        )
        or os.getenv("OIDC_ISSUER")
    )

def _client_id() -> str:
    return os.getenv("KEYCLOAK_CLIENT_ID") or os.getenv("OIDC_CLIENT_ID") or "osss-api"

def _client_secret() -> str | None:
    return os.getenv("KEYCLOAK_CLIENT_SECRET") or os.getenv("OIDC_CLIENT_SECRET")

def _token_endpoint(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/protocol/openid-connect/token"

def _basic_auth_header(client_id: str, client_secret: str) -> dict:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}

def _fmt_body(resp):
    try:
        return resp.json()
    except Exception:
        return (resp.text or "")[:800]

@pytest.fixture(scope="session")
def keycloak_token() -> str:
    issuer = _issuer()
    if not issuer:
        pytest.skip("Issuer env not set (KEYCLOAK_BASE_URL/REALM or KEYCLOAK_ISSUER).")
    client_id = _client_id()
    client_secret = _client_secret()
    if not client_secret:
        pytest.skip("KEYCLOAK_CLIENT_SECRET/OIDC_CLIENT_SECRET not set (confidential client required).")

    url = _token_endpoint(issuer)
    common = {
        "grant_type": "password",
        "username": os.getenv("OSSS_TEST_USER", "board_chair@osss.local"),
        "password": os.getenv("OSSS_TEST_PASS", "password"),
        "scope": "openid",
    }

    # client_secret_basic (matches your working curl)
    headers = _basic_auth_header(client_id, client_secret)
    r = requests.post(url, data=common, headers=headers, timeout=12)
    if r.status_code == 200:
        return r.json()["access_token"]

    # fallback: client_secret_post
    data_post = dict(common, client_id=client_id, client_secret=client_secret)
    r2 = requests.post(url, data=data_post, timeout=12)
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

# ---------- Transport helpers ----------

def _fetch_openapi_via_live():
    r = requests.get(BASE_URL + "/openapi.json", timeout=8)
    r.raise_for_status()
    return r.json()

def _fetch_openapi_via_testclient():
    from starlette.testclient import TestClient
    from OSSS.main import app
    with TestClient(app) as c:
        return c.get("/openapi.json").json()

def _fetch_openapi():
    return _fetch_openapi_via_live() if BASE_URL else _fetch_openapi_via_testclient()

def _probe_get(path: str, headers: dict):
    if BASE_URL:
        return requests.get(BASE_URL + path, headers=headers, timeout=12)
    else:
        from starlette.testclient import TestClient
        from OSSS.main import app
        with TestClient(app) as c:
            return c.get(path, headers=headers)

# ---------- Path discovery (list-only GET endpoints; no templated params) ----------

def _discover_list_get_paths(spec: dict) -> list[str]:
    out = []
    for path, ops in (spec.get("paths") or {}).items():
        if "{" in path:   # skip item endpoints
            continue
        get_op = (ops or {}).get("get")
        if not get_op:
            continue
        out.append(path)
    return sorted(set(out))

# Discover ONCE at import time to parametrize statically (no dynamic add_marker)
try:
    _SPEC = _fetch_openapi()
    LIST_PATHS = _discover_list_get_paths(_SPEC) or ["__NO_LIST_ENDPOINTS_FOUND__"]
except Exception as e:
    # If OpenAPI is unavailable during collection, create a sentinel so the test shows a reason.
    LIST_PATHS = [f"__OPENAPI_FETCH_FAILED__:{e}"]

# ---------- The actual test ----------

@pytest.mark.integration
@pytest.mark.parametrize("list_path", LIST_PATHS)
def test_get_list_endpoint(list_path, auth_headers):
    # Handle sentinels explicitly so they show up as skips (with reason)
    if list_path.startswith("__OPENAPI_FETCH_FAILED__"):
        pytest.skip(list_path)

    if list_path == "__NO_LIST_ENDPOINTS_FOUND__":
        pytest.skip("No list-style GET endpoints discovered from OpenAPI.")

    # Ensure it still exists at runtime
    spec = _fetch_openapi()
    if list_path not in set(_discover_list_get_paths(spec)):
        pytest.skip(f"{list_path} not present in current OpenAPI.")

    r = _probe_get(list_path, headers=auth_headers)

    # Hard fail on 5xx
    if r.status_code >= 500:
        pytest.fail(f"{list_path} -> {r.status_code}: {_fmt_body(r)}")

    # Show role gates clearly. In non-STRICT mode, make them xfail so they are visible.
    if r.status_code in (401, 403, 404, 422) and not STRICT:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = None
        if isinstance(detail, dict) and detail.get("error") == "missing_required_roles":
            need_any = detail.get("need_any_of") or []
            need_all = detail.get("need_all_of") or []
            pytest.xfail(f"{list_path} requires roles any_of={need_any} all_of={need_all}")
        pytest.xfail(f"{list_path} returned {r.status_code}: {_fmt_body(r)}")

    if r.status_code in (401, 403, 404, 422) and STRICT:
        pytest.fail(f"{list_path} returned {r.status_code}: {_fmt_body(r)}")

    assert 200 <= r.status_code < 400
