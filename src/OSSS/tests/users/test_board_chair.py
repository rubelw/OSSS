from __future__ import annotations

import os
import sys
import json
import inspect
import asyncio
import uuid
from typing import Iterable, List, Dict, Any, Set, Tuple, Iterator, Optional
from pathlib import PurePosixPath
import logging
import pytest

# ----------------- Config / env -----------------

POSITION_NAME = os.getenv("POSITION_NAME", "board_chair")
BASE = os.getenv("APP_BASE_URL", "").rstrip("/") or None
LIVE_MODE = bool(BASE)
REAL_AUTH = os.getenv("INTEGRATION_AUTH", "0") == "1"
STRICT = os.getenv("STRICT_ENDPOINTS", "0") == "1"

RBAC_JSON_PATH = os.getenv("RBAC_JSON_PATH") or os.path.join(
    os.path.dirname(__file__), "../../../RBAC.json"
)

# ----------------- Logging to stdout -----------------

def _get_logger() -> logging.Logger:
    logger = logging.getLogger("osss.tests.auto")
    # Ensure a stdout handler exists
    if not any(isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stdout for h in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False
    level_name = os.getenv("TEST_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    return logger

log = _get_logger()

def _log_info(msg: str):
    log.info(msg)

def _log_debug(msg: str):
    log.debug(msg)

# ----------------- HTTP helpers (sync/async friendly) -----------------

def _url(path: str) -> str:
    if LIVE_MODE:
        return BASE + path
    return path

async def _arequest(client, method: str, url: str, **kwargs):
    fn = getattr(client, method.lower())
    if inspect.iscoroutinefunction(fn):
        return await fn(url, **kwargs)
    # requests.Session.* are sync → run in thread
    return await asyncio.to_thread(fn, url, **kwargs)

async def _aget(client, url: str, **kwargs):
    return await _arequest(client, "get", url, **kwargs)

async def _apost(client, url: str, **kwargs):
    return await _arequest(client, "post", url, **kwargs)

async def _aput(client, url: str, **kwargs):
    return await _arequest(client, "put", url, **kwargs)

async def _apatch(client, url: str, **kwargs):
    return await _arequest(client, "patch", url, **kwargs)

async def _adelete(client, url: str, **kwargs):
    return await _arequest(client, "delete", url, **kwargs)

def _fmt_body(resp) -> str:
    try:
        return json.dumps(resp.json(), indent=2)[:1000]
    except Exception:
        return getattr(resp, "text", "")[:1000]

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

def extract_resources_with_prefix(records: List[Dict[str, Any]], prefix: str) -> List[str]:
    """Collect unique resource names from permissions starting with 'prefix:'."""
    seen = set()
    out: List[str] = []
    for rec in records:
        for perm in rec.get("permissions") or []:
            perm = perm.strip()
            if perm.startswith(prefix + ":"):
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

# ----------------- OpenAPI discovery -----------------

def _fetch_openapi_live() -> dict:
    import requests  # local import to keep import-time side-effects down
    r = requests.get(BASE + "/openapi.json", timeout=12)
    r.raise_for_status()
    return r.json()

def _discover_list_get_paths(spec: dict) -> list[str]:
    out: list[str] = []
    for path, ops in (spec.get("paths") or {}).items():
        if not isinstance(ops, dict):
            continue
        if "{" in path:  # skip item endpoints; this suite focuses on collection GETs
            continue
        get_op = ops.get("get")
        if get_op:
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

# ----------------- RequestBody samplers -----------------

def _sample_from_schema(schema: Dict[str, Any]) -> Any:
    if not isinstance(schema, dict):
        return None
    t = schema.get("type")
    fmt = schema.get("format")

    if "$ref" in schema:
        # Resolve very shallow refs if provided in components
        ref = schema["$ref"]
        return {"$ref": ref}  # best-effort: server will likely 422; we'll xfail on validation

    if t == "object":
        props = schema.get("properties") or {}
        required = schema.get("required") or []
        out = {}
        for name in required:
            sub = props.get(name) or {}
            out[name] = _sample_from_schema(sub)
        return out

    if t == "array":
        items = schema.get("items") or {}
        # minimal: empty array; if required, server may 422 and we xfail
        return []

    if t == "string":
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        if fmt in ("date-time", "datetime"):
            return "1970-01-01T00:00:00Z"
        if fmt == "date":
            return "1970-01-01"
        return "test"

    if t == "integer":
        return 0
    if t == "number":
        return 0
    if t == "boolean":
        return True

    return None

def _build_minimal_payload_for_method(spec: dict, path: str, method: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], str]]:
    """
    Returns (payload, files, content_type) for the given method,
    or None if no requestBody is defined.
    Supports JSON, x-www-form-urlencoded, multipart/form-data (best-effort).
    """
    path_item = (spec.get("paths") or {}).get(path) or {}
    op = path_item.get(method.lower())
    if not isinstance(op, dict):
        return None
    rb = op.get("requestBody")
    if not isinstance(rb, dict):
        return None

    content = rb.get("content") or {}
    # Preference order
    media_types = [
        "application/json",
        "application/x-www-form-urlencoded",
        "multipart/form-data",
    ]
    for mt in media_types:
        mt_obj = content.get(mt)
        if not mt_obj:
            continue
        schema = (mt_obj.get("schema") or {})
        payload = {}
        files = {}
        if mt == "application/json":
            payload = _sample_from_schema(schema) or {}
        elif mt == "application/x-www-form-urlencoded":
            sample = _sample_from_schema(schema) or {}
            # Coerce non-primitive to json string for form encoding
            if isinstance(sample, dict):
                payload = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in sample.items()}
            else:
                payload = {}
        elif mt == "multipart/form-data":
            sample = _sample_from_schema(schema) or {}
            if isinstance(sample, dict):
                # very light heuristic: put any field that looks like file into files
                for k, v in sample.items():
                    if "file" in k.lower():
                        files[k] = ("dummy.txt", b"dummy", "text/plain")
                    else:
                        payload[k] = v if isinstance(v, (str, int, float)) else json.dumps(v)
            else:
                files["file"] = ("dummy.txt", b"dummy", "text/plain")
        return payload or {}, files or {}, mt

    return None

