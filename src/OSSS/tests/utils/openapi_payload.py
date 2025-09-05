from __future__ import annotations
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Tuple
import json
import os
import re

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def load_openapi_from_client(client, url: str = "/openapi.json") -> Dict[str, Any]:
    """Works with FastAPI TestClient or httpx/requests Session."""
    r = client.get(url)
    r.raise_for_status()
    return r.json()


def _resolve_ref(schema: Dict[str, Any], components: Dict[str, Any]) -> Dict[str, Any]:
    """Follow a local $ref like '#/components/schemas/Foo'."""
    if "$ref" not in schema:
        return schema
    ref = schema["$ref"]
    if not ref.startswith("#/"):
        return schema  # out-of-scope ref; leave as-is
    node: Any = {"components": components}
    for part in ref.lstrip("#/").split("/"):
        node = node[part]
    return node


def _merge_allOf(schema: Dict[str, Any], components: Dict[str, Any]) -> Dict[str, Any]:
    """Merge allOf parts into a single schema object (simple/naive merge)."""
    out: Dict[str, Any] = {}
    for sub in schema.get("allOf", []):
        sub = _resolve_ref(sub, components)
        out.update(sub)
    # keep non-allOf props too
    for k, v in schema.items():
        if k != "allOf":
            out.setdefault(k, v)
    return out


def example_from_schema(schema: Dict[str, Any], components: Dict[str, Any]) -> Any:
    """Generate a reasonable example for a JSON Schema (OpenAPI flavor)."""
    if not schema:
        return None

    schema = _resolve_ref(schema, components)
    if "allOf" in schema:
        schema = _merge_allOf(schema, components)

    # Direct example/default beats everything
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]

    # oneOf / anyOf: pick first workable branch
    for comb in ("oneOf", "anyOf"):
        if comb in schema and schema[comb]:
            return example_from_schema(schema[comb][0], components)

    typ = schema.get("type")

    if typ == "object" or ("properties" in schema and typ is None):
        props: Dict[str, Any] = schema.get("properties", {}) or {}
        required = set(schema.get("required", []) or [])
        out = {}
        for name, subschema in props.items():
            out[name] = example_from_schema(subschema, components)
        # If object with no properties but additionalProperties
        if not out and schema.get("additionalProperties"):
            ap = schema["additionalProperties"]
            out["key"] = example_from_schema(ap if isinstance(ap, dict) else {}, components)
        return out

    if typ == "array":
        item_schema = schema.get("items", {}) or {}
        return [example_from_schema(item_schema, components)]

    if typ == "string":
        fmt = schema.get("format")
        if fmt == "uuid":
            return "00000000-0000-4000-8000-000000000000"
        if fmt in ("date-time", "datetime"):
            return "2025-01-01T00:00:00Z"
        if fmt == "date":
            return "2025-01-01"
        if fmt == "binary":
            # for multipart/form-data, caller should move this into 'files'
            return "<binary>"
        return "string"

    if typ == "integer":
        return 1
    if typ == "number":
        return 1.0
    if typ == "boolean":
        return True

    # Fallbacks
    if "properties" in schema:
        return {k: example_from_schema(v, components) for k, v in schema["properties"].items()}
    return None


