from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, List, Optional, Tuple
import re
from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from OSSS.ai.agents.data_query.config import (
    DataQueryRoute,
    resolve_route,
    find_route_for_text,
)
from OSSS.ai.services.backend_api_client import BackendAPIClient, BackendAPIConfig

from OSSS.ai.agents.data_query.queryspec import QuerySpec, FilterCondition
from OSSS.ai.agents.data_query.query_metadata import DEFAULT_QUERY_SPECS
from OSSS.ai.agents.data_query.text_filters import parse_text_filters
# 🔧 IMPORTANT: use the same logger import style as other modules
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

DEFAULT_BASE_URL = os.getenv("OSSS_BACKEND_BASE_URL", "http://app:8000")


# Minimum topic_confidence from classifier to trust its topic mapping.
# If below this, we fall back to text-based route matching.
MIN_TOPIC_CONFIDENCE = float(os.getenv("OSSS_DATAQUERY_MIN_TOPIC_CONFIDENCE", "0.15"))

# -----------------------------------------------------------------------------
# CONSENT CREATION WIZARD CONFIG
# -----------------------------------------------------------------------------

class ConsentFields:
    STUDENT = "student"
    GUARDIAN = "guardian"
    CONSENT_TYPE = "consent_type"
    STATUS = "status"
    EFFECTIVE_DATE = "effective_date"
    NOTES = "notes"


CONSENT_REQUIRED_FIELDS: List[str] = [
    ConsentFields.STUDENT,
    ConsentFields.GUARDIAN,
    ConsentFields.CONSENT_TYPE,
    ConsentFields.STATUS,
]

CONSENT_OPTIONAL_FIELDS: List[str] = [
    ConsentFields.EFFECTIVE_DATE,
    ConsentFields.NOTES,
]

CONSENT_FIELD_PROMPTS: Dict[str, str] = {
    ConsentFields.STUDENT: "Which student is this consent for? Please provide the full student name.",
    ConsentFields.GUARDIAN: "Who gave this consent? Please provide the guardian’s name or relationship.",
    ConsentFields.CONSENT_TYPE: (
        "What kind of consent is this? For example: media release, field trip, technology use, etc."
    ),
    ConsentFields.STATUS: "Was consent granted or denied?",
    ConsentFields.EFFECTIVE_DATE: (
        "What date should this consent be effective from? If it’s today, you can just say 'today'."
    ),
    ConsentFields.NOTES: "Any notes you’d like to include? You can say 'no' if there are none.",
}

CONSENT_FIELD_PROMPTS: Dict[str, str] = {
    ConsentFields.STUDENT: "Which student is this consent for? Please provide the full student name.",
    ConsentFields.GUARDIAN: "Who gave this consent? Please provide the guardian’s name or relationship.",
    ConsentFields.CONSENT_TYPE: (
        "What kind of consent is this? For example: media release, field trip, technology use, etc."
    ),
    ConsentFields.STATUS: "Was consent granted or denied?",
    ConsentFields.EFFECTIVE_DATE: (
        "What date should this consent be effective from? If it’s today, you can just say 'today'."
    ),
    ConsentFields.NOTES: "Any notes you’d like to include? You can say 'no' if there are none.",
}

# Map logical filter ops → backend suffixes
OP_MAP: Dict[str, str] = {
    # equality handled specially (no suffix)
    "contains": "icontains",
    "icontains": "icontains",
    # ✅ IMPORTANT: align with API, no more "istartswith"
    "startswith": "startswith",
    "prefix": "startswith",
    "gt": "gt",
    "greater_than": "gt",
    "gte": "gte",
    "greater_or_equal": "gte",
    "lt": "lt",
    "less_than": "lt",
    "lte": "lte",
    "less_or_equal": "lte",
    "in": "in",
    "one_of": "in",
}


