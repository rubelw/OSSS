# src/OSSS/tests/users/test_board_chair.py
from __future__ import annotations

import os
import inspect
import asyncio
import pytest
import requests

BASE = os.getenv("APP_BASE_URL", "").rstrip("/") or None
LIVE_MODE = bool(BASE)
REAL_AUTH = os.getenv("INTEGRATION_AUTH", "0") == "1"
STRICT = os.getenv("STRICT_ENDPOINTS", "0") == "1"

def _url(path: str) -> str:
    if LIVE_MODE:
        return BASE + path
    return path

async def _aget(client, url: str, **kwargs):
    get_fn = getattr(client, "get")
    if inspect.iscoroutinefunction(get_fn):
        return await get_fn(url, **kwargs)
    return await asyncio.to_thread(get_fn, url, **kwargs)

def _fmt_body(resp) -> str:
    try:
        return str(resp.json())
    except Exception:
        return getattr(resp, "text", "")[:800]

def _fetch_openapi_live() -> dict:
    r = requests.get(BASE + "/openapi.json", timeout=10)
    r.raise_for_status()
    return r.json()

def _discover_list_get_paths(spec: dict) -> list[str]:
    out: list[str] = []
    for path, ops in (spec.get("paths") or {}).items():
        if "{" in path:
            continue
        get_op = (ops or {}).get("get")
        if not get_op:
            continue
        out.append(path)
    return sorted(set(out))

if LIVE_MODE:
    try:
        _SPEC = _fetch_openapi_live()
        LIST_PATHS = _discover_list_get_paths(_SPEC) or ["__NO_LIST_ENDPOINTS_FOUND__"]
    except Exception as e:
        LIST_PATHS = [f"__OPENAPI_FETCH_FAILED__:{e}"]
else:
    LIST_PATHS = ["__LIVE_MODE_DISABLED__"]

# ---------- simple live smoke tests ----------

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
async def test_openapi_available(client):
    r = await _aget(client, _url("/openapi.json"), timeout=8)
    assert r.status_code == 200
    data = r.json()
    assert "paths" in data

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
async def test_me_requires_auth(client):
    r = await _aget(client, _url("/me"), timeout=8)
    assert r.status_code in (401, 403)

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not (LIVE_MODE and REAL_AUTH), reason="Requires live app + real Keycloak auth")
async def test_probe_with_keycloak_auth(client, auth_headers):
    r = await _aget(client, _url("/_oauth_probe"), headers=auth_headers, timeout=8)
    assert r.status_code == 200, getattr(r, "text", "")
    data = r.json()
    assert data.get("ok") is True

# ---------- authenticated list-endpoint sweep ----------

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
@pytest.mark.skipif(not REAL_AUTH, reason="INTEGRATION_AUTH=1 required to iterate endpoints with auth")
@pytest.mark.parametrize("list_path", LIST_PATHS)
async def test_get_list_endpoint(client, list_path, auth_headers):
    # Sentinels
    if list_path == "__LIVE_MODE_DISABLED__":
        pytest.skip("APP_BASE_URL not set (live mode only).")
    if list_path.startswith("__OPENAPI_FETCH_FAILED__"):
        pytest.skip(list_path)
    if list_path == "__NO_LIST_ENDPOINTS_FOUND__":
        pytest.skip("No list-style GET endpoints discovered from OpenAPI.")

    # Ensure still present
    try:
        spec = _fetch_openapi_live()
        if list_path not in set(_discover_list_get_paths(spec)):
            pytest.skip(f"{list_path} not present in current OpenAPI.")
    except Exception:
        pass

    r = await _aget(client, _url(list_path), headers=auth_headers, timeout=12)

    # Hard fail on server errors
    if r.status_code >= 500:
        pytest.fail(f"{list_path} -> {r.status_code}: {_fmt_body(r)}")

    # With auth, some endpoints may still be role-gated. Respect STRICT.
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