def _collect_parameters(operation: Dict[str, Any], path_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Combine path-level and operation-level parameters (operation overrides)."""
    params = []
    seen = set()
    for src in (path_item.get("parameters", []), operation.get("parameters", [])):
        for p in src or []:
            key = (p.get("name"), p.get("in"))
            if key in seen:
                # operation-level param with same name/in should override
                continue
            seen.add(key)
            params.append(p)
    return params


def _build_params_dict(parameters: List[Dict[str, Any]], components: Dict[str, Any], where: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for p in parameters:
        if p.get("in") != where:
            continue
        name = p["name"]
        schema = p.get("schema") or {}
        if "example" in p:
            out[name] = p["example"]
        else:
            out[name] = example_from_schema(schema, components)
        # ensure strings for path params
        if where == "path" and out[name] is None:
            out[name] = "1"
    return out


def _format_path(path_tmpl: str, path_params: Mapping[str, Any]) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(path_params.get(m.group(1), m.group(0))), path_tmpl)


def _build_request_body(operation: Dict[str, Any], components: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Return (json, data, files) for the request body.
    Preference: application/json -> application/x-www-form-urlencoded -> multipart/form-data
    """
    body = operation.get("requestBody")
    if not body:
        return {}, {}, {}
    body = _resolve_ref(body, components)

    content = (body.get("content") or {})
    # Try json first
    if "application/json" in content:
        schema = content["application/json"].get("schema") or {}
        return {"json": example_from_schema(schema, components)}, {}, {}

    # x-www-form-urlencoded
    if "application/x-www-form-urlencoded" in content:
        schema = content["application/x-www-form-urlencoded"].get("schema") or {}
        payload = example_from_schema(schema, components)
        if not isinstance(payload, dict):
            payload = {}
        return {}, {"data": payload}, {}

    # multipart/form-data
    if "multipart/form-data" in content:
        schema = content["multipart/form-data"].get("schema") or {}
        payload = example_from_schema(schema, components)
        data: Dict[str, Any] = {}
        files: Dict[str, Any] = {}
        if isinstance(payload, dict):
            for k, v in payload.items():
                if isinstance(v, str) and v == "<binary>":
                    # (filename, fileobj/bytes, content_type)
                    files[k] = ("file.bin", b"0123456789", "application/octet-stream")
                else:
                    data[k] = v
        return {}, {"data": data}, {"files": files}

    # last resort: pick any content type schema and treat as json
    for _ctype, cobj in content.items():
        schema = (cobj or {}).get("schema") or {}
        return {"json": example_from_schema(schema, components)}, {}, {}

    return {}, {}, {}


def iter_openapi_operations(openapi: Dict[str, Any]) -> Iterator[Tuple[str, str, Dict[str, Any], Dict[str, Any]]]:
    """
    Yields (method, path, operation, path_item)
    for every method present in the openapi doc.
    """
    paths = openapi.get("paths", {}) or {}
    for path, path_item in paths.items():
        for method, operation in path_item.items():
            if method.lower() in HTTP_METHODS and isinstance(operation, dict):
                yield method.lower(), path, operation, path_item


def build_request_for_operation(
    base_url: str,
    method: str,
    path: str,
    operation: Dict[str, Any],
    path_item: Dict[str, Any],
    components: Dict[str, Any],
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Returns (method, url, kwargs) where kwargs is suitable for requests/httpx/TestClient.
    """
    params = _collect_parameters(operation, path_item)
    path_params = _build_params_dict(params, components, where="path")
    query_params = _build_params_dict(params, components, where="query")

    url = base_url.rstrip("/") + _format_path(path, path_params)
    json_k, data_k, files_k = _build_request_body(operation, components)

    kwargs: Dict[str, Any] = {}
    kwargs.update(json_k)
    kwargs.update(data_k)
    kwargs.update(files_k)
    if query_params:
        kwargs["params"] = query_params

    return method.upper(), url, kwargs


def collect_all_payloads(openapi: Dict[str, Any], base_url: str = "") -> List[Dict[str, Any]]:
    """
    Build a list of calls with example payloads for ALL methods found in openapi.json.
    Each item: {"operationId": str|None, "method": str, "path": str, "url": str, "kwargs": {...}}
    """
    components = openapi.get("components", {}) or {}
    out: List[Dict[str, Any]] = []
    for method, path, operation, path_item in iter_openapi_operations(openapi):
        m, url, kwargs = build_request_for_operation(base_url, method, path, operation, path_item, components)
        out.append({
            "operationId": operation.get("operationId"),
            "method": m,
            "path": path,
            "url": url,
            "kwargs": kwargs,
        })
    return out
