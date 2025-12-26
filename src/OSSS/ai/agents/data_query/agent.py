# src/OSSS/ai/agents/data_query/agent.py
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from OSSS.ai.agents.data_query.config import (
    DataQueryRoute,
    resolve_route,
    find_route_for_text,
)
from OSSS.ai.services.backend_api_client import BackendAPIClient, BackendAPIConfig
# 🔧 IMPORTANT: use the same logger import style as other modules
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

DEFAULT_BASE_URL = os.getenv("OSSS_BACKEND_BASE_URL", "http://app:8000")

# Minimum topic_confidence from classifier to trust its topic mapping.
# If below this, we fall back to text-based route matching.
MIN_TOPIC_CONFIDENCE = float(os.getenv("OSSS_DATAQUERY_MIN_TOPIC_CONFIDENCE", "0.15"))


def _get_classifier_and_text_from_context(context: AgentContext) -> tuple[dict, str]:
    """
    Robustly pull classifier result + original query text from AgentContext.

    We prefer execution_state["original_query"] (which is the raw user query
    from /api/query) over any possibly-mutated context.original_query.
    """
    exec_state = getattr(context, "execution_state", {}) or {}
    meta = getattr(context, "metadata", {}) or {}

    classifier = (
        exec_state.get("prestep", {}).get("classifier")
        or exec_state.get("pre_step", {}).get("classifier")
        or exec_state.get("classifier")
        or meta.get("classifier")
        or {}
    )

    # 🔑 IMPORTANT: prefer exec_state["original_query"] first
    raw_text = (
        exec_state.get("original_query")
        or getattr(context, "original_query", None)
        or exec_state.get("query")
        or meta.get("original_query")
        or meta.get("query")
        or ""
    )

    logger.info(
        "[data_query:context] extracted classifier + text from context",
        extra={
            "event": "data_query_context_extracted",
            "exec_state_keys": list(exec_state.keys()),
            "meta_keys": list(meta.keys()) if isinstance(meta, dict) else [],
            "has_classifier": bool(classifier),
            "raw_text_preview": (raw_text[:200] if isinstance(raw_text, str) else ""),
        },
    )

    return classifier, raw_text if isinstance(raw_text, str) else ""


# -----------------------------------------------------------------------------
# ROUTE SELECTION (classifier/topic → DataQueryRoute)
# -----------------------------------------------------------------------------
def choose_route_for_query(raw_text: str, classifier: Dict[str, Any]) -> DataQueryRoute:
    """
    Decide which DataQueryRoute to use based on classifier output, with
    resolve_route and find_route_for_text as the single sources of truth.

    Order:
      1) If classifier.topic_confidence is high enough, try classifier.topic
         and classifier.topics[]
      2) Otherwise (or if those fail), fall back to text-based route matching:
         find_route_for_text(raw_text)
    """
    topic_primary = classifier.get("topic")
    topics_all = classifier.get("topics") or []
    intent = (classifier.get("intent") or "").strip().lower() or None
    topic_conf = float(classifier.get("topic_confidence") or 0.0)

    logger.debug(
        "[data_query:routing] route selection input",
        extra={
            "event": "data_query_choose_route_called",
            "raw_text": raw_text,
            "topic_primary": topic_primary,
            "topics_all": topics_all,
            "topic_confidence": topic_conf,
            "min_topic_confidence": MIN_TOPIC_CONFIDENCE,
            "classifier": classifier,
        },
    )

    # ---- 1) Use classifier topics only if confidence is high enough ---------
    if topic_primary and topic_conf >= MIN_TOPIC_CONFIDENCE:
        logger.info(
            "[data_query:routing] classifier topic_confidence high enough, "
            "trying classifier topics first",
            extra={
                "event": "data_query_use_classifier_topics",
                "topic_primary": topic_primary,
                "topics_all": topics_all,
                "topic_confidence": topic_conf,
                "min_topic_confidence": MIN_TOPIC_CONFIDENCE,
            },
        )

        candidates: List[Optional[str]] = [topic_primary] + list(topics_all)
        for cand in candidates:
            if not cand:
                continue
            topic_str = str(cand).strip()
            if not topic_str:
                continue

            route = resolve_route(topic_str, intent=intent)
            if route is not None:
                logger.info(
                    "[data_query:routing] using classifier-derived topic via resolve_route",
                    extra={
                        "event": "data_query_choose_route_classifier_topic",
                        "candidate_topic": topic_str,
                        "resolved_topic": route.topic,
                        "resolved_collection": route.collection,
                        "resolved_view_name": route.view_name,
                        "resolved_path": route.resolved_path,
                    },
                )
                return route
    else:
        # Classifier confidence too low → log and skip classifier topics entirely.
        logger.info(
            "[data_query:routing] classifier topic_confidence too low; "
            "skipping classifier topics and falling back to text heuristic",
            extra={
                "event": "data_query_skip_classifier_topics_low_conf",
                "topic_primary": topic_primary,
                "topics_all": topics_all,
                "topic_confidence": topic_conf,
                "min_topic_confidence": MIN_TOPIC_CONFIDENCE,
                "raw_text_preview": raw_text[:200],
            },
        )

    # ---- 2) Fallback: text-based heuristic ----------------------------------
    logger.info(
        "[data_query:routing] falling back to text heuristic (find_route_for_text)",
        extra={
            "event": "data_query_choose_route_fallback_to_text",
            "raw_text_preview": raw_text[:200],
            "topic_primary": topic_primary,
            "topics_all": topics_all,
            "topic_confidence": topic_conf,
        },
    )
    return find_route_for_text(raw_text, intent=intent)


