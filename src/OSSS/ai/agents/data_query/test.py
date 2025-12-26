#!/usr/bin/env python
"""
Populate / update routes.json from schema_topic_map.json, ensuring:
  - Every schema entry has a corresponding route
  - Extra schema fields propagate into the route
  - The SQL table name is added to synonyms list if missing

Usage:
    python sync_routes_from_schema.py \
        --schema schema_topic_map.json \
        --routes routes.json \
        --output routes.json
"""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_BASE_URL = "http://app:8000"
DEFAULT_SKIP = 0
DEFAULT_LIMIT = 100


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return data


def index_routes(routes: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Index existing routes by common identifiers."""
    idx: Dict[str, Dict[str, Any]] = {}
    for r in routes:
        for key in ("topic", "collection", "view_name"):
            v = r.get(key)
            if isinstance(v, str) and v:
                k = v.lower()
                idx.setdefault(k, r)
    return idx


def ensure_route_for_schema_entry(
    schema_entry: Dict[str, Any],
    routes: List[Dict[str, Any]],
    routes_idx: Dict[str, Dict[str, Any]],
    default_base_url: str = DEFAULT_BASE_URL,
) -> Dict[str, Any]:
    """
    Given one schema entry, ensure a corresponding route exists and is populated.
    Adds table_name to synonyms list automatically.
    """
    schema_id = str(schema_entry.get("id") or "").strip()
    topic_key = str(schema_entry.get("topic_key") or schema_id).strip()

    if not schema_id:
        raise ValueError(f"Schema entry missing 'id': {schema_entry!r}")

    # Try matching existing route by topic-key or id
    route = None
    for key in (topic_key, schema_id):
        if key and key.lower() in routes_idx:
            route = routes_idx[key.lower()]
            break

    # If route missing → create it
    if route is None:
        api_route = schema_entry.get("api_route") or f"/api/{schema_id}"
        route = {
            "topic": topic_key,
            "collection": schema_id,
            "view_name": schema_id,
            "path": api_route,
            "detail_path": f"{api_route.rstrip('/')}/{{id}}",
            "base_url": default_base_url,
            "default_params": {"skip": DEFAULT_SKIP, "limit": DEFAULT_LIMIT},
        }
        routes.append(route)
        routes_idx[topic_key.lower()] = route
        routes_idx[schema_id.lower()] = route

    # Fill in defaults if missing
    route.setdefault("topic", topic_key)
    route.setdefault("collection", schema_id)
    route.setdefault("view_name", schema_id)

    api_route = schema_entry.get("api_route") or f"/api/{schema_id}"
    route.setdefault("path", api_route)
    route.setdefault("detail_path", f"{api_route.rstrip('/')}/{{id}}")

    route.setdefault("base_url", default_base_url)
    route.setdefault("default_params", {})
    route["default_params"].setdefault("skip", DEFAULT_SKIP)
    route["default_params"].setdefault("limit", DEFAULT_LIMIT)

    # Merge schema fields onto route (non-destructive)
    for key, value in schema_entry.items():
        route.setdefault(key, value)

    # ---------------------------
    # ⭐ Ensure synonyms exists and includes the SQL table name
    # ---------------------------
    # --- updated synonyms behavior ---
    # Always add user-friendly table name version: underscores → spaces
    raw_table_name = schema_entry.get("table") or schema_id
    pretty_table_name = raw_table_name.replace("_", " ").strip()

    synonyms = route.get("synonyms")
    if not isinstance(synonyms, list):
        synonyms = [] if synonyms in (None, "") else [synonyms]

    # Avoid duplicates or case variants
    existing = {s.lower().strip() for s in synonyms}

    if pretty_table_name.lower() not in existing:
        synonyms.append(pretty_table_name)

    route["synonyms"] = synonyms
    # --- end updated behavior ---

    # ---------------------------

    return route


def sync_routes(
    schema_path: Path,
    routes_path: Path,
    output_path: Path,
    base_url: str,
) -> None:
    schema_entries = load_json_list(schema_path)
    routes = load_json_list(routes_path)
    routes_idx = index_routes(routes)

    for entry in schema_entries:
        ensure_route_for_schema_entry(entry, routes, routes_idx, base_url)

    routes_sorted = sorted(routes, key=lambda r: (str(r.get("topic", "")).lower()))
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(routes_sorted, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync routes.json from schema_topic_map.json")
    parser.add_argument("--schema", type=Path, default=Path("schema_topic_map.json"))
    parser.add_argument("--routes", type=Path, default=Path("routes.json"))
    parser.add_argument("--output", type=Path, default=Path("routes.json"))
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    sync_routes(args.schema, args.routes, args.output, args.base_url)


if __name__ == "__main__":
    main()
