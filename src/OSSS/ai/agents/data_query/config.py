# src/OSSS/ai/agents/data_query/config.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from OSSS.ai.observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class DataQueryRoute:
    # core routing fields
    topic: str
    collection: str
    view_name: str
    path: Optional[str] = None               # e.g. "/api/consents"
    detail_path: Optional[str] = None        # e.g. "/api/consents/{id}"
    store_key: Optional[str] = None
    base_url: Optional[str] = None
    default_params: Dict[str, Any] = field(
        default_factory=lambda: {"skip": 0, "limit": 100}
    )

    # schema / metadata (plumbed from routes.json)
    id: Optional[str] = None
    table: Optional[str] = None
    api_route: Optional[str] = None
    topic_key: Optional[str] = None
    display_name: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)
    description: Optional[str] = None

    @property
    def resolved_path(self) -> str:
        if self.path:
            return self.path
        return f"/api/{self.collection}"

    @property
    def resolved_store_key(self) -> str:
        if self.store_key:
            return self.store_key
        return f"data_query:{self.view_name}"

    def resolve_detail_path(self, resource_id: Any) -> str:
        if self.detail_path:
            return self.detail_path.format(id=resource_id)
        base = self.resolved_path.rstrip("/")
        return f"{base}/{resource_id}"

    # 💡 helper: normalized “entity” object for UI / consumers
    def to_entity(self) -> Dict[str, Any]:
        """
        Normalize route metadata into a schema-like entity dict suitable
        for attaching to payloads / UI meta.
        """
        topic_key = self.topic_key or self.topic or self.collection
        api_route = self.api_route or self.resolved_path

        return {
            "id": self.id or self.topic or self.collection,
            "topic_key": topic_key,
            "table": self.table or self.collection,
            "api_route": api_route,
            "display_name": self.display_name or topic_key.replace("_", " "),
            "synonyms": self.synonyms or [],
            "description": self.description,
            # convenience extras
            "collection": self.collection,
            "view_name": self.view_name,
            "path": self.path,
            "detail_path": self.detail_path,
            "base_url": self.base_url,
            "default_params": self.default_params,
        }


def _load_routes_from_json() -> List[DataQueryRoute]:
    here = Path(__file__).parent
    json_path = here / "routes.json"

    logger.info(
        "[data_query.config] Loading data-query routes from JSON",
        extra={
            "event": "data_query_routes_load_start",
            "json_path": str(json_path),
        },
    )

    try:
        with json_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        logger.exception(
            "[data_query.config] routes.json not found",
            extra={
                "event": "data_query_routes_load_error",
                "json_path": str(json_path),
                "error_type": "FileNotFoundError",
            },
        )
        raise
    except json.JSONDecodeError as e:
        logger.exception(
            "[data_query.config] Failed to parse routes.json",
            extra={
                "event": "data_query_routes_load_error",
                "json_path": str(json_path),
                "error_type": "JSONDecodeError",
                "error_msg": str(e),
            },
        )
        raise
    except Exception as e:
        logger.exception(
            "[data_query.config] Unexpected error loading routes.json",
            extra={
                "event": "data_query_routes_load_error",
                "json_path": str(json_path),
                "error_type": type(e).__name__,
                "error_msg": str(e),
            },
        )
        raise

    routes: List[DataQueryRoute] = []
    for item in raw:
        route = DataQueryRoute(
            topic=item["topic"],
            collection=item["collection"],
            view_name=item.get("view_name", item["topic"]),
            path=item.get("path"),
            detail_path=item.get("detail_path"),
            store_key=item.get("store_key"),
            base_url=item.get("base_url"),
            default_params=item.get("default_params", {"skip": 0, "limit": 100}),
            # plumb through metadata fields
            id=item.get("id"),
            table=item.get("table"),
            api_route=item.get("api_route"),
            topic_key=item.get("topic_key"),
            display_name=item.get("display_name"),
            synonyms=item.get("synonyms") or [],
            description=item.get("description"),
        )
        routes.append(route)

    logger.info(
        "[data_query.config] Loaded data-query routes",
        extra={
            "event": "data_query_routes_loaded",
            "route_count": len(routes),
            "topics": [r.topic for r in routes],
            "collections": [r.collection for r in routes],
        },
    )

    return routes