# -----------------------------------------------------------------------------
# RENDER HELPERS
# -----------------------------------------------------------------------------
def _rows_to_markdown_table(
    rows: List[Dict[str, Any]], *, columns: Optional[List[str]] = None, max_rows: int = 20
) -> str:
    logger.debug(
        "[data_query:render] generating markdown preview",
        extra={"num_rows": len(rows), "max_rows": max_rows},
    )
    if not rows:
        return "_No rows returned._"

    if columns:
        cols = [c for c in columns if c]
    else:
        cols = list(rows[0].keys())

    def esc(v: Any) -> str:
        s = "" if v is None else str(v)
        return s.replace("\n", " ").replace("|", "\\|")

    shown = rows[:max_rows]
    md: List[str] = []
    md.append("| " + " | ".join(cols) + " |")
    md.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for row in shown:
        md.append("| " + " | ".join(esc(row.get(c, "")) for c in cols) + " |")

    if len(rows) > max_rows:
        md.append(f"\n_Showing {max_rows} of {len(rows)} rows._")

    preview = "\n".join(md)
    logger.debug(
        "[data_query:render] markdown preview generated",
        extra={"preview_length": len(preview)},
    )
    return preview


# -----------------------------------------------------------------------------
# DATAQUERY AGENT
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class DataQuerySpec:
    name: str
    store_key: str
    source: str = "http"


