# src/OSSS/tests/users/test_bus_driver.py
from __future__ import annotations

import os
import sys
import json
import inspect
import asyncio
from typing import Iterable, List, Dict, Any, Set, Tuple, Any, Iterator
from pathlib import Path
import pytest
import requests
import logging
from pathlib import PurePosixPath


POSITION_NAME="bus_driver"
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
        _emit_console(f"[INFO] {{msg}}")

def _log_debug(msg: str):
    if LOG_ENABLED and log.isEnabledFor(logging.DEBUG):
        log.debug(msg)
        _emit_console(f"[DEBUG] {{msg}}")

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
                _log_info(f"Loaded RBAC.json from: {{p}}")
                return data
        except Exception as e:
            _log_debug(f"Failed to load RBAC.json from {{p}}: {{e}}")
            continue
    _log_info("RBAC.json not found in any candidate paths; proceeding without RBAC filtering.")
    return None

def _iter_positions(node: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for pos in (node.get("positions") or []):
        yield pos
    for child in (node.get("children") or []):
        yield from _iter_positions(child)

def  _position_permissions_from_rbac() -> Set[str]:
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
                    _log_info(f"permission: {{str(perm)}}")

                    if isinstance(perm, str) and perm.startswith("read:"):
                        tables.add(perm.split(":", 1)[1])

    _log_info(f"RBAC: found {{matches}} " + POSITION_NAME + " position(s); read-perm tables={{len(tables)}}")
    _log_debug(f"RBAC tables: {{sorted(tables)}}")
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

    _log_info(f"OpenAPI: matched {{len(selected)}} list endpoint(s) to RBAC tables")
    _log_debug(f"Matched endpoints: {{selected}}")
    return sorted(selected)

# Precompute at import time
if LIVE_MODE:
    try:
        _SPEC = _fetch_openapi_live()
        _ALL_LIST_PATHS = _discover_list_get_paths(_SPEC) or ["__NO_LIST_ENDPOINTS_FOUND__"]
        _log_info(f"Discovered {{len(_ALL_LIST_PATHS)}} list-style GET endpoint(s) from OpenAPI")
    except Exception as e:
        _ALL_LIST_PATHS = [f"__OPENAPI_FETCH_FAILED__:{{e}}"]
        _log_info(f"Failed to fetch OpenAPI: {{e}}")
else:
    _ALL_LIST_PATHS = ["__LIVE_MODE_DISABLED__"]
    _log_info("Live mode disabled; APP_BASE_URL not set.")

_BOARD_CHAIR_TABLES =  _position_permissions_from_rbac()
if LIVE_MODE and _ALL_LIST_PATHS and not _ALL_LIST_PATHS[0].startswith("__"):
    _MATCHED_LIST_PATHS = _filter_paths_for_tables(_ALL_LIST_PATHS, _BOARD_CHAIR_TABLES)
    if not _MATCHED_LIST_PATHS:
        _MATCHED_LIST_PATHS = ["__NO_MATCHING_ENDPOINTS_FOR_RBAC__"]
        _log_info("No OpenAPI list endpoints match read-permissions from RBAC.json.")
else:
    _MATCHED_LIST_PATHS = _ALL_LIST_PATHS

ALL_CANDIDATES = [
    RBAC_JSON_PATH,
    "../../../RBAC.json",
    "./RBAC.json",
    "/mnt/data/RBAC.json",
]
ALL_DATA = _rbac_load(ALL_CANDIDATES)
LOCAL_RECORDS = collect_position_records(ALL_DATA)
ALL_RECORDS = [r for r in LOCAL_RECORDS if r["name"].lower() == POSITION_NAME]

try:
    ALL_RECORDS  # noqa: F821  # will raise NameError if not defined
except NameError:
    pytest.fail("`records` is not defined")

ALL_PERMISSIONS: Any = extract_read_resources(ALL_RECORDS)

# optional: log / guard
if not ALL_PERMISSIONS:
    pytest.skip("No readable resources found for POSITION_NAME in RBAC.json")

# wrap the whole list so it's passed ONCE (not per element)
_PERMISSIONS_PARAM = [pytest.param(ALL_PERMISSIONS, id=f"rbac-read-{{len(ALL_PERMISSIONS)}}")]


# ---------- RBAC sanity tests (run regardless of live mode) ----------

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
    _log_info(f"RBAC.json top-level keys: {{list(data.keys())}}")

@pytest.mark.rbac
def test_rbac_has_position():
    """Ensure the RBAC hierarchy includes the requested POSITION_NAME."""
    candidates = [
        RBAC_JSON_PATH,
        "../../../RBAC.json",
        "./RBAC.json",
        "/mnt/data/RBAC.json",
    ]
    data = _rbac_load(candidates)
    records = collect_position_records(data)
    records = [r for r in records if r["name"].lower() == POSITION_NAME]
    assert isinstance(records, list) and len(records) >= 1, f"Position {{POSITION_NAME!r}} not found in RBAC.json"

@pytest.mark.rbac
def test_rbac_position_has_read_permissions():
    """Ensure the position has at least one read:* permission."""
    candidates = [
        RBAC_JSON_PATH,
        "../../../RBAC.json",
        "./RBAC.json",
        "/mnt/data/RBAC.json",
    ]
    data = _rbac_load(candidates)
    records = collect_position_records(data)
    records = [r for r in records if r["name"].lower() == POSITION_NAME]
    permissions: Any = extract_read_resources(records)
    assert isinstance(permissions, list) and len(permissions) >= 1, f"Position {{POSITION_NAME!r}} has no read:* permissions"

# ---------- simple live smoke tests ----------

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
async def test_openapi_available(client):
    _log_info("GET /openapi.json")
    r = await _aget(client, _url("/openapi.json"), timeout=8)
    _log_info(f"/openapi.json -> {{r.status_code}}")
    assert r.status_code == 200
    data = r.json()
    assert "paths" in data

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
async def test_me_requires_auth(client):
    _log_info("GET /me (unauthenticated)")
    r = await _aget(client, _url("/me"), timeout=8)
    _log_info(f"/me (unauth) -> {{r.status_code}}")
    assert r.status_code in (401, 403)

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not (LIVE_MODE and REAL_AUTH), reason="Requires live app + real Keycloak auth")
async def test_probe_with_keycloak_auth(client, auth_headers):
    _log_info("GET /_oauth_probe (with Bearer)")
    r = await _aget(client, _url("/_oauth_probe"), headers=auth_headers, timeout=8)
    _log_info(f"/_oauth_probe -> {{r.status_code}}")
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
        pytest.skip("No OpenAPI list endpoints match read-permissions from RBAC.json.")

    try:
        spec = _fetch_openapi_live()
        if list_path not in set(_discover_list_get_paths(spec)):
            pytest.skip(f"{{list_path}} not present in current OpenAPI.")
    except Exception:
        pass

    tail = PurePosixPath(list_path.rstrip("/")).name
    _log_info(f"suffix {{tail}}")
    _log_info(f"permissions: {{permissions}}")

    _log_info(f"GET {{list_path}} (with Bearer)")
    r = await _aget(client, _url(list_path), headers=auth_headers, timeout=12)
    _log_info(f"{{list_path}} -> {{r.status_code}}")

    # RBAC-aware assertion
    if tail in permissions:
        assert r.status_code == 200, (
            f"{{list_path}} -> {{r.status_code}}: {{_fmt_body(r)}} "
            f"(expected 200 because RBAC allows read:{{tail}})"
        )
    else:
        assert r.status_code != 200, (
            f"{{list_path}} -> {{r.status_code}}: {{_fmt_body(r)}} "
            f"(unexpected 200; RBAC does not include read:{{tail}})"
        )