_ROUTES: List[DataQueryRoute] = _load_routes_from_json()

# Build a richer registry: topic, collection, and view_name all map to the route.
_ROUTES_BY_TOPIC: Dict[str, DataQueryRoute] = {}
for r in _ROUTES:
    keys = set()

    if r.topic:
        keys.add(str(r.topic).strip().lower())
    if r.collection:
        keys.add(str(r.collection).strip().lower())
    if r.view_name:
        keys.add(str(r.view_name).strip().lower())

    for key in keys:
        if not key:
            continue
        if key in _ROUTES_BY_TOPIC and _ROUTES_BY_TOPIC[key] is not r:
            # Log but don't overwrite: first one wins
            logger.debug(
                "[data_query.config] duplicate topic key for registry; keeping first",
                extra={
                    "event": "data_query_routes_duplicate_key",
                    "key": key,
                    "existing_topic": _ROUTES_BY_TOPIC[key].topic,
                    "new_topic": r.topic,
                },
            )
            continue
        _ROUTES_BY_TOPIC[key] = r

# NEW: direct lookup by synonym text
_ROUTES_BY_SYNONYM: Dict[str, DataQueryRoute] = {}
for r in _ROUTES:
    for syn in (r.synonyms or []):
        key = syn.strip().lower()
        if not key:
            continue
        # first win, don't overwrite
        if key not in _ROUTES_BY_SYNONYM:
            _ROUTES_BY_SYNONYM[key] = r
        else:
            logger.debug(
                "[data_query.config] duplicate synonym key for registry; keeping first",
                extra={
                    "event": "data_query_routes_duplicate_synonym",
                    "synonym": key,
                    "existing_topic": _ROUTES_BY_SYNONYM[key].topic,
                    "new_topic": r.topic,
                },
            )

_DEFAULT_ROUTE: DataQueryRoute = _ROUTES[0]

logger.info(
    "[data_query.config] DataQueryRoute registry initialized",
    extra={
        "event": "data_query_routes_registry_initialized",
        "route_count": len(_ROUTES),
        "default_topic": _DEFAULT_ROUTE.topic,
        "default_collection": _DEFAULT_ROUTE.collection,
        "default_view_name": _DEFAULT_ROUTE.view_name,
    },
)


def resolve_route(topic: Optional[str], intent: Optional[str] = None) -> DataQueryRoute:
    """
    Resolve a route based on a classifier topic (and optional intent).

    Logs:
      - incoming topic/intent
      - whether we matched exactly, via prefix, or fell back to default
    """
    logger.debug(
        "[data_query.config] resolve_route called",
        extra={
            "event": "data_query_resolve_route_called",
            "topic": topic,
            "intent": intent,
        },
    )

    if topic:
        t = topic.lower()
        if t in _ROUTES_BY_TOPIC:
            route = _ROUTES_BY_TOPIC[t]
            logger.info(
                "[data_query.config] Resolved route by exact topic match",
                extra={
                    "event": "data_query_resolve_route_exact",
                    "topic": t,
                    "collection": route.collection,
                    "view_name": route.view_name,
                    "path": route.resolved_path,
                },
            )
            return route

        # simple prefix match (e.g. "consents.list" → "consents")
        for key, route in _ROUTES_BY_TOPIC.items():
            if t.startswith(key):
                logger.info(
                    "[data_query.config] Resolved route by prefix topic match",
                    extra={
                        "event": "data_query_resolve_route_prefix",
                        "topic": t,
                        "matched_key": key,
                        "collection": route.collection,
                        "view_name": route.view_name,
                        "path": route.resolved_path,
                    },
                )
                return route

    logger.info(
        "[data_query.config] Falling back to default route",
        extra={
            "event": "data_query_resolve_route_default",
            "topic": topic,
            "intent": intent,
            "default_topic": _DEFAULT_ROUTE.topic,
            "default_collection": _DEFAULT_ROUTE.collection,
            "default_view_name": _DEFAULT_ROUTE.view_name,
            "default_path": _DEFAULT_ROUTE.resolved_path,
        },
    )
    return _DEFAULT_ROUTE


