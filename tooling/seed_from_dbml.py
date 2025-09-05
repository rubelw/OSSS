
#!/usr/bin/env python3
"""Seed a FastAPI app from a DBML schema.

Features
- Loads .env from CWD or any parent dir (python-dotenv if available; otherwise minimal fallback).
- Auth via Keycloak password grant (REALM_URL, CLIENT_ID, USERNAME, PASSWORD) or direct BEARER_TOKEN.
- Reads DBML tables; probes POST /api/<table> endpoints from OpenAPI.
- Builds minimal valid payloads from OpenAPI schemas (handles $ref, allOf/oneOf/anyOf, enums, required, formats).
- Sends JSON/form/multipart based on requestBody content-types.
- Logs outcomes; skips 400/401/403/404/405/409/422 without stopping the whole run.
"""
import argparse
import logging
import os
import sys
import re
import json
import random
import string
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from urllib.parse import urljoin
import uuid
import datetime

try:
    import requests
except Exception as e:
    print("This script requires 'requests'. pip install requests", file=sys.stderr)
    raise

# ------------------------ .env loader ------------------------

def load_env_searching_up(start: Path) -> Optional[Path]:
    """Search for a .env file starting at 'start' and moving upward."""
    cur = start.resolve()
    for _ in range(30):
        candidate = cur / ".env"
        if candidate.exists():
            return candidate
        if cur.parent == cur:
            break
        cur = cur.parent
    return None

def load_dotenv_best_effort():
    """Load .env with python-dotenv if present; else do a tiny parser."""
    path = load_env_searching_up(Path.cwd())
    if not path:
        return
    try:
        from dotenv import load_dotenv as _dotenv_load
        _dotenv_load(dotenv_path=str(path))
        print(f"[dotenv] Loaded {path}", flush=True)
        return
    except Exception:
        # minimal fallback
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                os.environ.setdefault(k, v)
            print(f"[dotenv] Loaded (fallback) {path}", flush=True)
        except Exception as e:
            print(f"[dotenv] Failed to load {path}: {e}", file=sys.stderr)

# ------------------------ logging ------------------------

def setup_logging(verbosity: int):
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

log = logging.getLogger("seed")

# ------------------------ DBML parsing ------------------------

DBML_TABLE_RE = re.compile(r'(?im)^\s*Table\s+([A-Za-z0-9_]+)\s*\{')

def extract_tables_from_dbml(dbml_text: str) -> List[str]:
    tables = DBML_TABLE_RE.findall(dbml_text)
    seen = set()
    out: List[str] = []
    for t in tables:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out

# ------------------------ OpenAPI helpers ------------------------