# ----------------- Precompute from RBAC & OpenAPI -----------------

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

ALL_CANDIDATES = [
    RBAC_JSON_PATH,
    "../../../RBAC.json",
    "./RBAC.json",
    "/mnt/data/RBAC.json",
]
ALL_DATA = _rbac_load(ALL_CANDIDATES) or {}
LOCAL_RECORDS = collect_position_records(ALL_DATA)
ALL_RECORDS = [r for r in LOCAL_RECORDS if r.get("name", "").lower() == POSITION_NAME]

READ_RESOURCES: List[str] = extract_resources_with_prefix(ALL_RECORDS, "read")
MANAGE_RESOURCES: List[str] = extract_resources_with_prefix(ALL_RECORDS, "manage")

READ_SET: Set[str] = set(READ_RESOURCES)
MANAGE_SET: Set[str] = set(MANAGE_RESOURCES)

# Use RBAC to filter list endpoints
if LIVE_MODE and _ALL_LIST_PATHS and not _ALL_LIST_PATHS[0].startswith("__"):
    _MATCHED_LIST_PATHS = _filter_paths_for_tables(_ALL_LIST_PATHS, READ_SET or set())
    if not _MATCHED_LIST_PATHS:
        _MATCHED_LIST_PATHS = ["__NO_MATCHING_ENDPOINTS_FOR_RBAC__"]
        _log_info(f"No OpenAPI list endpoints match {POSITION_NAME} read-permissions from RBAC.json.")
else:
    _MATCHED_LIST_PATHS = _ALL_LIST_PATHS

# Bundle permissions for parametrization
_PERMS_PARAM = [pytest.param({"read": READ_SET, "manage": MANAGE_SET},
                             id=f"rbac-read{len(READ_SET)}-manage{len(MANAGE_SET)}")]

# ----------------- Sanity tests for RBAC -----------------

@pytest.mark.rbac
def test_rbac_file_can_be_read():
    if not ALL_DATA:
        pytest.skip("RBAC.json not found in any known path; set RBAC_JSON_PATH or place the file.")
    assert isinstance(ALL_DATA, dict) and ALL_DATA, "RBAC.json loaded but appears empty"
    _log_info(f"RBAC.json top-level keys: {list(ALL_DATA.keys())}")