def _apply_filters_to_params(
    base_params: Dict[str, Any],
    filters: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Merge structured filters into HTTP params.

    Expected filter shape:

        {
            "field": "consent_type",
            "op": "startswith",   # eq|equals|contains|startswith|gt|gte|lt|lte|in
            "value": "D"
        }

    Suffixes are mapped via OP_MAP to whatever your backend actually expects.
    """
    if not filters:
        return base_params

    params = dict(base_params)

    for f in filters:
        if not isinstance(f, dict):
            continue

        field = (f.get("field") or "").strip()
        op = (f.get("op") or "eq").strip().lower()
        value = f.get("value", None)

        if not field or value is None:
            continue

        # 🔧 Normalize quoted string values like "'D'" or "\"D\""
        if isinstance(value, str):
            v = value.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in {"'", '"'}:
                value = v[1:-1]

        # Equality → no suffix
        if op in {"eq", "equals"}:
            key = field

        # IN / ONE_OF → list → CSV, with __in suffix
        elif op in {"in", "one_of"}:
            suffix = OP_MAP.get(op, "in")
            key = f"{field}__{suffix}"
            if isinstance(value, list):
                value = ",".join(str(v) for v in value)

        else:
            # All other ops: use suffix from OP_MAP, fallback to op itself
            suffix = OP_MAP.get(op, op)
            key = f"{field}__{suffix}"

        params[key] = value

    return params


def _detect_create_intent(raw_user_input: str, refined_text: str) -> bool:
    """
    Lexical gate to detect 'add/create consent' style intents, even if the
    classifier doesn't explicitly say 'create'.

    We look across both the original user input and the refined text.
    """
    text_combined = f"{raw_user_input} {refined_text}".lower()

    create_tokens = ("create", "add")
    consent_tokens = ("consent", "consents", "concent", "concents")

    has_create_or_add = any(tok in text_combined for tok in create_tokens)
    has_consent_word = any(tok in text_combined for tok in consent_tokens)

    return has_create_or_add and has_consent_word


def _is_consents_create_route(route: DataQueryRoute) -> bool:
    """
    Heuristic to detect that this DataQueryRoute is for creating a consent
    record, rather than just querying consents.

    You can tighten this once your DataQueryRoute has explicit operation flags.
    """
    name = getattr(route, "name", None)
    operation = getattr(route, "operation", None)
    topic = getattr(route, "topic", None)
    collection = getattr(route, "collection", None)

    if str(name or "").lower() in {"consents_create", "consent_create"}:
        return True
    if str(operation or "").lower() == "create" and str(collection or "") == "consents":
        return True
    if str(operation or "").lower() == "create" and str(topic or "") == "consents":
        return True
    return False


def _normalize_status_answer(answer: str) -> str:
    """
    Normalize user free-text answer into a canonical consent status string.
    """
    text = (answer or "").strip().lower()
    if not text:
        return ""

    if any(w in text for w in ["grant", "granted", "yes", "yep", "allow", "allowed", "approve", "approved", "ok", "okay"]):
        return "granted"
    if any(w in text for w in ["deny", "denied", "no", "nope", "disallow", "refuse", "decline"]):
        return "denied"

    # Fallback: return raw text so you can see what user typed.
    return text


def _consent_wizard_missing_fields(payload: Dict[str, Any]) -> List[str]:
    """
    Compute which required fields are still missing in the wizard payload.
    """
    missing: List[str] = []
    for key in CONSENT_REQUIRED_FIELDS:
        value = payload.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(key)
    return missing


def _summarize_consent_payload(payload: Dict[str, Any]) -> str:
    """
    Human-readable summary for confirmation message.
    """
    lines = [
        f"- **Student**: {payload.get(ConsentFields.STUDENT) or '_not set_'}",
        f"- **Guardian**: {payload.get(ConsentFields.GUARDIAN) or '_not set_'}",
        f"- **Type**: {payload.get(ConsentFields.CONSENT_TYPE) or '_not set_'}",
        f"- **Status**: {payload.get(ConsentFields.STATUS) or '_not set_'}",
        f"- **Effective date**: {payload.get(ConsentFields.EFFECTIVE_DATE) or 'today'}",
        f"- **Notes**: {payload.get(ConsentFields.NOTES) or 'none'}",
    ]
    return "\n".join(lines)


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

        # src/OSSS/ai/agents/data_query/agent.py

    # inside DataQueryAgent

    # inside DataQueryAgent

    async def _enrich_person_name_for_consents(
            self,
            client: BackendAPIClient,
            rows_full: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        For consents results, look up each person_id in the backend API and
        add a 'person_name' field to each row.

        Uses the provided BackendAPIClient; does NOT assume async context-manager
        support on the client.
        """
        if not rows_full:
            return rows_full

        # Collect unique person_ids
        person_ids = {
            row.get("person_id")
            for row in rows_full
            if row.get("person_id") is not None
        }
        if not person_ids:
            return rows_full

        try:
            persons_by_id: Dict[Any, Dict[str, Any]] = {}

            # Fetch each person; you can optimize to a bulk endpoint later if needed
            for pid in person_ids:
                try:
                    # Adjust path if your people endpoint is different
                    person = await client.get_json(f"/api/persons/{pid}")
                    if person:
                        persons_by_id[pid] = person
                except Exception as inner_exc:  # per-person log, but non-fatal
                    logger.warning(
                        "[data_query:consents] Failed to fetch person for consent row",
                        extra={
                            "event": "data_query_consents_fetch_person_failed",
                            "person_id": pid,
                            "error_type": type(inner_exc).__name__,
                            "error_message": str(inner_exc),
                        },
                    )

            # Attach person_name to each row where we have a match
            for row in rows_full:
                pid = row.get("person_id")
                person = persons_by_id.get(pid)
                if not person:
                    continue

                full_name = (
                        person.get("full_name")
                        or " ".join(
                    part
                    for part in [
                        person.get("first_name"),
                        person.get("last_name"),
                    ]
                    if part
                )
                )

                if full_name:
                    row["person_name"] = full_name

            # Log a quick sample of the enriched keys
            logger.info(
                "[data_query:consents] enrichment complete",
                extra={
                    "event": "data_query_consents_enrichment_complete",
                    "row_keys_sample": list(rows_full[0].keys()) if rows_full else [],
                },
            )

            return rows_full

        except Exception as exc:
            # Non-fatal: log and return original rows
            logger.warning(
                "[data_query:consents] Failed to enrich person_name from backend",
                extra={
                    "event": "data_query_consents_enrich_person_name_failed",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
            )
            return rows_full

    def _shrink_to_ui_defaults(
            self,
            rows_full: List[Dict[str, Any]],
            query_spec: QuerySpec,
    ) -> List[Dict[str, Any]]:
        if not rows_full:
            return []

        # --- 1) Start from projections (if any) or keys from first row ---
        if query_spec.projections:
            raw_keys = list(query_spec.projections)
        else:
            raw_keys = list(rows_full[0].keys())

        # --- 2) Normalize keys so they're plain strings, not Projection objects ---
        base_keys: List[str] = []
        for k in raw_keys:
            if isinstance(k, str):
                base_keys.append(k)
                continue

            # Handle Projection-like objects defensively
            alias = getattr(k, "alias", None)
            name = (
                    alias
                    or getattr(k, "field", None)
                    or getattr(k, "column", None)
                    or getattr(k, "name", None)
            )

            if isinstance(name, str):
                base_keys.append(name)

        # Optional: de-duplicate while preserving order
        seen: set[str] = set()
        deduped_keys: List[str] = []
        for k in base_keys:
            if k not in seen:
                seen.add(k)
                deduped_keys.append(k)
        base_keys = deduped_keys

        # --- 2b) NEW: include any *_name fields found in the actual rows -----
        # This fixes the "person_id but not person_name" issue when projections
        # don't know about enrichment/join-added fields.
        sample_row = rows_full[0]
        extra_name_keys: List[str] = []
        for k in sample_row.keys():
            if (
                    isinstance(k, str)
                    and k.endswith("_name")
                    and k not in base_keys
            ):
                extra_name_keys.append(k)

        if extra_name_keys:
            base_keys.extend(extra_name_keys)

        # --- 3) Generic UX rule: prefer *_name over *_id when both exist ---
        # e.g. person_name vs person_id, student_name vs student_id, etc.
        name_keys = {k for k in base_keys if k.endswith("_name")}
        id_keys_to_drop = set()
        for name_key in name_keys:
            stem = name_key[:-5]  # strip '_name'
            id_key = f"{stem}_id"
            if id_key in base_keys:
                id_keys_to_drop.add(id_key)

        if id_keys_to_drop:
            base_keys = [k for k in base_keys if k not in id_keys_to_drop]

        # --- 3b) Log what we ended up with for debugging --------------------
        logger.info(
            "[data_query:render] compact column selection",
            extra={
                "event": "data_query_compact_columns_selected",
                "base_collection": query_spec.base_collection,
                "columns": base_keys,
            },
        )

        # --- 4) Build compact rows using only string keys ---
        compact_rows: List[Dict[str, Any]] = []
        for row in rows_full:
            compact_rows.append({k: row.get(k) for k in base_keys if k in row})

        return compact_rows

    # -------------------------------------------------------------------------
    # QUERY EXECUTION (QuerySpec → HTTP calls → joined/projection rows)
    # -------------------------------------------------------------------------

    async def _execute_queryspec_http(
            self,
            client: BackendAPIClient,
            route: DataQueryRoute,
            query_spec: QuerySpec,
            params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Execute a QuerySpec against a REST backend.

        - Fetch base collection rows.
        - Apply any configured joins (e.g., consents.person_id -> persons.full_name).
        - Return enriched rows.
        """
        # 1) Fetch base rows
        base_path = getattr(route, "resolved_path", None) or getattr(route, "path", None) or ""
        base_rows = await client.get_json(base_path, params=params)  # adjust to your method name

        if not base_rows or not query_spec.joins:
            return base_rows or []

        # 2) For now, handle only the first join (you can generalize later)
        #    In your case, consents → persons
        join = query_spec.joins[0]

        if join.target_collection == "persons" and join.source_field == "person_id":
            # Collect unique person_ids from base rows
            person_ids = {
                row.get(join.source_field)
                for row in base_rows
                if row.get(join.source_field)
            }
            if not person_ids:
                return base_rows

            # 3) Fetch persons in one shot; adjust to your backend filter style
            # Example assumes /api/persons?ids=uuid1,uuid2,uuid3
            persons_path = "/api/persons"
            person_params = {"ids": ",".join(sorted(person_ids))}
            persons = await client.get_json(persons_path, params=person_params)

            # Build lookup: id -> "Last, First"
            person_lookup: Dict[str, str] = {}
            for p in persons:
                pid = p.get("id")
                if not pid:
                    continue
                first = p.get("first_name") or ""
                last = p.get("last_name") or ""
                name = (last + ", " + first).strip(", ").strip()
                person_lookup[pid] = name or pid  # fallback to id if missing

            # 4) Enrich base rows
            enriched: List[Dict[str, Any]] = []
            for row in base_rows:
                new_row = dict(row)
                pid = row.get("person_id")
                if pid:
                    new_row["person_name"] = person_lookup.get(pid, pid)
                    # Optional: drop person_id so the UI just sees person_name
                    new_row.pop("person_id", None)
                enriched.append(new_row)

            return enriched

        # If join is something else we haven't explicitly handled, just return base rows
        return base_rows

    async def _merge_join_results(
        self,
        client: BackendAPIClient,
        base_rows: List[Dict[str, Any]],
        query_spec: QuerySpec,
    ) -> List[Dict[str, Any]]:
        """
        For each Join in QuerySpec, fetch the remote collection using an
        __in filter on the join.to_field and attach the matching object
        as a nested dict on each base row:

            row[join.alias or join.to_collection] = remote_row
        """
        if not query_spec.joins:
            return base_rows

        # Work on a copy to avoid mutating caller's list in unexpected ways
        rows = [dict(row) for row in base_rows]

        for j in query_spec.joins:
            from_collection = j.from_collection
            base_collection = query_spec.base_collection

            # For now, keep it simple: only handle joins where from_collection == base_collection
            if from_collection and from_collection != base_collection:
                logger.info(
                    "[data_query:queryspec] skipping join with non-base from_collection",
                    extra={
                        "event": "data_query_join_skip_non_base",
                        "from_collection": from_collection,
                        "base_collection": base_collection,
                        "to_collection": j.to_collection,
                    },
                )
                continue

            fk_values = {
                row.get(j.from_field)
                for row in rows
                if row.get(j.from_field) is not None
            }

            if not fk_values:
                logger.info(
                    "[data_query:queryspec] no FK values found for join; skipping",
                    extra={
                        "event": "data_query_join_no_fk_values",
                        "from_field": j.from_field,
                        "to_collection": j.to_collection,
                    },
                )
                continue

            # Assume the backend supports __in for the join.to_field (e.g. id__in=1,2,3)
            in_key = f"{j.to_field}__in"
            join_params = {in_key: ",".join(str(v) for v in fk_values)}

            logger.info(
                "[data_query:queryspec] fetching join collection",
                extra={
                    "event": "data_query_join_fetch",
                    "to_collection": j.to_collection,
                    "from_field": j.from_field,
                    "to_field": j.to_field,
                    "param_key": in_key,
                    "fk_count": len(fk_values),
                },
            )

            join_rows = await client.get_collection(
                j.to_collection,
                skip=0,
                limit=len(fk_values),
                params=join_params,
            )

            # Index by the join.to_field on the remote side
            index: Dict[Any, Dict[str, Any]] = {}
            for r in join_rows:
                key = r.get(j.to_field)
                if key is not None and key not in index:
                    index[key] = r

            nested_key = j.alias or j.to_collection

            for row in rows:
                fk_val = row.get(j.from_field)
                if fk_val is None:
                    continue
                remote = index.get(fk_val)
                if remote is not None:
                    # attach as nested object
                    row[nested_key] = remote

        return rows

    def _apply_projections(
            self,
            rows: List[Dict[str, Any]],
            query_spec: QuerySpec,
    ) -> List[Dict[str, Any]]:
        """
        Apply QuerySpec.projections to the (possibly join-enriched) rows.

        - If no projections are defined, return the original rows.
        - For base_collection projections, pull directly from row[field].
        - For joined projections, look for the nested object attached by
          _merge_join_results under join.alias or join.to_collection.

        This returns the *full* projection row; UI shrinking is handled separately.
        """
        if not rows:
            return []

        if not query_spec.projections:
            # No projections configured → return full rows as-is
            return rows

        base_collection = query_spec.base_collection
        joins_by_collection = {j.to_collection: j for j in query_spec.joins}

        projected_rows: List[Dict[str, Any]] = []

        for row in rows:
            out: Dict[str, Any] = {}

            for proj in query_spec.projections:
                alias = proj.alias or proj.field

                # Base collection fields: get directly from row
                if proj.collection == base_collection:
                    out[alias] = row.get(proj.field)
                    continue

                # Joined collections: use the nested object
                join = joins_by_collection.get(proj.collection)
                if not join:
                    continue

                nested_key = join.alias or join.to_collection
                nested = row.get(nested_key)

                if isinstance(nested, dict):
                    out[alias] = nested.get(proj.field)

            projected_rows.append(out)

        return projected_rows

    def get_node_definition(self) -> LangGraphNodeDefinition:
        return LangGraphNodeDefinition(
            node_type="tool",
            agent_name=self.name,
            dependencies=["refiner"],
        )

    # -------------------------------------------------------------------------
    # CONSENT WIZARD INTERNAL HELPERS
    # -------------------------------------------------------------------------
    def _get_consent_wizard_state(self, context: AgentContext) -> Dict[str, Any]:
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        return exec_state.get("consent_wizard") or {}

    def _set_consent_wizard_state(self, context: AgentContext, state: Optional[Dict[str, Any]]) -> None:
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        if state:
            exec_state["consent_wizard"] = state
        else:
            exec_state.pop("consent_wizard", None)
        context.execution_state = exec_state

    def _consent_wizard_channel_key(self) -> str:
        # Single logical channel for consent wizard UX
        return f"{self.name}:consent_wizard"

    async def _start_consent_wizard(
        self,
        context: AgentContext,
        route: DataQueryRoute,
        base_url: str,
        entity_meta: Dict[str, Any],
    ) -> AgentContext:
        """
        First call into consents_create route: initialize wizard payload and
        ask for the first required field.
        """
        logger.info(
            "[data_query:consent_wizard] starting consent creation wizard",
            extra={
                "event": "data_query_consent_wizard_start",
                "route_name": getattr(route, "name", None),
                "topic": getattr(route, "topic", None),
                "collection": getattr(route, "collection", None),
            },
        )

        payload: Dict[str, Any] = {
            "source": "ai_data_query",
            "base_url": base_url,
            "entity_id": entity_meta.get("id"),
        }

        missing = _consent_wizard_missing_fields(payload)
        # At start, this will be all required fields
        next_field = missing[0] if missing else None

        wizard_state: Dict[str, Any] = {
            "pending_action": "collect",
            "payload": payload,
            "required_fields": list(CONSENT_REQUIRED_FIELDS),
            "optional_fields": list(CONSENT_OPTIONAL_FIELDS),
            "current_field": next_field,
            "route_info": {
                "name": getattr(route, "name", None),
                "collection": getattr(route, "collection", None),
                "topic": getattr(route, "topic", None),
                "resolved_path": getattr(route, "resolved_path", None),
                "base_url": base_url,
            },
        }
        self._set_consent_wizard_state(context, wizard_state)

        channel_key = self._consent_wizard_channel_key()

        if next_field:
            prompt = CONSENT_FIELD_PROMPTS.get(
                next_field,
                "I need a bit more information. Please provide the next detail.",
            )
            context.add_agent_output(
                channel_key,
                {
                    "content": (
                        "I can create a consent record, but I need a few details first.\n\n"
                        + prompt
                    ),
                    "meta": {
                        "action": "consent_wizard",
                        "step": "collect_field",
                        "current_field": next_field,
                        "missing_fields": missing,
                    },
                    "intent": "action",
                },
            )
        else:
            # Extremely unlikely, but fall back to immediate confirmation
            summary = _summarize_consent_payload(payload)
            wizard_state["pending_action"] = "confirm"
            self._set_consent_wizard_state(context, wizard_state)
            context.add_agent_output(
                channel_key,
                {
                    "content": (
                        "Here’s the consent I’m ready to create:\n\n"
                        f"{summary}\n\n"
                        "Type 'confirm' to save this consent or 'cancel' to abort."
                    ),
                    "meta": {
                        "action": "consent_wizard",
                        "step": "confirm",
                    },
                    "intent": "action",
                },
            )

        return context

    async def _continue_consent_wizard(
        self,
        context: AgentContext,
        wizard_state: Dict[str, Any],
        user_text: str,
    ) -> AgentContext:
        """
        Continue the consent wizard: either collect the next field or handle
        the final confirmation.
        """
        channel_key = self._consent_wizard_channel_key()
        pending_action = wizard_state.get("pending_action")
        payload: Dict[str, Any] = wizard_state.get("payload") or {}

        # ---------------------------------------------------------------------
        # CONFIRMATION STEP
        # ---------------------------------------------------------------------
        if pending_action == "confirm":
            answer = (user_text or "").strip().lower()
            logger.info(
                "[data_query:consent_wizard] confirmation step",
                extra={
                    "event": "data_query_consent_wizard_confirm",
                    "answer": answer,
                },
            )
            if answer in {"yes", "y", "confirm", "ok", "okay"}:
                # ✅ Ready for actual creation. We DO NOT guess BackendAPIClient
                # methods here – we just park the payload so another component
                # can invoke a write.
                exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
                exec_state["consent_create_ready"] = payload
                context.execution_state = exec_state

                # Clear wizard state
                self._set_consent_wizard_state(context, None)

                summary = _summarize_consent_payload(payload)
                context.add_agent_output(
                    channel_key,
                    {
                        "content": (
                            "Great, I’ve collected everything needed for this consent:\n\n"
                            f"{summary}\n\n"
                            "The payload is ready for creation in the backend."
                        ),
                        "meta": {
                            "action": "consent_wizard",
                            "step": "confirmed",
                        },
                        "intent": "action",
                    },
                )

                # NOTE: This is where you can later plug in:
                #   client = BackendAPIClient(BackendAPIConfig(base_url=payload['base_url']))
                #   await client.create_consent(payload)
                # and then update the message to reflect actual DB write.
                return context

            # User cancelled
            self._set_consent_wizard_state(context, None)
            context.add_agent_output(
                channel_key,
                {
                    "content": "Okay, I won’t create this consent record.",
                    "meta": {
                        "action": "consent_wizard",
                        "step": "cancelled",
                    },
                    "intent": "action",
                },
            )
            return context

        # ---------------------------------------------------------------------
        # FIELD COLLECTION STEP
        # ---------------------------------------------------------------------
        current_field = wizard_state.get("current_field")
        if not current_field:
            # If for some reason we lost track, recompute missing and restart.
            missing = _consent_wizard_missing_fields(payload)
            current_field = missing[0] if missing else None
            wizard_state["current_field"] = current_field
            self._set_consent_wizard_state(context, wizard_state)

        logger.info(
            "[data_query:consent_wizard] collecting field",
            extra={
                "event": "data_query_consent_wizard_collect_field",
                "current_field": current_field,
                "user_text": user_text,
            },
        )

        answer = (user_text or "").strip()

        if current_field == ConsentFields.STATUS:
            payload[ConsentFields.STATUS] = _normalize_status_answer(answer)
        elif current_field == ConsentFields.NOTES:
            payload[ConsentFields.NOTES] = "" if answer.lower() in {"no", "none"} else answer
        elif current_field == ConsentFields.EFFECTIVE_DATE:
            # Store raw; backend or later logic can normalize "today" etc.
            payload[ConsentFields.EFFECTIVE_DATE] = answer or "today"
        else:
            # student, guardian, consent_type
            payload[current_field] = answer

        wizard_state["payload"] = payload

        # Recompute missing required fields
        missing = _consent_wizard_missing_fields(payload)

        if missing:
            # Ask next required field
            next_field = missing[0]
            wizard_state["current_field"] = next_field
            wizard_state["pending_action"] = "collect"
            self._set_consent_wizard_state(context, wizard_state)

            prompt = CONSENT_FIELD_PROMPTS.get(
                next_field,
                "Please provide the next detail for this consent.",
            )

            context.add_agent_output(
                channel_key,
                {
                    "content": prompt,
                    "meta": {
                        "action": "consent_wizard",
                        "step": "collect_field",
                        "current_field": next_field,
                        "missing_fields": missing,
                    },
                    "intent": "action",
                },
            )
            return context

        # All required fields are present → move to confirmation
        wizard_state["pending_action"] = "confirm"
        wizard_state["current_field"] = None
        self._set_consent_wizard_state(context, wizard_state)

        summary = _summarize_consent_payload(payload)
        context.add_agent_output(
            channel_key,
            {
                "content": (
                    "Here’s the consent I’m ready to create:\n\n"
                    f"{summary}\n\n"
                    "Type 'confirm' to save this consent, or 'cancel' to abort."
                ),
                "meta": {
                    "action": "consent_wizard",
                    "step": "confirm",
                },
                "intent": "action",
            },
        )
        return context

    # -------------------------------------------------------------------------
    # MAIN EXECUTION
    # -------------------------------------------------------------------------
    async def run(self, context: AgentContext) -> AgentContext:
        """
        Main data_query entrypoint.

        Now supports:
          - lexical detection of "add/create consent" via `_detect_create_intent`
          - QuerySpec-based filter parsing via `parse_text_filters`
          - merging structured filters + text-derived filters into HTTP params
        """

        # --- EXECUTION CONFIG --------------------------------------------------
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        # ensure we can mutate and the changes persist
        exec_cfg: Dict[str, Any] = exec_state.setdefault("execution_config", {})
        dq_cfg: Dict[str, Any] = exec_cfg.setdefault("data_query", {})

        # Classifier output + refined text (typically after Refiner)
        classifier, raw_text = _get_classifier_and_text_from_context(context)
        raw_text_norm = (raw_text or "").strip()
        raw_text_lower = raw_text_norm.lower()

        # 🔎 ORIGINAL / RAW USER INPUT (pre-refiner), if we have it
        raw_user_input = (exec_state.get("user_question") or "").strip()
        raw_user_lower = raw_user_input.lower()

        # Keep any structured filters passed into execution_config.data_query
        structured_filters_cfg: List[Dict[str, Any]] = dq_cfg.get("filters") or []

        # Existing wizard state → skip routing + structured gating entirely
        consent_wizard_state = exec_state.get("consent_wizard") or {}

        # ----------------------------------------------------------------------
        # 🔑 LEXICAL CREATE-CONSENT DETECTION
        # ----------------------------------------------------------------------
        consent_create_intent = _detect_create_intent(
            raw_user_input=raw_user_input,
            refined_text=raw_text_norm,
        )

        # 🚧 SIMPLE STRUCTURED QUERY GATE
        is_structured_query = raw_text_lower.startswith("query ")
        force_data_query = bool(dq_cfg.get("force"))

        logger.info(
            "[data_query] lexical gate",
            extra={
                "event": "data_query_lexical_gate",
                "raw_text_preview": raw_text_norm[:200],
                "raw_user_preview": raw_user_input[:200],
                "is_structured_query": is_structured_query,
                "force_data_query": force_data_query,
                "has_consent_wizard_state": bool(consent_wizard_state),
                "consent_create_intent": consent_create_intent,
            },
        )

        # ---- SKIP CONDITIONS -------------------------------------------------
        if (
                not is_structured_query
                and not force_data_query
                and not consent_wizard_state
                and not consent_create_intent
        ):
            logger.info(
                "[data_query:routing] skipping: no structured query, no force, "
                "no wizard state, no create-consent trigger",
                extra={
                    "event": "data_query_skip_non_structured",
                    "raw_text_preview": raw_text_norm[:200],
                },
            )
            return context

        # ---- CONSENT WIZARD CONTINUATION ------------------------------------
        if consent_wizard_state:
            logger.info(
                "[data_query:consent_wizard] continuing existing wizard",
                extra={"event": "data_query_consent_wizard_continue"},
            )
            return await self._continue_consent_wizard(
                context,
                consent_wizard_state,
                raw_text_norm or raw_user_input,
            )

        # ---- INTENT RESOLUTION ----------------------------------------------
        state_intent = getattr(context, "intent", None) or exec_state.get("intent")
        classifier_intent = (
            classifier.get("intent") if isinstance(classifier, dict) else None
        )
        intent_raw = state_intent or classifier_intent
        intent = (intent_raw or "").strip().lower() or None

        # 💡 If lexical consent-create detected and there's no strong conflicting intent,
        # treat this as a create.
        if consent_create_intent and intent not in {"create", "update", "delete"}:
            intent = "create"

        topic_override = dq_cfg.get("topic")

        logger.info(
            "[data_query] run() begin",
            extra={
                "event": "data_query_run_begin",
                "intent": intent,
                "topic_override": topic_override,
                "raw_text_preview": raw_text_norm[:200],
                "raw_user_preview": raw_user_input[:200],
            },
        )

        logger.debug(
            "[data_query] run() begin (debug)",
            extra={
                "event": "data_query_run_begin_debug",
                "intent": intent,
                "topic_override": topic_override,
                "raw_text": raw_text_norm,
                "raw_user_input": raw_user_input,
                "classifier": classifier,
            },
        )

        # ---- ROUTE SELECTION -------------------------------------------------
        # 1️⃣ Explicit override always wins
        if topic_override:
            route = resolve_route(topic_override, intent=intent)
            route_source = "explicit_override"

        # 2️⃣ Lexical create-consent → bias toward consents route if possible
        elif consent_create_intent:
            route = None
            route_source = "consent_keyword_gate"

            try:
                route = resolve_route("consents", intent="create")
            except Exception:
                route = None

            if route is None:
                try:
                    route = resolve_route("consents", intent=intent)
                except Exception:
                    route = None

            # If still nothing → fallback text matching using ORIGINAL user text
            if route is None:
                route = choose_route_for_query(
                    raw_user_input or raw_text_norm,
                    classifier,
                )
                route_source = "consent_keyword_fallback_text"

        # 3️⃣ Default classifier/text routing
        else:
            route = choose_route_for_query(raw_text_norm, classifier)
            route_source = "classifier_or_text"

        logger.info(
            "[data_query:routing] final route resolved",
            extra={
                "event": "data_query_route_resolved",
                "route_source": route_source,
                "route_topic": getattr(route, "topic", None),
                "route_collection": getattr(route, "collection", None),
                "route_name": getattr(route, "name", None),
                "intent": intent,
            },
        )

        # ---- METADATA FROM ROUTE --------------------------------------------
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
                "path": getattr(route, "path", None),
                "detail_path": getattr(route, "detail_path", None),
                "base_url": getattr(route, "base_url", None),
                "default_params": getattr(route, "default_params", None),
            }

        logger.debug(
            "[data_query:schema] metadata derived from route",
            extra={
                "event": "data_query_schema_from_route",
                "route_topic": getattr(route, "topic", None),
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
                    "route_topic": getattr(route, "topic", None),
                    "route_collection": getattr(route, "collection", None),
                },
            )
            raise RuntimeError(
                f"No base_url configured for route {getattr(route, 'topic', None)!r} and "
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
                    "route_topic": getattr(route, "topic", None),
                    "route_collection": getattr(route, "collection", None),
                },
            )
            raise RuntimeError(
                f"Invalid base_url for route {getattr(route, 'id', getattr(route, 'topic', None))!r}: "
                f"{raw_base_url!r} (expected something like 'http://localhost:8000')"
            )

        params: Dict[str, Any] = {}
        params.update(getattr(route, "default_params", None) or {})
        params.update(dq_cfg.get("default_params") or {})
        params.update(exec_cfg.get("http_query_params") or {})

        # ----------------------------------------------------------------------
        # QuerySpec: merge structured filters + text-derived filters
        # ----------------------------------------------------------------------
        collection = getattr(route, "collection", None) or entity_meta.get("collection")
        base_spec = DEFAULT_QUERY_SPECS.get(collection) if collection else None

        if base_spec:
            query_spec = QuerySpec(
                base_collection=base_spec.base_collection,
                projections=list(base_spec.projections),
                joins=list(base_spec.joins),
                filters=list(base_spec.filters),
                synonyms=dict(base_spec.synonyms),
                search_fields=list(base_spec.search_fields),
                default_limit=base_spec.default_limit,
            )
        else:
            query_spec = QuerySpec(base_collection=collection or "")

        # Attach structured filters from execution_config.data_query
        for f in structured_filters_cfg:
            try:
                field = (f.get("field") or "").strip()
                op = (f.get("op") or "eq").strip().lower()
                value = f.get("value", None)
                if field and value is not None:
                    query_spec.filters.append(
                        FilterCondition(field=field, op=op, value=value)
                    )
            except Exception:
                logger.exception(
                    "[data_query:filters] failed to attach cfg filter",
                    extra={"event": "data_query_cfg_filter_attach_error", "filter": f},
                )

        # Parse text-based filters like:
        #   "where last name starts with 'R'"
        #   "where status = active"
        if raw_text_norm:
            before_count = len(query_spec.filters)
            query_spec = parse_text_filters(raw_text_norm, query_spec)
            after_count = len(query_spec.filters)
            if after_count > before_count:
                logger.info(
                    "[data_query:filters] parsed filters from text",
                    extra={
                        "event": "data_query_filters_from_text",
                        "raw_text_preview": raw_text_norm[:200],
                        "new_filter_count": after_count - before_count,
                        "total_filter_count": after_count,
                    },
                )

        # Summarize QuerySpec for observability (avoid storing full dataclass)
        dq_meta = exec_state.setdefault("data_query_step_metadata", {})
        dq_meta["query_spec_summary"] = {
            "base_collection": query_spec.base_collection,
            "projection_count": len(query_spec.projections),
            "join_count": len(query_spec.joins),
            "filter_count": len(query_spec.filters),
            "search_fields": list(query_spec.search_fields),
        }

        # Convert QuerySpec.filters -> dicts for _apply_filters_to_params
        compiled_filters: List[Dict[str, Any]] = [
            {"field": fc.field, "op": fc.op, "value": fc.value}
            for fc in query_spec.filters
        ]

        if compiled_filters:
            logger.info(
                "[data_query:filters] applying filters to HTTP params",
                extra={
                    "event": "data_query_apply_filters",
                    "filter_count": len(compiled_filters),
                    "filters": compiled_filters,
                },
            )
            params = _apply_filters_to_params(params, compiled_filters)

        entity_meta["base_url"] = base_url
        entity_meta["default_params"] = params

        logger.info(
            "[data_query:routing] final route + HTTP config",
            extra={
                "event": "data_query_final_route_resolved",
                "route_source": route_source,
                "topic": getattr(route, "topic", None),
                "collection": getattr(route, "collection", None),
                "view": getattr(route, "view_name", None),
                "path": getattr(route, "resolved_path", None),
                "base_url": base_url,
                "params": params,
                "schema_topic_key": entity_meta.get("topic_key"),
            },
        )

        # ---- CONSENT WIZARD ENTRY POINT -------------------------------------
        if consent_create_intent:
            logger.info(
                "[data_query:consent_wizard] starting wizard via create-consent intent",
                extra={
                    "event": "data_query_consent_wizard_entry",
                    "route_topic": getattr(route, "topic", None),
                    "route_collection": getattr(route, "collection", None),
                    "intent": intent,
                },
            )
            return await self._start_consent_wizard(context, route, base_url, entity_meta)

        # --- HTTP CALL ---------------------------------------------------------
        client = BackendAPIClient(BackendAPIConfig(base_url=base_url))
        request_path = (
                getattr(route, "resolved_path", None)
                or getattr(route, "path", None)
                or ""
        )
        request_url = f"{base_url}{request_path}"

        logger.info(
            "[data_query:http] issuing query via QuerySpec",
            extra={
                "event": "data_query_http_queryspec",
                "collection": getattr(route, "collection", None),
                "url": request_url,
                "skip": params.get("skip"),
                "limit": params.get("limit"),
                "params": params,
            },
        )

        # Ensure these are always defined so we never hit UnboundLocalError
        rows_full: List[Dict[str, Any]] = []
        rows_compact: List[Dict[str, Any]] = []
        status_code: Optional[int] = None
        error: Optional[str] = None

        try:
            rows_full = await self._execute_queryspec_http(
                client=client,
                route=route,
                query_spec=query_spec,
                params=params,
            )

            # Build compact subset for UI
            # 🔍 Special-case enrichment for consents
            if route.topic == "consents":
                rows_full = await self._enrich_person_name_for_consents(client, rows_full)

            rows_compact = self._shrink_to_ui_defaults(rows_full, query_spec)

            status_code = 200  # HTTP layer inside BackendAPIClient succeeded

            logger.info(
                "[data_query:http] received response (after joins/projections)",
                extra={
                    "event": "data_query_http_collection_response",
                    "collection": getattr(route, "collection", None),
                    "row_count": len(rows_full),
                    "url": request_url,
                },
            )

            payload = {
                "ok": True,
                "view": getattr(route, "view_name", None),
                "source": "http",
                "url": request_url,
                "status_code": status_code,
                "row_count": len(rows_full),
                # For backward compatibility: rows = compact set
                "rows": rows_compact,
                # Explicit full/compact for UI layer
                "rows_full": rows_full,
                "rows_compact": rows_compact,
                "entity": entity_meta,
                "projection_mode": "compact",
            }
        except Exception as exc:
            error = str(exc)
            rows_full = []
            rows_compact = []

            logger.exception(
                "[data_query:http] request failed",
                extra={
                    "event": "data_query_http_collection_error",
                    "collection": getattr(route, "collection", None),
                    "url": request_url,
                },
            )
            payload = {
                "ok": False,
                "view": getattr(route, "view_name", None),
                "source": "http",
                "url": request_url,
                "status_code": status_code,
                "row_count": 0,
                "rows": [],
                "rows_full": [],
                "rows_compact": [],
                "error": error,
                "entity": entity_meta,
            }

        # --- SINGLE CHANNEL KEY FOR THIS RESULT -------------------------------
        topic_val = getattr(route, "topic", None)
        topic_key = topic_val.strip() if isinstance(topic_val, str) else ""
        if topic_key:
            channel_key = f"{self.name}:{topic_key}"
        else:
            channel_key = self.name  # "data_query"

        logger.info(
            "[data_query:output] using single channel key for agent_output",
            extra={
                "event": "data_query_output_channel_key",
                "channel_key": channel_key,
                "route_topic": getattr(route, "topic", None),
                "route_view_name": getattr(route, "view_name", None),
            },
        )

        # --- STORE IN CONTEXT --------------------------------------------------
        store_key = (
                getattr(route, "resolved_store_key", None)
                or getattr(route, "view_name", None)
                or "data_query"
        )
        context.execution_state[store_key] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.name}:{getattr(route, 'view_name', None)}"] = payload

        logger.debug(
            "[data_query] stored payload in execution_state",
            extra={
                "event": "data_query_payload_stored",
                "store_key": store_key,
            },
        )

        # --- OUTPUT FOR UI -----------------------------------------------------
        if payload.get("ok"):
            rows_full = payload.get("rows_full") or []
            rows_compact = payload.get("rows_compact") or rows_full

            md_compact = _rows_to_markdown_table(rows_compact)
            md_full = _rows_to_markdown_table(rows_full) if rows_full else md_compact

            meta_block = {
                "view": payload["view"],
                "row_count": payload["row_count"],
                "url": payload["url"],
                "status_code": payload["status_code"],
                "entity": entity_meta,
                "projection_mode": payload.get("projection_mode", "compact"),
                "has_compact": True,
                "has_full": True,
                "table_markdown_compact": md_compact,
                "table_markdown_full": md_full,
            }

            canonical_output = {
                "table_markdown": md_compact,
                "table_markdown_compact": md_compact,
                "table_markdown_full": md_full,
                # default content = compact
                "markdown": md_compact,
                "content": md_compact,
                "meta": meta_block,
                "action": "query",
                "intent": "action",
            }

            logger.debug(
                "[data_query:output] adding successful agent_output",
                extra={
                    "event": "data_query_output_success",
                    "markdown_length": len(md_compact),
                },
            )

            context.add_agent_output(channel_key, canonical_output)

            structured_outputs = context.execution_state.setdefault(
                "structured_outputs", {}
            )
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
                "view": payload.get("view"),
                "row_count": payload.get("row_count"),
                "ok": payload.get("ok"),
            },
        )
        return context
