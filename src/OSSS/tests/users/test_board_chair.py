# src/OSSS/tests/users/test_board_chair.py
from __future__ import annotations

import os
import sys
import base64
from datetime import datetime, timezone
import json
import inspect
import asyncio
from typing import Optional, Iterable, List, Dict, Any, Set, Tuple, Any, Iterator
import pytest
import requests
import logging
from pathlib import PurePosixPath

POSITION_NAME = "board_chair"

BASE = os.getenv("APP_BASE_URL", "").rstrip("/") or None
LIVE_MODE = bool(BASE)
REAL_AUTH = os.getenv("INTEGRATION_AUTH", "0") == "1"
STRICT = os.getenv("STRICT_ENDPOINTS", "0") == "1"

RBAC_JSON_PATH = os.getenv("RBAC_JSON_PATH") or os.path.join(
    os.path.dirname(__file__), "../../../RBAC.json"
)

# ----- console logger (stdout + immediate flush) -----
LOG_ENABLED = os.getenv("TEST_LOG", "1") != "0"

def _get_logger() -> logging.Logger:
    logger = logging.getLogger("osss.tests")
    has_stdout_handler = any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout
        for h in logger.handlers
    )
    if not has_stdout_handler:
        handler = logging.StreamHandler(stream=sys.stdout)  # <- stdout
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    level_name = os.getenv("TEST_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    return logger

log = _get_logger()

def _emit_console(line: str):
    try:
        print(line, file=sys.stdout, flush=True)
    except Exception:
        pass

def _log_info(msg: str):
    if LOG_ENABLED:
        log.info(msg)
        _emit_console(f"[INFO] {msg}")

def _log_debug(msg: str):
    if LOG_ENABLED and log.isEnabledFor(logging.DEBUG):
        log.debug(msg)
        _emit_console(f"[DEBUG] {msg}")

def _url(path: str) -> str:
    if LIVE_MODE:
        return BASE + path
    return path

async def _aget(client, url: str, **kwargs):
    get_fn = getattr(client, "get")
    if inspect.iscoroutinefunction(get_fn):
        return await get_fn(url, **kwargs)
    return await asyncio.to_thread(get_fn, url, **kwargs)

async def _apost(client, url: str, **kwargs):
    """
    Async-friendly POST that works with either:
      - httpx.AsyncClient (await client.post)
      - requests.Session (run in a thread via asyncio.to_thread)
    """
    post_fn = getattr(client, "post")
    if inspect.iscoroutinefunction(post_fn):
        return await post_fn(url, **kwargs)
    # requests.Session.post is sync → run in thread
    return await asyncio.to_thread(post_fn, url, **kwargs)

def _fmt_body(resp) -> str:
    try:
        return str(resp.json())
    except Exception:
        return getattr(resp, "text", "")[:800]

# ----------------- Keycloak login/logout helpers -----------------
def _b64url_decode_to_json(seg: str) -> dict:
    try:
        # pad for urlsafe base64
        pad = '=' * (-len(seg) % 4)
        raw = base64.urlsafe_b64decode(seg + pad)
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return {}

def _peek_jwt(token: str) -> tuple[dict, dict]:
    """
    Return (header, payload) without verifying signature.
    Safe for debugging/logging only.
    """
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return ({}, {})
        hdr = _b64url_decode_to_json(parts[0])
        pl  = _b64url_decode_to_json(parts[1])
        return (hdr, pl)
    except Exception:
        return ({}, {})

def _log_token_summary(auth_headers: dict):
    try:
        auth = (auth_headers or {}).get("Authorization", "")
        tok = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else None
        if not tok:
            _log_info("No Bearer token in auth_headers")
            return

        hdr, pl = _peek_jwt(tok)
        now = datetime.now(timezone.utc)
        iss_env = os.getenv("OIDC_ISSUER") or os.getenv("KEYCLOAK_ISSUER")
        aud_env = os.getenv("OIDC_CLIENT_ID") or os.getenv("KEYCLOAK_CLIENT_ID") or "osss-api"

        exp_ts: Optional[int] = pl.get("exp")
        nbf_ts: Optional[int] = pl.get("nbf")
        exp_s, nbf_s, ttl_s = None, None, None
        if isinstance(exp_ts, int):
            exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
            exp_s = exp_dt.isoformat()
            ttl_s = f"{int((exp_dt - now).total_seconds())}s"
        if isinstance(nbf_ts, int):
            nbf_dt = datetime.fromtimestamp(nbf_ts, tz=timezone.utc)
            nbf_s = nbf_dt.isoformat()

        realm_roles = (pl.get("realm_access") or {}).get("roles") or []
        client_roles = []
        ra = pl.get("resource_access") or {}
        for client, obj in ra.items():
            roles = (obj or {}).get("roles") or []
            for r in roles:
                client_roles.append(f"{client}:{r}")

        _log_info(
            "JWT header: alg={alg} kid={kid}".format(
                alg=hdr.get("alg"), kid=hdr.get("kid")
            )
        )
        _log_info(
            "JWT payload: iss={iss} aud={aud} azp={azp} sub={sub} preferred_username={u}".format(
                iss=pl.get("iss"), aud=pl.get("aud"), azp=pl.get("azp"),
                sub=pl.get("sub"), u=pl.get("preferred_username")
            )
        )
        _log_info(
            "JWT times: iat={iat} nbf={nbf}({nbf_s}) exp={exp}({exp_s}) ttl={ttl}".format(
                iat=pl.get("iat"), nbf=nbf_ts, nbf_s=nbf_s, exp=exp_ts, exp_s=exp_s, ttl=ttl_s
            )
        )
        if realm_roles:
            _log_info(f"JWT realm roles: {sorted(set(realm_roles))[:10]}{' …' if len(realm_roles)>10 else ''}")
        if client_roles:
            _log_info(f"JWT client roles: {sorted(set(client_roles))[:10]}{' …' if len(client_roles)>10 else ''}")

        if iss_env and pl.get("iss") != iss_env:
            _log_info(f"[mismatch] ENV issuer={iss_env} but token.iss={pl.get('iss')}")
        # aud can be str or list
        aud_tok = pl.get("aud")
        aud_ok = (aud_tok == aud_env) or (isinstance(aud_tok, list) and aud_env in aud_tok)
        if aud_env and not aud_ok:
            _log_info(f"[mismatch] ENV client_id={aud_env} not in token.aud={aud_tok}")
    except Exception as e:
        _log_debug(f"_log_token_summary failed: {e}")

def _log_response_diagnostics(resp):
    try:
        hdrs = getattr(resp, "headers", {}) or {}
        interesting = {
            "date": hdrs.get("date"),
            "content-type": hdrs.get("content-type"),
            "www-authenticate": hdrs.get("www-authenticate"),
            "vary": hdrs.get("vary"),
            "cache-control": hdrs.get("cache-control"),
            "server": hdrs.get("server"),
            "x-request-id": hdrs.get("x-request-id") or hdrs.get("x-correlation-id"),
        }
        _log_info(f"Response headers(min): { {k:v for k,v in interesting.items() if v} }")
        body = _fmt_body(resp)
        if body:
            snip = body if len(body) <= 600 else (body[:600] + " …(truncated)")
            _log_info(f"Response body: {snip}")
    except Exception as e:
        _log_debug(f"_log_response_diagnostics failed: {e}")

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
    v = os.getenv("KEYCLOAK_CLIENT_SECRET") or os.getenv("OIDC_CLIENT_SECRET")
    if v and v.strip().lower() not in {"changeme", "<real-secret>", "replace_me"}:
        return v
    return None

def _token_endpoint(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/protocol/openid-connect/token"

def _revoke_endpoint(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/protocol/openid-connect/revoke"

def _logout_endpoint(issuer: str) -> str:
    return f"{issuer.rstrip('/')}/protocol/openid-connect/logout"

def _basic_auth_header(client_id: str, client_secret: str) -> dict:
    import base64
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}

def _login_password_grant(username: str, password: str) -> tuple[str, str | None]:
    """
    Returns (access_token, refresh_token_or_None). Raises AssertionError on failure.
    """
    issuer = _issuer()
    if not issuer:
        pytest.skip("Issuer not configured; set KEYCLOAK_BASE_URL/KEYCLOAK_REALM or KEYCLOAK_ISSUER.")

    client_id = _client_id()
    client_secret = _client_secret()
    if not client_secret:
        pytest.skip("KEYCLOAK_CLIENT_SECRET/OIDC_CLIENT_SECRET not set (confidential client required).")

    url = _token_endpoint(issuer)
    common = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "scope": "openid",
    }

    # Try client_secret_basic
    headers = _basic_auth_header(client_id, client_secret)
    r = requests.post(url, data=common, headers=headers, timeout=15)
    if r.status_code == 200:
        j = r.json()
        return j.get("access_token"), j.get("refresh_token")

    # Fallback to client_secret_post
    data_post = dict(common, client_id=client_id, client_secret=client_secret)
    r2 = requests.post(url, data=data_post, timeout=15)
    if r2.status_code == 200:
        j = r2.json()
        return j.get("access_token"), j.get("refresh_token")

    def _fmt(r):
        ct = r.headers.get("content-type", "")
        return r.text if "json" not in ct else json.dumps(r.json(), indent=2)

    raise AssertionError(
        "[Keycloak] Token request failed.\n"
        f"  URL: {url}\n"
        f"  Attempt 1 (Basic) status: {r.status_code} body: {_fmt(r)[:600]}\n"
        f"  Attempt 2 (Post)  status: {r2.status_code} body: {_fmt(r2)[:600]}"
    )

def _logout_keycloak(refresh_token: str | None):
    issuer = _issuer()
    if not issuer or not refresh_token:
        return

    client_id = _client_id()
    client_secret = _client_secret()
    if not client_secret:
        return

    # Try revoke endpoint
    try:
        r = requests.post(
            _revoke_endpoint(issuer),
            data={"token": refresh_token, "token_type_hint": "refresh_token"},
            headers=_basic_auth_header(client_id, client_secret),
            timeout=10,
        )
        _log_info(f"Keycloak revoke: HTTP {r.status_code}")
        if r.status_code in (200, 201, 204):
            return
    except Exception as e:
        _log_debug(f"Keycloak revoke failed: {e}")

    # Try logout endpoint
    try:
        r2 = requests.post(
            _logout_endpoint(issuer),
            data={"refresh_token": refresh_token, "client_id": client_id, "client_secret": client_secret},
            timeout=10,
        )
        _log_info(f"Keycloak logout: HTTP {r2.status_code}")
    except Exception as e:
        _log_debug(f"Keycloak logout failed: {e}")

def _try_app_logout(access_token: str | None):
    if not (LIVE_MODE and access_token):
        return
    for p in ("/auth/logout", "/logout", "/api/logout"):
        try:
            r = requests.post(
                BASE + p,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=6,
            )
            _log_info(f"App logout {p}: HTTP {r.status_code}")
            if r.status_code in (200, 204):
                return
        except Exception as e:
            _log_debug(f"App logout {p} failed: {e}")

# Provide a module-local fixture that logs in before tests and logs out afterward.
@pytest.fixture(scope="module")
def auth_headers():
    """
    Overrides any conftest-provided `auth_headers` so this file
    always logs in and logs out once per module.
    """
    if not LIVE_MODE or not REAL_AUTH:
        pytest.skip("Live auth disabled; requires APP_BASE_URL and INTEGRATION_AUTH=1.")

    # Username / password for this role (env may override)
    username = os.getenv("OSSS_TEST_USER") or f"{POSITION_NAME}@osss.local"
    password = os.getenv("OSSS_TEST_PASS") or "password"

    _log_info(f"Logging in as {username} for {POSITION_NAME}")
    access_token, refresh_token = _login_password_grant(username, password)
    if not access_token:
        pytest.fail("Login returned no access token")

    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    try:
        yield headers
    finally:
        _log_info("Logging out (revoking/ending session)")
        _try_app_logout(access_token)
        _logout_keycloak(refresh_token)


# ----------------- RBAC helpers -----------------

def _normalize_permissions(perms: Any) -> List[str]:
    out: List[str] = []
    if isinstance(perms, list):
        for p in perms:
            if isinstance(p, str):
                p = p.strip()
                if p:
                    out.append(p)
    return out

def iter_position_records(node: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    for pos in (node.get("positions") or []):
        if isinstance(pos, dict):
            name = pos.get("name")
            if isinstance(name, str) and name.strip():
                yield {
                    "name": name.strip(),
                    "permissions": _normalize_permissions(pos.get("permissions")),
                }
    for child in (node.get("children") or []):
        if isinstance(child, dict):
            yield from iter_position_records(child)

def collect_position_records(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    hierarchy = data.get("hierarchy")
    if not isinstance(hierarchy, list):
        return records
    for unit in hierarchy:
        if isinstance(unit, dict):
            records.extend(iter_position_records(unit))
    return records

def extract_read_resources(records: List[Dict[str, Any]]) -> List[str]:
    """Collect unique resource names from permissions starting with 'read:'."""
    seen = set()
    out: List[str] = []
    for rec in records:
        for perm in rec.get("permissions") or []:
            perm = perm.strip()
            if perm.startswith("read:"):
                parts = perm.split(":", 1)
                if len(parts) == 2:
                    resource = parts[1].strip()
                    if resource and resource not in seen:
                        seen.add(resource)
                        out.append(resource)
    out.sort()
    return out

def _rbac_load(path_candidates: Iterable[str]) -> Dict[str, Any] | None:
    for p in path_candidates:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                _log_info(f"Loaded RBAC.json from: {p}")
                return data
        except Exception as e:
            _log_debug(f"Failed to load RBAC.json from {p}: {e}")
            continue
    _log_info("RBAC.json not found in any candidate paths; proceeding without RBAC filtering.")
    return None

def _iter_positions(node: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for pos in (node.get("positions") or []):
        yield pos
    for child in (node.get("children") or []):
        yield from _iter_positions(child)

def _position_permissions_from_rbac() -> Set[str]:
    candidates = [
        RBAC_JSON_PATH,
        "../../../RBAC.json",
        "./RBAC.json",
        "/mnt/data/RBAC.json",  # tool-upload fallback
    ]
    data = _rbac_load(candidates)
    if not data:
        return set()

    tables: Set[str] = set()
    matches = 0
    for unit in (data.get("hierarchy") or []):
        for pos in _iter_positions(unit):
            name = (pos.get("name") or "").strip().lower()
            if name in {POSITION_NAME}:
                matches += 1
                for perm in (pos.get("permissions") or []):
                    _log_debug(f"permission: {str(perm)}")
                    if isinstance(perm, str) and perm.startswith("read:"):
                        tables.add(perm.split(":", 1)[1])

    _log_info(f"RBAC: found {matches} {POSITION_NAME} position(s); read-perm tables={len(tables)}")
    _log_debug(f"RBAC tables: {sorted(tables)}")
    return tables

# ----------------- OpenAPI discovery -----------------

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

def _last_segment(path: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p]
    return parts[-1] if parts else ""

def _score_path_for_name(path: str) -> Tuple[int, int]:
    parts = [p for p in path.strip("/").split("/") if p]
    prefix = parts[0] if parts else ""
    if prefix == "api":
        pref = 0
    elif prefix == "v1":
        pref = 1
    else:
        pref = 2
    return (pref, len(parts))

def _filter_paths_for_tables(list_paths: List[str], tables: Set[str]) -> List[str]:
    by_table: Dict[str, List[str]] = {}
    for p in list_paths:
        tail = _last_segment(p)
        if tail in tables:
            by_table.setdefault(tail, []).append(p)

    selected: List[str] = []
    for tail, paths in by_table.items():
        paths = sorted(paths, key=_score_path_for_name)
        selected.append(paths[0])

    _log_info(f"OpenAPI: matched {len(selected)} list endpoint(s) to RBAC tables")
    _log_debug(f"Matched endpoints: {selected}")
    return sorted(selected)

# Precompute at import time
if LIVE_MODE:
    try:
        _SPEC = _fetch_openapi_live()
        _ALL_LIST_PATHS = _discover_list_get_paths(_SPEC) or ["__NO_LIST_ENDPOINTS_FOUND__"]
        _log_info(f"Discovered {len(_ALL_LIST_PATHS)} list-style GET endpoint(s) from OpenAPI")
    except Exception as e:
        _ALL_LIST_PATHS = [f"__OPENAPI_FETCH_FAILED__:{e}"]
        _log_info(f"Failed to fetch OpenAPI: {e}")
else:
    _ALL_LIST_PATHS = ["__LIVE_MODE_DISABLED__"]
    _log_info("Live mode disabled; APP_BASE_URL not set.")

_SELECTED_TABLES = _position_permissions_from_rbac()
if LIVE_MODE and _ALL_LIST_PATHS and not _ALL_LIST_PATHS[0].startswith("__"):
    _MATCHED_LIST_PATHS = _filter_paths_for_tables(_ALL_LIST_PATHS, _SELECTED_TABLES)
    if not _MATCHED_LIST_PATHS:
        _MATCHED_LIST_PATHS = ["__NO_MATCHING_ENDPOINTS_FOR_RBAC__"]
        _log_info(f"No OpenAPI list endpoints match {POSITION_NAME} read-permissions from RBAC.json.")
else:
    _MATCHED_LIST_PATHS = _ALL_LIST_PATHS

ALL_CANDIDATES = [
    RBAC_JSON_PATH,
    "../../../RBAC.json",
    "./RBAC.json",
    "/mnt/data/RBAC.json",
]
ALL_DATA = _rbac_load(ALL_CANDIDATES)
LOCAL_RECORDS = collect_position_records(ALL_DATA) if ALL_DATA else []
ALL_RECORDS = [r for r in LOCAL_RECORDS if r["name"].lower() == POSITION_NAME]

try:
    ALL_RECORDS  # noqa: F821  # will raise NameError if not defined
except NameError:
    pytest.fail("`records` is not defined")

ALL_PERMISSIONS: Any = extract_read_resources(ALL_RECORDS)

# optional: log / guard
if not ALL_PERMISSIONS:
    pytest.skip("No readable resources found for POSITION_NAME in RBAC.json", allow_module_level=True)

# wrap the whole list so it's passed ONCE (not per element)
_PERMISSIONS_PARAM = [pytest.param(ALL_PERMISSIONS, id=f"rbac-read-{len(ALL_PERMISSIONS)}")]

# ---------- RBAC sanity tests ----------

@pytest.mark.rbac
def test_rbac_file_can_be_read():
    """Verify we can locate and load RBAC.json from known paths."""
    candidates = [
        RBAC_JSON_PATH,
        "../../../RBAC.json",
        "./RBAC.json",
        "/mnt/data/RBAC.json",
    ]
    data = _rbac_load(candidates)
    if not data:
        pytest.skip("RBAC.json not found in any known path; set RBAC_JSON_PATH or place the file.")
    assert isinstance(data, dict) and data, "RBAC.json loaded but appears empty"
    _log_info(f"RBAC.json top-level keys: {list(data.keys())}")

@pytest.mark.rbac
def test_rbac_has_board_chair_position():
    data = _rbac_load([RBAC_JSON_PATH, "../../../RBAC.json", "./RBAC.json", "/mnt/data/RBAC.json"])
    records = collect_position_records(data) if data else []
    records = [r for r in records if r["name"].lower() == POSITION_NAME]
    _log_info(f"records: {records}")
    assert isinstance(records, list) and len(records) >= 1, "`records` is an empty list (expected at least 1 item)"

@pytest.mark.rbac
def test_rbac_permissions_nonempty_for_position():
    data = _rbac_load([RBAC_JSON_PATH, "../../../RBAC.json", "./RBAC.json", "/mnt/data/RBAC.json"])
    records = collect_position_records(data) if data else []
    records = [r for r in records if r["name"].lower() == POSITION_NAME]
    permissions: Any = extract_read_resources(records)
    _log_info(f"permissions: {permissions}")
    assert isinstance(permissions, list) and len(permissions) >= 1, "`permissions` is empty"

# ---------- simple live smoke tests ----------

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
async def test_openapi_available(client):
    _log_info("GET /openapi.json")
    r = await _aget(client, _url("/openapi.json"), timeout=8)
    _log_info(f"/openapi.json -> {r.status_code}")
    assert r.status_code == 200
    data = r.json()
    assert "paths" in data

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
async def test_me_requires_auth(client):
    _log_info("GET /me (unauthenticated)")
    r = await _aget(client, _url("/me"), timeout=8)
    _log_info(f"/me (unauth) -> {r.status_code}")
    assert r.status_code in (401, 403)

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not (LIVE_MODE and REAL_AUTH), reason="Requires live app + real Keycloak auth")
async def test_probe_with_keycloak_auth(client, auth_headers):
    _log_info("GET /_oauth_probe (with Bearer)")
    r = await _aget(client, _url("/_oauth_probe"), headers=auth_headers, timeout=8)
    _log_info(f"/_oauth_probe -> {r.status_code}")
    assert r.status_code == 200, getattr(r, "text", "")
    data = r.json()
    assert data.get("ok") is True

# ---------- authenticated list-endpoint sweep (RBAC) ----------

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
@pytest.mark.skipif(not REAL_AUTH, reason="INTEGRATION_AUTH=1 required to iterate endpoints with auth")
@pytest.mark.parametrize("list_path", _MATCHED_LIST_PATHS)
@pytest.mark.parametrize("permissions", _PERMISSIONS_PARAM)
async def test_get_list_endpoint(client, permissions, list_path, auth_headers):
    if list_path == "__LIVE_MODE_DISABLED__":
        pytest.skip("APP_BASE_URL not set (live mode only).")
    if list_path.startswith("__OPENAPI_FETCH_FAILED__"):
        pytest.skip(list_path)
    if list_path == "__NO_LIST_ENDPOINTS_FOUND__":
        pytest.skip("No list-style GET endpoints discovered from OpenAPI.")
    if list_path == "__NO_MATCHING_ENDPOINTS_FOR_RBAC__":
        pytest.skip(f"No OpenAPI list endpoints match {POSITION_NAME} read-permissions from RBAC.json.")

    try:
        spec = _fetch_openapi_live()
        if list_path not in set(_discover_list_get_paths(spec)):
            pytest.skip(f"{list_path} not present in current OpenAPI.")
    except Exception:
        pass

    tail = PurePosixPath(list_path.rstrip("/")).name
    _log_info(f"suffix {tail}")
    _log_info(f"permissions: {permissions}")

    # NEW: log token + env sanity, and full URL
    _log_token_summary(auth_headers)
    full_url = _url(list_path)
    _log_info(f"Resolved URL: {full_url}")

    _log_info(f"GET {list_path} (with Bearer)")
    r = await _aget(client, full_url, headers=auth_headers, timeout=12)
    _log_info(f"{list_path} -> {r.status_code}")

    # NEW: log response headers/body on failures or non-200
    if r.status_code != 200:
        _log_response_diagnostics(r)

    if tail in permissions:
        # Allowed by RBAC → should succeed
        assert r.status_code == 200, (
            f"{list_path} -> {r.status_code}: {_fmt_body(r)} "
            f"(expected 200 because RBAC allows read:{tail})"
        )
    else:
        # Not in RBAC → a 200 is always unexpected (STRICT or not)
        assert r.status_code != 200, (
            f"{list_path} -> {r.status_code}: {_fmt_body(r)} "
            f"(unexpected 200; RBAC does not include read:{tail})"
        )

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not (LIVE_MODE and REAL_AUTH), reason="Requires live app + real Keycloak auth")
async def test_create_organization(client, auth_headers):
    """
    Create an Organization named 'test' via /api/organizations using OrganizationCreate schema.
    Accept 200/201 for success. If it already exists and your API returns 409, treat that as ok.
    """
    payload = {
        "name": "test",
        # "code": None,  # include only if your API allows/ignores explicit null
    }

    url = _url("/api/organizations")
    r = await _apost(client, url, json=payload, headers=auth_headers, timeout=12)

    # Server errors should give a clear message (string!)
    if r.status_code >= 500:
        pytest.fail(f"POST {url} -> {r.status_code}. Body={_fmt_body(r)}")

    # Success cases (your API may return 200 or 201 on create)
    if r.status_code in (200, 201):
        try:
            body = r.json()
        except Exception:
            pytest.fail(f"POST {url} returned non-JSON success. Text={getattr(r, 'text', '')[:800]}")
        assert isinstance(body, dict), f"Expected JSON object, got: {body!r}"
        assert body.get("name") == "test", f"Unexpected name in response: {body}"
        # optional: check id/timestamps if present
        return

    # Already exists? Many APIs return 409 for duplicate unique fields.
    if r.status_code == 409:
        # You can assert on response body if it helps:
        _ = _fmt_body(r)
        # treat as acceptable outcome for idempotent test runs
        return

    # Any other non-2xx is unexpected here
    pytest.fail(f"POST {url} unexpected status {r.status_code}. Body={_fmt_body(r)}")