@pytest.mark.rbac
def test_rbac_has_position_name():
    recs = [r for r in LOCAL_RECORDS if r.get("name", "").lower() == POSITION_NAME]
    assert isinstance(recs, list) and len(recs) >= 1, f"Position {POSITION_NAME!r} not found in RBAC"

@pytest.mark.rbac
def test_rbac_permissions_nonempty():
    # At least one read or manage permission present
    assert (len(READ_SET) + len(MANAGE_SET)) >= 1, f"No read/manage permissions for {POSITION_NAME}"

# ----------------- Simple live smoke tests -----------------

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
async def test_openapi_available(client):
    _log_info("GET /openapi.json")
    r = await _aget(client, _url("/openapi.json"), timeout=10)
    _log_info(f"/openapi.json -> {r.status_code}")
    assert r.status_code == 200
    assert "paths" in r.json()

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
async def test_me_requires_auth(client):
    _log_info("GET /me (unauthenticated)")
    r = await _aget(client, _url("/me"), timeout=10)
    _log_info(f"/me (unauth) -> {r.status_code}")
    assert r.status_code in (401, 403)

# ----------------- Endpoint tests driven by RBAC + OpenAPI -----------------

@pytest.mark.anyio("asyncio")
@pytest.mark.integration
@pytest.mark.skipif(not LIVE_MODE, reason="APP_BASE_URL not set (live mode only)")
@pytest.mark.skipif(not REAL_AUTH, reason="INTEGRATION_AUTH=1 required to iterate endpoints with auth")
@pytest.mark.parametrize("list_path", _MATCHED_LIST_PATHS)
@pytest.mark.parametrize("perms", _PERMS_PARAM)
async def test_endpoints(client, perms, list_path, auth_headers):
    if list_path == "__LIVE_MODE_DISABLED__":
        pytest.skip("APP_BASE_URL not set (live mode only).")
    if list_path.startswith("__OPENAPI_FETCH_FAILED__"):
        pytest.skip(list_path)
    if list_path == "__NO_LIST_ENDPOINTS_FOUND__":
        pytest.skip("No list-style GET endpoints discovered from OpenAPI.")
    if list_path == "__NO_MATCHING_ENDPOINTS_FOR_RBAC__":
        pytest.skip(f"No OpenAPI list endpoints match {POSITION_NAME} read-permissions from RBAC.json.")

    try:
        spec = _SPEC if LIVE_MODE else {}
        if list_path not in set(_discover_list_get_paths(spec)):
            pytest.skip(f"{list_path} not present in current OpenAPI.")
    except Exception:
        pass

    tail = PurePosixPath(list_path.rstrip("/")).name
    read_allowed = tail in perms["read"]
    manage_allowed = tail in perms["manage"]

    # ---- GET (list) ----
    _log_info(f"GET {list_path} (with Bearer)")
    r = await _aget(client, _url(list_path), headers=auth_headers, timeout=12)
    _log_info(f"{list_path} -> {r.status_code}")

    if r.status_code >= 500:
        pytest.fail(f"{list_path} -> {r.status_code}: {_fmt_body(r)}")

    if read_allowed or manage_allowed:
        assert r.status_code == 200, (
            f"{list_path} -> {r.status_code}: {_fmt_body(r)} "
            f"(expected 200 because RBAC allows read:{tail})"
        )
    else:
        if STRICT:
            assert r.status_code != 200, (
                f"{list_path} unexpectedly returned 200; RBAC does not include read:{tail}"
            )

    # ---- Write verbs on collection (best-effort) ----
    # POST
    post_data = _build_minimal_payload_for_method(_SPEC, list_path, "post")
    if post_data is not None:
        payload, files, ct = post_data
        headers = dict(auth_headers)
        kwargs = {}
        if ct == "application/json":
            kwargs = {"json": payload}
        elif ct == "application/x-www-form-urlencoded":
            kwargs = {"data": payload}
        elif ct == "multipart/form-data":
            kwargs = {"data": payload, "files": files}
        else:
            kwargs = {"json": payload}
            ct = "application/json"
        if ct in {"application/json", "application/x-www-form-urlencoded"}:
            headers["Content-Type"] = ct

        _log_info(f"POST {list_path} using {ct} payload={payload!r} files={list(files.keys())}")
        resp = await _apost(client, _url(list_path), headers=headers, timeout=12, **kwargs)
        code = resp.status_code
        _log_info(f"POST {list_path} -> {code}")

        if code in (400, 422):
            pytest.xfail(f"POST {list_path} returned {code} (validation) before RBAC; cannot assert. Body={_fmt_body(resp)}")

        if manage_allowed:
            assert 200 <= code < 300, (
                f"{list_path} -> {code}: {_fmt_body(resp)} "
                f"(expected 2xx because RBAC includes manage:{tail})"
            )
        else:
            assert code != 200, (
                f"{list_path} unexpectedly returned 200; RBAC does not include manage:{tail}"
            )

    # PUT
    put_data = _build_minimal_payload_for_method(_SPEC, list_path, "put")
    if put_data is not None:
        payload, files, ct = put_data
        headers = dict(auth_headers)
        if ct in {"application/json", "application/x-www-form-urlencoded"}:
            headers["Content-Type"] = ct
        if ct == "application/json":
            kwargs = {"json": payload}
        elif ct == "application/x-www-form-urlencoded":
            kwargs = {"data": payload}
        elif ct == "multipart/form-data":
            kwargs = {"data": payload, "files": files}
        else:
            kwargs = {"json": payload}
        _log_info(f"PUT {list_path} using {ct} payload={payload!r} files={list(files.keys())}")
        resp = await _aput(client, _url(list_path), headers=headers, timeout=12, **kwargs)
        code = resp.status_code
        _log_info(f"PUT {list_path} -> {code}")

        if code in (400, 422):
            pytest.xfail(f"PUT {list_path} returned {code} (validation) before RBAC; cannot assert. Body={_fmt_body(resp)}")

        if manage_allowed:
            assert 200 <= code < 300, (
                f"{list_path} -> {code}: {_fmt_body(resp)} "
                f"(expected 2xx because RBAC includes manage:{tail})"
            )
        else:
            assert code != 200, (
                f"{list_path} unexpectedly returned 200; RBAC does not include manage:{tail}"
            )

    # PATCH
    patch_data = _build_minimal_payload_for_method(_SPEC, list_path, "patch")
    if patch_data is not None:
        payload, files, ct = patch_data
        headers = dict(auth_headers)
        if ct in {"application/json", "application/x-www-form-urlencoded"}:
            headers["Content-Type"] = ct
        if ct == "application/json":
            kwargs = {"json": payload}
        elif ct == "application/x-www-form-urlencoded":
            kwargs = {"data": payload}
        elif ct == "multipart/form-data":
            kwargs = {"data": payload, "files": files}
        else:
            kwargs = {"json": payload}
        _log_info(f"PATCH {list_path} using {ct} payload={payload!r} files={list(files.keys())}")
        resp = await _apatch(client, _url(list_path), headers=headers, timeout=12, **kwargs)
        code = resp.status_code
        _log_info(f"PATCH {list_path} -> {code}")

        if code in (400, 422):
            pytest.xfail(f"PATCH {list_path} returned {code} (validation) before RBAC; cannot assert. Body={_fmt_body(resp)}")

        if manage_allowed:
            assert 200 <= code < 300, (
                f"{list_path} -> {code}: {_fmt_body(resp)} "
                f"(expected 2xx because RBAC includes manage:{tail})"
            )
        else:
            assert code != 200, (
                f"{list_path} unexpectedly returned 200; RBAC does not include manage:{tail}"
            )

    # DELETE (collection-level; if defined)
    path_item = (_SPEC.get("paths") or {}).get(list_path) or {}
    if "delete" in path_item:
        _log_info(f"DELETE {list_path}")
        resp = await _adelete(client, _url(list_path), headers=auth_headers, timeout=12)
        code = resp.status_code
        _log_info(f"DELETE {list_path} -> {code}")

        if code in (400, 422):
            pytest.xfail(f"DELETE {list_path} returned {code} (validation) before RBAC; cannot assert. Body={_fmt_body(resp)}")

        if manage_allowed:
            assert 200 <= code < 300, (
                f"{list_path} -> {code}: {_fmt_body(resp)} "
                f"(expected 2xx because RBAC includes manage:{tail})"
            )
        else:
            assert code != 200, (
                f"{list_path} unexpectedly returned 200; RBAC does not include manage:{tail}"
            )