class DataQueryAgent(BaseAgent):
    name = "data_query"
    BASE_URL = DEFAULT_BASE_URL

    def __init__(
        self,
        *,
        data_query: Optional[Dict[str, Any]] = None,
        pg_engine: Optional[AsyncEngine] = None,
    ):
        super().__init__(name=self.name, timeout_seconds=20.0)
        self.data_query = data_query or {}
        self.pg_engine = pg_engine
        logger.debug(
            "[data_query:init] agent initialized",
            extra={"base_url_default": self.BASE_URL},
        )

    def get_node_definition(self) -> LangGraphNodeDefinition:
        return LangGraphNodeDefinition(
            node_type="tool",
            agent_name=self.name,
            dependencies=["refiner"],
        )

    async def run(self, context: AgentContext) -> AgentContext:

        # --- EXECUTION CONFIG --------------------------------------------------
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        exec_cfg: Dict[str, Any] = exec_state.get("execution_config", {}) or {}
        dq_cfg: Dict[str, Any] = exec_cfg.get("data_query") or {}

        # Classifier + raw text (best-effort)
        classifier, raw_text = _get_classifier_and_text_from_context(context)
        raw_text_norm = (raw_text or "").strip()
        raw_text_lower = raw_text_norm.lower()

        # 🚧 LEXICAL GATE:
        is_structured_query = raw_text_lower.startswith("query ")
        force_data_query = bool(dq_cfg.get("force"))

        logger.info(
            "[data_query] lexical gate",
            extra={
                "event": "data_query_lexical_gate",
                "raw_text_preview": raw_text_norm[:200],
                "is_structured_query": is_structured_query,
                "force_data_query": force_data_query,
            },
        )

        if not is_structured_query and not force_data_query:
            logger.info(
                "[data_query:routing] skipping: does not look like a structured query",
                extra={
                    "event": "data_query_skip_non_structured",
                    "raw_text_preview": raw_text_norm[:200],
                },
            )
            return context

        # --- INTENT ------------------------------------------------------------
        state_intent = getattr(context, "intent", None) or exec_state.get("intent")
        classifier_intent = (
            classifier.get("intent") if isinstance(classifier, dict) else None
        )
        intent_raw = state_intent or classifier_intent
        intent = (intent_raw or "").strip().lower() or None

        topic_override = dq_cfg.get("topic")

        logger.info(
            "[data_query] run() begin",
            extra={
                "event": "data_query_run_begin",
                "intent": intent,
                "topic_override": topic_override,
                "raw_text_preview": raw_text_norm[:200],
                "classifier_topic": classifier.get("topic") if isinstance(classifier, dict) else None,
                "classifier_topics": classifier.get("topics") if isinstance(classifier, dict) else None,
            },
        )

        logger.debug(
            "[data_query] run() begin (debug)",
            extra={
                "event": "data_query_run_begin_debug",
                "intent": intent,
                "topic_override": topic_override,
                "raw_text": raw_text_norm,
                "classifier": classifier,
            },
        )

        # --- ROUTE SELECTION ---------------------------------------------------
        if topic_override:
            route = resolve_route(topic_override, intent=intent)
            route_source = "explicit_override"
            logger.info(
                "[data_query:routing] using explicit topic override",
                extra={
                    "event": "data_query_routing_explicit_override",
                    "topic_override": topic_override,
                    "route_topic": route.topic,
                    "route_collection": route.collection,
                },
            )
        else:
            route = choose_route_for_query(raw_text, classifier)
            route_source = "classifier_or_text"

        # --- METADATA FROM ROUTE ----------------------------------------------
        if hasattr(route, "to_entity") and callable(getattr(route, "to_entity")):
            entity_meta: Dict[str, Any] = route.to_entity()
        else:
            entity_meta = {
                "id": getattr(route, "id", None) or route.topic or route.collection,
                "topic_key": getattr(
                    route,
                    "topic_key",
                    getattr(route, "topic", getattr(route, "collection", None)),
                ),
                "table": getattr(route, "table", getattr(route, "collection", None)),
                "api_route": getattr(route, "api_route", route.resolved_path),
                "display_name": getattr(
                    route,
                    "display_name",
                    (
                        route.topic.replace("_", " ")
                        if isinstance(route.topic, str)
                        else getattr(route, "collection", None)
                    ),
                ),
                "synonyms": getattr(route, "synonyms", []) or [],
                "description": getattr(route, "description", None),
                "collection": route.collection,
                "view_name": route.view_name,
                "path": route.path,
                "detail_path": route.detail_path,
                "base_url": route.base_url,
                "default_params": route.default_params,
            }

        logger.debug(
            "[data_query:schema] metadata derived from route",
            extra={
                "event": "data_query_schema_from_route",
                "route_topic": route.topic,
                "schema_id": entity_meta.get("id"),
                "schema_table": entity_meta.get("table"),
                "schema_topic_key": entity_meta.get("topic_key"),
                "synonym_count": len(entity_meta.get("synonyms") or []),
            },
        )

        # --- PARAMS + BASE URL -------------------------------------------------
        raw_base_url_from_cfg = dq_cfg.get("base_url")
        raw_base_url_from_route = getattr(route, "base_url", None)

        if raw_base_url_from_cfg:
            base_url_source = "data_query_cfg"
            raw_base_url = raw_base_url_from_cfg
        elif raw_base_url_from_route:
            base_url_source = "route"
            raw_base_url = raw_base_url_from_route
        else:
            base_url_source = "agent_default"
            raw_base_url = self.BASE_URL

        if not raw_base_url:
            logger.error(
                "[data_query:routing] no base_url configured at any level",
                extra={
                    "event": "data_query_no_base_url",
                    "route_topic": route.topic,
                    "route_collection": route.collection,
                },
            )
            raise RuntimeError(
                f"No base_url configured for route {route.topic!r} and "
                "no OSSS_BACKEND_BASE_URL default is set."
            )

        base_url = raw_base_url.rstrip("/")

        if not base_url.startswith(("http://", "https://")):
            logger.error(
                "[data_query:routing] invalid base_url",
                extra={
                    "event": "data_query_invalid_base_url",
                    "raw_base_url": raw_base_url,
                    "normalized_base_url": base_url,
                    "base_url_source": base_url_source,
                    "route_id": getattr(route, "id", None),
                    "route_topic": route.topic,
                    "route_collection": route.collection,
                },
            )
            raise RuntimeError(
                f"Invalid base_url for route {getattr(route, 'id', route.topic)!r}: "
                f"{raw_base_url!r} (expected something like 'http://localhost:8000')"
            )

        params: Dict[str, Any] = {}
        params.update(route.default_params or {})
        params.update(dq_cfg.get("default_params") or {})
        params.update(exec_cfg.get("http_query_params") or {})

        entity_meta["base_url"] = base_url
        entity_meta["default_params"] = params

        logger.info(
            "[data_query:routing] final route resolved",
            extra={
                "event": "data_query_final_route_resolved",
                "route_source": route_source,
                "base_url_source": base_url_source,
                "topic": route.topic,
                "collection": route.collection,
                "view": route.view_name,
                "path": route.resolved_path,
                "base_url": base_url,
                "params": params,
                "schema_topic_key": entity_meta.get("topic_key"),
            },
        )

        # --- HTTP CALL ---------------------------------------------------------
        client = BackendAPIClient(BackendAPIConfig(base_url=base_url))
        request_url = f"{base_url}{route.resolved_path}"

        logger.info(
            "[data_query:http] issuing collection GET",
            extra={
                "event": "data_query_http_collection_get",
                "collection": route.collection,
                "url": request_url,
                "skip": params.get("skip"),
                "limit": params.get("limit"),
                "params": params,
            },
        )

        try:
            rows = await client.get_collection(
                route.collection,
                skip=int(params.get("skip", 0)),
                limit=int(params.get("limit", 100)),
                params={k: v for k, v in params.items() if k not in ("skip", "limit")},
            )
            logger.info(
                "[data_query:http] received response",
                extra={
                    "event": "data_query_http_collection_response",
                    "collection": route.collection,
                    "row_count": len(rows),
                    "url": request_url,
                },
            )
            payload = {
                "ok": True,
                "view": route.view_name,
                "source": "http",
                "url": request_url,
                "status_code": 200,
                "row_count": len(rows),
                "rows": rows,
                "entity": entity_meta,
            }
        except Exception as exc:
            logger.exception(
                "[data_query:http] request failed",
                extra={
                    "event": "data_query_http_collection_error",
                    "collection": route.collection,
                    "url": request_url,
                },
            )
            payload = {
                "ok": False,
                "view": route.view_name,
                "source": "http",
                "url": request_url,
                "status_code": None,
                "row_count": 0,
                "rows": [],
                "error": str(exc),
                "entity": entity_meta,
            }

        # --- SINGLE CHANNEL KEY FOR THIS RESULT -------------------------------
        topic_key = (
            route.topic.strip()
            if isinstance(route.topic, str)
            else ""
        )
        if topic_key:
            channel_key = f"{self.name}:{topic_key}"
        else:
            channel_key = self.name  # "data_query"

        logger.info(
            "[data_query:output] using single channel key for agent_output",
            extra={
                "event": "data_query_output_channel_key",
                "channel_key": channel_key,
                "route_topic": route.topic,
                "route_view_name": route.view_name,
            },
        )

        # --- STORE IN CONTEXT --------------------------------------------------
        context.execution_state[route.resolved_store_key] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.name}:{route.view_name}"] = payload

        logger.debug(
            "[data_query] stored payload in execution_state",
            extra={
                "event": "data_query_payload_stored",
                "store_key": route.resolved_store_key,
            },
        )

        # --- OUTPUT FOR UI -----------------------------------------------------
        if payload.get("ok"):
            md = _rows_to_markdown_table(payload["rows"])
            meta_block = {
                "view": payload["view"],
                "row_count": payload["row_count"],
                "url": payload["url"],
                "status_code": payload["status_code"],
                "entity": entity_meta,
            }

            # Canonical structured-output object for data_query
            canonical_output = {
                # These three are aliases so downstream code can pick whichever it expects
                "table_markdown": md,
                "markdown": md,
                "content": md,
                "meta": meta_block,
                "action": "query",
                "intent": "action",
            }

            logger.debug(
                "[data_query:output] adding successful agent_output",
                extra={
                    "event": "data_query_output_success",
                    "markdown_length": len(md),
                },
            )

            # ✅ Single agent_output channel to avoid duplicate tables
            context.add_agent_output(channel_key, canonical_output)

            # Optional: also mirror into structured_outputs under same key
            structured_outputs = context.execution_state.setdefault("structured_outputs", {})
            structured_outputs[channel_key] = canonical_output

        else:
            logger.debug(
                "[data_query:output] adding failed agent_output",
                extra={
                    "event": "data_query_output_failure",
                    "error": payload.get("error"),
                },
            )
            context.add_agent_output(
                channel_key,
                {
                    "content": f"**data_query failed**: {payload.get('error', 'unknown error')}",
                    "meta": payload,
                    "action": "query",
                    "intent": "action",
                },
            )

        logger.info(
            "[data_query] run() completed",
            extra={
                "event": "data_query_run_completed",
                "view": route.view_name,
                "row_count": payload.get("row_count"),
                "ok": payload.get("ok"),
            },
        )
        return context

    async def invoke(self, context: AgentContext) -> AgentContext:
        return await self.run(context)
