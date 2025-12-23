# src/OSSS/ai/agents/data_query/specs_runtime.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal

from fastapi.routing import APIRoute
from fastapi import FastAPI

SourceType = Literal["http", "postgres_sql"]

@dataclass(frozen=True)
class DataQuerySpec:
    name: str
    description: str
    source: SourceType
    base_url: Optional[str] = None

    list_path: Optional[str] = None
    get_path: Optional[str] = None
    create_path: Optional[str] = None
    patch_path: Optional[str] = None
    put_path: Optional[str] = None
    delete_path: Optional[str] = None

    default_query_params: Optional[Dict[str, Any]] = None
    store_key: str = "data_query_result"
    max_rows: int = 200


def build_specs_from_app(app: FastAPI, *, base_url: str) -> dict[str, DataQuerySpec]:
    # resource -> methods -> path
    by_resource: dict[str, dict[str, str]] = {}
    descriptions: dict[str, str] = {}

    for r in app.routes:
        if not isinstance(r, APIRoute):
            continue
        path = r.path  # e.g. "/api/students" or "/api/students/{item_id}"
        if not path.startswith("/api/"):
            continue

        # resource key: "/api/<resource>"
        parts = path.split("/")
        if len(parts) < 3:
            continue
        resource = parts[2]  # "<resource>"

        by_resource.setdefault(resource, {})

        for m in (r.methods or set()):
            m = m.upper()
            # prefer stable assignment based on shape
            if m == "GET" and "{item_id}" not in path and "{id}" not in path:
                by_resource[resource]["LIST"] = path
            elif m == "GET" and ("{item_id}" in path or "{id}" in path):
                by_resource[resource]["GET"] = path.replace("{item_id}", "{id}")
            elif m == "POST":
                by_resource[resource]["POST"] = path
            elif m == "PATCH":
                by_resource[resource]["PATCH"] = path.replace("{item_id}", "{id}")
            elif m == "PUT":
                by_resource[resource]["PUT"] = path.replace("{item_id}", "{id}")
            elif m == "DELETE":
                by_resource[resource]["DELETE"] = path.replace("{item_id}", "{id}")

        # grab a human-ish description/summary if available
        if resource not in descriptions:
            desc = (r.summary or "").strip() or (r.name or "").strip() or resource.replace("_", " ").title()
            descriptions[resource] = desc

    specs: dict[str, DataQuerySpec] = {}
    for resource, mapping in sorted(by_resource.items()):
        name = resource  # resource is already plural from your factory
        specs[name] = DataQuerySpec(
            name=name,
            description=descriptions.get(resource, name),
            source="http",
            base_url=base_url,
            list_path=mapping.get("LIST"),
            get_path=mapping.get("GET"),
            create_path=mapping.get("POST"),
            patch_path=mapping.get("PATCH"),
            put_path=mapping.get("PUT"),
            delete_path=mapping.get("DELETE"),
            default_query_params={"skip": 0, "limit": 50},
            store_key=f"{name}_result",
        )

    return specs