def find_route_for_text(
    text: Optional[str],
    intent: Optional[str] = None,
) -> DataQueryRoute:
    logger.debug(
        "[data_query.config] find_route_for_text called",
        extra={
            "event": "data_query_find_route_for_text_called",
            "text_preview": (text[:100] if text else None),
            "intent": intent,
        },
    )

    if not text:
        logger.info(
            "[data_query.config] No text provided; using default route",
            extra={
                "event": "data_query_find_route_for_text_default_no_text",
                "default_topic": _DEFAULT_ROUTE.topic,
                "default_collection": _DEFAULT_ROUTE.collection,
                "default_view_name": _DEFAULT_ROUTE.view_name,
            },
        )
        return _DEFAULT_ROUTE

    t = text.lower().strip()

    # Optional tiny heuristic: strip leading verbs like "query", "list", "show"
    # so "query consents" → "consents"
    for prefix in ("query ", "list ", "show ", "get "):
        if t.startswith(prefix):
            candidate = t[len(prefix):].strip()
            if candidate in _ROUTES_BY_TOPIC:
                route = _ROUTES_BY_TOPIC[candidate]
                logger.info(
                    "[data_query.config] Resolved route by verb-stripped text",
                    extra={
                        "event": "data_query_find_route_for_text_verb_strip",
                        "original_text": t,
                        "candidate": candidate,
                        "topic": route.topic,
                        "collection": route.collection,
                        "view_name": route.view_name,
                        "path": route.resolved_path,
                    },
                )
                return route
            # don't break; fall through to other heuristics with full text
            break

    # 1) exact match on topic / collection / view_name
    if t in _ROUTES_BY_TOPIC:
        route = _ROUTES_BY_TOPIC[t]
        logger.info(
            "[data_query.config] Resolved route by exact text match",
            extra={
                "event": "data_query_find_route_for_text_exact",
                "text": t,
                "topic": route.topic,
                "collection": route.collection,
                "view_name": route.view_name,
                "path": route.resolved_path,
            },
        )
        return route

    # 2) exact match on synonym (e.g. "asset warranties" → warranties)
    if t in _ROUTES_BY_SYNONYM:
        route = _ROUTES_BY_SYNONYM[t]
        logger.info(
            "[data_query.config] Resolved route by exact synonym match",
            extra={
                "event": "data_query_find_route_for_text_synonym_exact",
                "text": t,
                "topic": route.topic,
                "collection": route.collection,
                "view_name": route.view_name,
                "path": route.resolved_path,
            },
        )
        return route

    # 3) substring topic match (e.g. "query consents" → consents)
    for key, route in _ROUTES_BY_TOPIC.items():
        if key and key in t:
            logger.info(
                "[data_query.config] Resolved route by substring topic match",
                extra={
                    "event": "data_query_find_route_for_text_substring_topic",
                    "text": t,
                    "matched_key": key,
                    "topic": route.topic,
                    "collection": route.collection,
                    "view_name": route.view_name,
                    "path": route.resolved_path,
                },
            )
            return route

    # 4) substring synonym match (e.g. "list consent forms" where synonym is "consent forms")
    for syn, route in _ROUTES_BY_SYNONYM.items():
        if syn and syn in t:
            logger.info(
                "[data_query.config] Resolved route by substring synonym match",
                extra={
                    "event": "data_query_find_route_for_text_substring_synonym",
                    "text": t,
                    "matched_synonym": syn,
                    "topic": route.topic,
                    "collection": route.collection,
                    "view_name": route.view_name,
                    "path": route.resolved_path,
                },
            )
            return route

    logger.info(
        "[data_query.config] No text/topic/synonym match; using default route",
        extra={
            "event": "data_query_find_route_for_text_default",
            "text": t,
            "intent": intent,
            "default_topic": _DEFAULT_ROUTE.topic,
            "default_collection": _DEFAULT_ROUTE.collection,
            "default_view_name": _DEFAULT_ROUTE.view_name,
            "default_path": _DEFAULT_ROUTE.resolved_path,
        },
    )
    return _DEFAULT_ROUTE