def fetch_openapi(base_url: str, session: requests.Session, timeout: int = 15) -> Dict[str, Any]:
    url = urljoin(base_url.rstrip("/") + "/", "openapi.json")
    log.info(f"Fetching OpenAPI: {url}")
    r = session.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def find_post_for_table(openapi: Dict[str, Any], table: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Look for POST /api/<table> or common variants."""
    paths = openapi.get("paths") or {}
    candidates = [
        f"/api/{table}",
        f"/v1/{table}",
        f"/{table}",
    ]
    for p in list(paths.keys()):
        if p in candidates:
            post = (paths[p] or {}).get("post")
            if post:
                return p, post
    for p, ops in paths.items():
        tail = p.rstrip("/").split("/")[-1]
        if tail == table and "post" in (ops or {}):
            return p, ops["post"]
    return None

# ------------------------ Schema resolver ------------------------

class SchemaResolver:
    def __init__(self, spec: Dict[str, Any]):
        self.spec = spec
        self._cache: Dict[str, Any] = {}

    def resolve_ref(self, ref: str) -> Any:
        if not ref.startswith("#/"):
            return {}
        if ref in self._cache:
            return self._cache[ref]
        parts = ref.lstrip("#/").split("/")
        node: Any = self.spec
        for p in parts:
            node = node.get(p, {})
        self._cache[ref] = node
        return node

    def _merge_allOf(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        allOf = schema.get("allOf")
        if not allOf:
            return schema
        base: Dict[str, Any] = {k: v for k, v in schema.items() if k != "allOf"}
        for s in allOf:
            if "$ref" in s:
                s = self.resolve_ref(s["$ref"])
            s = self._merge_allOf(s)
            for k, v in s.items():
                if k == "required":
                    base.setdefault("required", [])
                    for item in v:
                        if item not in base["required"]:
                            base["required"].append(item)
                elif k == "properties":
                    base.setdefault("properties", {})
                    base["properties"].update(v or {})
                else:
                    base[k] = v
        return base

    def simplify(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        if not schema:
            return {}
        if "$ref" in schema:
            schema = self.resolve_ref(schema["$ref"])
        schema = self._merge_allOf(schema)
        for key in ("oneOf", "anyOf"):
            opts = schema.get(key)
            if opts and isinstance(opts, list):
                choice = opts[0]
                if "$ref" in choice:
                    choice = self.resolve_ref(choice["$ref"])
                schema = self._merge_allOf(choice)
                break
        return schema

# ------------------------ Payload builder ------------------------

def random_string(n=8):
    import random, string
    return "".join(random.choice(string.ascii_lowercase) for _ in range(n))

def example_for_type(schema: Dict[str, Any]) -> Any:
    t = schema.get("type")
    fmt = schema.get("format")
    enum = schema.get("enum")
    if enum:
        return enum[0]
    if t == "string":
        if fmt in ("date-time", "datetime"):
            return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        if fmt == "date":
            return datetime.date.today().isoformat()
        if fmt == "email":
            return "test@example.com"
        if fmt in ("uuid", "uuid4"):
            return str(uuid.uuid4())
        if fmt == "binary":
            return "file.bin"
        return "string"
    if t == "integer":
        return 1
    if t == "number":
        return 0
    if t == "boolean":
        return False
    if t == "array":
        items = schema.get("items") or {}
        if items.get("type") == "object" or items.get("properties"):
            return [{}]
        return [example_for_type(items)]
    if t == "object":
        return {}
    return "string"

def build_minimal_object(schema: Dict[str, Any], resolver: SchemaResolver) -> Dict[str, Any]:
    schema = resolver.simplify(schema or {})
    props: Dict[str, Any] = schema.get("properties") or {}
    required: List[str] = list(schema.get("required") or [])
    out: Dict[str, Any] = {}

    for name, prop in props.items():
        if "$ref" in prop:
            prop = resolver.resolve_ref(prop["$ref"])
            prop = resolver.simplify(prop)
        t = prop.get("type")
        if t == "object":
            out[name] = build_minimal_object(prop, resolver)
        elif t == "array":
            items = prop.get("items") or {}
            if "$ref" in items:
                items = resolver.resolve_ref(items["$ref"])
                items = resolver.simplify(items)
            if items.get("type") == "object" or items.get("properties"):
                out[name] = [build_minimal_object(items, resolver)]
            else:
                out[name] = [example_for_type(items)]
        else:
            out[name] = example_for_type(prop)

    for req in required:
        if req not in out:
            out[req] = "string"
    return out

def build_payload_from_request_body(spec: Dict[str, Any], path: str, post_op: Dict[str, Any]):
    """Return (content_type, data, files or None)."""
    rb = (post_op or {}).get("requestBody")
    if not rb:
        return None
    content = (rb.get("content") or {})
    resolver = SchemaResolver(spec)

    for ct in ("multipart/form-data", "application/x-www-form-urlencoded", "application/json"):
        if ct not in content:
            continue
        schema = content[ct].get("schema") or {}
        schema = resolver.simplify(schema)
        if schema.get("type") == "object" or schema.get("properties"):
            data = build_minimal_object(schema, resolver)
        else:
            data = {"value": "string"}

        files = None
        if ct == "multipart/form-data":
            files = {}
            props = schema.get("properties") or {}
            for name, prop in props.items():
                p = prop
                if "$ref" in p:
                    p = resolver.resolve_ref(p["$ref"])
                    p = resolver.simplify(p)
                if p.get("type") == "string" and p.get("format") == "binary":
                    files[name] = ("file.txt", b"dummy")
                    data.pop(name, None)
        return ct, data, files
    return None

# ------------------------ Keycloak auth ------------------------

def get_bearer_token(session: requests.Session, env: Dict[str, str]) -> Optional[str]:
    token = env.get("BEARER_TOKEN")
    if token:
        return token
    realm_url = env.get("REALM_URL")
    client_id = env.get("CLIENT_ID")
    username = env.get("USERNAME")
    password = env.get("PASSWORD")
    if not (realm_url and client_id and username and password):
        return None
    token_url = realm_url.rstrip("/") + "/protocol/openid-connect/token"
    data = {
        "grant_type": "password",
        "client_id": client_id,
        "username": username,
        "password": password,
    }
    log.info(f"Requesting token from {token_url} for {username}")
    r = session.post(token_url, data=data, timeout=20)
    if r.status_code != 200:
        log.warning("Token request failed: %s %s", r.status_code, r.text[:400])
        return None
    return (r.json() or {}).get("access_token")

# ------------------------ main ------------------------

def main():
    load_dotenv_best_effort()

    ap = argparse.ArgumentParser(description="Seed FastAPI app from DBML + OpenAPI")
    ap.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8081"))
    ap.add_argument("--dbml", default=os.getenv("DBML_PATH", "./schema.dbml"))
    ap.add_argument("--max-per-table", type=int, default=int(os.getenv("MAX_PER_TABLE", "1")))
    ap.add_argument("-v", "--verbose", action="count", default=0)
    args = ap.parse_args()

    setup_logging(args.verbose)

    base = args.base_url.rstrip("/")
    dbml_path = Path(args.dbml)

    if not dbml_path.exists():
        print(f"DBML file not found: {dbml_path}", file=sys.stderr)
        sys.exit(2)

    dbml_text = dbml_path.read_text(encoding="utf-8")
    tables = extract_tables_from_dbml(dbml_text)
    if not tables:
        print("No tables found in DBML.", file=sys.stderr)
        sys.exit(1)

    sess = requests.Session()

    token = get_bearer_token(sess, os.environ)
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        spec = fetch_openapi(base, sess)
    except Exception as e:
        print(f"Failed to fetch openapi.json from {base}: {e}", file=sys.stderr)
        sys.exit(2)

    total_created = 0

    for t in tables:
        found = find_post_for_table(spec, t)
        if not found:
            log.info(f"[SKIP] No POST endpoint for table {t}")
            continue
        path, post_op = found
        built = build_payload_from_request_body(spec, path, post_op)
        url = urljoin(base + "/", path.lstrip("/"))
        if not built:
            log.info(f"[SKIP] {path} has no requestBody")
            continue
        ct, data, files = built
        log.info(f"POST {url} ct={ct} payload={data} files={list((files or {}).keys())}")

        try:
            if ct == "application/json":
                r = sess.post(url, json=data, headers={**headers, "Content-Type": ct}, timeout=30)
            elif ct == "application/x-www-form-urlencoded":
                r = sess.post(url, data=data, headers={**headers, "Content-Type": ct}, timeout=30)
            elif ct == "multipart/form-data":
                r = sess.post(url, data=data, files=files, headers=headers, timeout=30)
            else:
                r = sess.post(url, json=data, headers=headers, timeout=30)
        except Exception as e:
            log.error(f"[ERROR] POST {url} raised: {e}")
            continue

        if 200 <= r.status_code < 300:
            log.info(f"[OK] {path} -> {r.status_code}")
            total_created += 1
        elif r.status_code in (400, 401, 403, 404, 405, 409, 422):
            log.warning(f"[SKIP {r.status_code}] {path} -> {r.text[:400]}")
        else:
            log.error(f"[FAIL {r.status_code}] {path} -> {r.text[:400]}")

    print(f"Done. Created ~{total_created} item(s).", flush=True)

if __name__ == "__main__":
    main()
