from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncEngine
import re
import json
from OSSS.ai.context import AgentContext
from OSSS.ai.agents.classifier_agent import ClassifierResult

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

from OSSS.ai.agents.data_query.wizard_config import (
    WizardConfig,
    WizardFieldConfig,
    get_wizard_config_for_collection,
)

logger = get_logger(__name__)


@dataclass
class ExtractedTextFilters:
    filters: List[Dict[str, Any]]
    sort: Optional[Dict[str, Any]]


def _extract_text_filters_from_query(
    raw_text: str,
    route: Optional[DataQueryRoute],
) -> ExtractedTextFilters:
    """
    Lightweight fallback parser for simple text filters that the main
    parse_text_filters(QuerySpec) pipeline might miss.

    Right now this only handles "starts with" patterns like:

        "filter to only show status which start with the letter 'D'"
        "restrict status to those starting with D"

    It returns an ExtractedTextFilters where:
      - .filters is a list[dict] in the same shape expected by _apply_filters_to_params
      - .sort is currently always None (sorting handled elsewhere)
    """
    filters: List[Dict[str, Any]] = []

    if not raw_text:
        return ExtractedTextFilters(filters=[], sort=None)

    text = raw_text.lower()

    for pattern in STARTS_WITH_FILTER_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue

        field = m.group("field")
        value = m.group("value")
        if not field or not value:
            continue

        filters.append(
            {
                "field": field,
                "op": "startswith",
                "value": value,
            }
        )
        break  # only handle the first match for now

    if filters:
        logger.info(
            "[text_filters:fallback] extracted simple 'startswith' filter from text",
            extra={
                "event": "data_query_fallback_text_filters",
                "raw_text_preview": raw_text[:200],
                "route_topic": getattr(route, "topic", None),
                "route_collection": getattr(route, "collection", None),
                "filters": filters,
            },
        )

    # Sorting fallback is handled by _extract_text_sort_from_query separately.
    return ExtractedTextFilters(filters=filters, sort=None)


DEFAULT_BASE_URL = os.getenv("OSSS_BACKEND_BASE_URL", "http://app:8000")


# Minimum topic_confidence from classifier to trust its topic mapping.
# If below this, we fall back to text-based route matching.
MIN_TOPIC_CONFIDENCE = float(os.getenv("OSSS_DATAQUERY_MIN_TOPIC_CONFIDENCE", "0.15"))

# -----------------------------------------------------------------------------
# FILTER OP MAP
# -----------------------------------------------------------------------------

# Map logical filter ops → backend suffixes
OP_MAP: Dict[str, str] = {
    # equality handled specially (no suffix)
    "contains": "contains",     # ⬅ backend expects __contains
    "icontains": "contains",    # ⬅ normalize to contains; backend is already case-insensitive via ilike

    # ✅ IMPORTANT: align with API, no more "istartswith"
    "startswith": "startswith",  # ⬅ backend expects __startswith
    "prefix": "startswith",

    # ✅ NEW: endswith support
    "endswith": "endswith",
    "suffix": "endswith",

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

STARTS_WITH_FILTER_PATTERNS = [
    # Matches: "filter to only show status which start with the letter 'D'"
    re.compile(
        r"(?:filter|restrict)\s+"
        r"(?:to\s+)?(?:only\s+)?(?:show\s+)?"
        r"(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s+"
        r"(?:which|that)?\s*start(?:s)?\s+with"
        r"(?:\s+the\s+letter)?\s+'?(?P<value>[A-Za-z])'?",
        re.IGNORECASE,
    ),
    # Matches: "restrict status to those starting with D"
    re.compile(
        r"restrict\s+"
        r"(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s+"
        r"to\s+those\s+starting\s+with\s+'?(?P<value>[A-Za-z])'?",
        re.IGNORECASE,
    ),
]

# Simple regex to catch phrases like:
#   "sort status in descending order"
#   "sort status descending"
#   "sort status desc"
#   "sort by name"
#   "sorted by name"
#   "sort seasons by name"
#   "sorted seasons by name"
SORT_PATTERN = re.compile(
    r"(?:sort|sorted)\s+"  # "sort " or "sorted "
    r"(?:"  # start either/or
        # Case A: "sort seasons by name"
        r"(?P<collection>[a-zA-Z_][a-zA-Z0-9_]*)\s+by\s+(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)"
        r"|"
        # Case B: "sort by name" or "sort name"
        r"(?:by\s+)?(?P<field_only>[a-zA-Z_][a-zA-Z0-9_]*)"
    r")"
    r"(?:\s+in\s+(?P<long_dir>ascending|descending)\s+order"
    r"|\s+(?P<short_dir>asc|desc))?",  # optional direction
    re.IGNORECASE,
)

LIKE_PATTERN_RE = re.compile(
    r"(?i)^(?:is\s+)?(i?like)\s+(.+)$"
)

REFINED_QUERY_KEY = "refined_query"


def _looks_like_database_query(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return False

    # Strong signals
    if t.startswith("query "):
        return True
    if t.startswith("select "):
        return True

    # Weak but useful: mentions of "table", "database", "record", etc.
    KEYWORDS = (" database", " table", " tables", " row ", " rows ", " records ", "schema")
    if any(kw in t for kw in KEYWORDS):
        return True

    return False


def _extract_refined_text_from_refiner_output(refiner_output: object) -> Optional[str]:
    """
    Normalize whatever the RefinerAgent returned into a clean refined_query string.

    Handles:
    - dict with `refined_query` key (ideal)
    - LLMResponse-like objects with a `.text` attribute that contains JSON or plain text
    - JSON-ish string containing `"refined_query": "..."` even if not perfectly valid JSON
    - plain string which is already the refined query
    """
    # Case 0: LLMResponse-like object with a `text` attribute
    # (but which is NOT already a dict or str).
    if (
        refiner_output is not None
        and not isinstance(refiner_output, (dict, str))
        and hasattr(refiner_output, "text")
    ):
        try:
            text_value = getattr(refiner_output, "text", None)
            if isinstance(text_value, str):
                # Recurse with the underlying text string
                return _extract_refined_text_from_refiner_output(text_value)
        except Exception:
            # If anything goes wrong, fall through to generic handling
            pass

    # Case 1: Already a dict
    if isinstance(refiner_output, dict):
        val = refiner_output.get(REFINED_QUERY_KEY)
        if isinstance(val, str):
            return val.strip()

    # Case 2: String output
    if isinstance(refiner_output, str):
        text = refiner_output.strip()

        # 2a: Try strict JSON first
        if text.startswith("{") and REFINED_QUERY_KEY in text:
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None

            if isinstance(parsed, dict):
                val = parsed.get(REFINED_QUERY_KEY)
                if isinstance(val, str):
                    return val.strip()

        # 2b: Fuzzy regex fallback for JSON-ish responses.
        # Use a non-greedy / safe matcher so we don't swallow the entire
        # LLMResponse repr; we only want up to the next quote.
        if REFINED_QUERY_KEY in text:
            m = re.search(
                r'"refined_query"\s*:\s*"([^"]*)"',
                text,
                flags=re.DOTALL,
            )
            if m:
                return m.group(1).strip()

            # Secondary fallback for single-quoted content like:
            # "refined_query': 'query seasons'"
            m_single = re.search(
                r"[\"']refined_query[\"']\s*:\s*'([^']*)'",
                text,
                flags=re.DOTALL,
            )
            if m_single:
                return m_single.group(1).strip()

        # 2c: Otherwise, treat it as already-refined text
        return text

    # Anything else: no usable refined text
    return None


def _get_classifier_and_text_from_context(
    context: AgentContext,
) -> tuple[dict, str]:
    # canonical classifier dict
    get_clf = getattr(context, "get_classifier_result", None)
    if callable(get_clf):
        classifier = get_clf() or {}
    else:
        exec_state: dict = getattr(context, "execution_state", {}) or {}
        classifier = exec_state.get("classifier_result") or {}
        if not isinstance(classifier, dict):
            classifier = {}

    # canonical user question
    get_uq = getattr(context, "get_user_question", None)
    if callable(get_uq):
        raw_user_query = get_uq()
    else:
        exec_state: dict = getattr(context, "execution_state", {}) or {}
        raw_user_query = (
            exec_state.get("original_query")
            or exec_state.get("user_question")
            or ""
        )

    # refiner output → still optional
    refiner_output = None
    get_last_output = getattr(context, "get_last_output", None)
    if callable(get_last_output):
        try:
            refiner_output = get_last_output("refiner")
        except Exception:
            refiner_output = None

    refined_text = _extract_refined_text_from_refiner_output(refiner_output)
    effective_text = (refined_text or raw_user_query or "").strip()

    return classifier, effective_text


def _extract_refined_query(raw: str) -> Optional[str]:
    """
    Try to extract the refined_query string from the RefinerAgent output.

    Handles:
    - Proper JSON like {"refined_query": "query seasons ..."}
    - Slightly malformed JSON that still contains a "refined_query": "..." segment.
    """
    if not raw:
        return None

    text = raw.strip()

    # 1) Best-effort: try normal JSON
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and isinstance(obj.get("refined_query"), str):
            return obj["refined_query"]
    except Exception:
        pass

    # 2) Fallback: regex against JSON-ish text
    m = re.search(r'"refined_query"\s*:\s*"([^"]*)"', text)
    if m:
        return m.group(1)

    return None


def _normalize_like_filter_condition(fc: FilterCondition) -> FilterCondition:
    """
    Convert FilterCondition that encodes a SQL-ish LIKE into a proper op/value.

    Examples:
      value="like '%ion%'"  -> op='contains', value='ion'
      value="like 'ion%'"   -> op='startswith', value='ion'
      value="like '%ion'"   -> op='endswith',  value='ion'

    Only applied to filters where op is eq/equals and value is a string.
    """
    # Only normalize equality-like ops with string values
    if fc.op not in {"eq", "equals"}:
        return fc
    if not isinstance(fc.value, str):
        return fc

    text = fc.value.strip()
    m = LIKE_PATTERN_RE.match(text)
    if not m:
        return fc

    pattern = m.group(2).strip()
    # Strip outer quotes if present
    if len(pattern) >= 2 and pattern[0] == pattern[-1] and pattern[0] in {"'", '"'}:
        pattern = pattern[1:-1]

    if not pattern:
        return fc

    starts_pct = pattern.startswith("%")
    ends_pct = pattern.endswith("%")

    core = pattern.strip("%")
    if not core:
        return fc

    # Decide op based on wildcard placement
    if starts_pct and ends_pct:
        new_op = "contains"
    elif starts_pct:
        new_op = "endswith"
    elif ends_pct:
        new_op = "startswith"
    else:
        # no wildcards → keep as eq
        return fc

    return FilterCondition(field=fc.field, op=new_op, value=core)


def _extract_text_sort_from_query(text: str) -> Optional[Tuple[str, str]]:
    """
    Fallback heuristic to parse a single sort clause from free text.

    Supports:
      - "sort by name"
      - "sorted by name"
      - "sort seasons by name"
      - "sort status desc"
      - "sort status in descending order"
    """
    if not text:
        return None

    m = SORT_PATTERN.search(text)
    if not m:
        return None

    # Prefer explicit field from "sort <collection> by <field>",
    # otherwise fall back to the single-field case.
    field = m.group("field") or m.group("field_only")
    if not field:
        return None

    long_dir = m.group("long_dir")
    short_dir = m.group("short_dir")

    dir_token = (long_dir or short_dir or "asc").lower()
    direction = "desc" if dir_token.startswith("desc") else "asc"

    return field, direction


def _apply_filters_to_params(
    base_params: Dict[str, Any],
    filters: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Merge structured filters into HTTP params.

    Expected filter shape:

        {
            "field": "field_name",
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


# -----------------------------------------------------------------------------
# GENERIC WIZARD HELPERS
# -----------------------------------------------------------------------------


def _wizard_missing_fields(payload: Dict[str, Any], cfg: WizardConfig) -> List[str]:
    """
    Compute which required fields are still missing in the wizard payload.
    Returns a list of field names.
    """
    missing: List[str] = []
    for field in cfg.fields:
        if not field.required:
            continue
        value = payload.get(field.name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field.name)
    return missing


def _summarize_wizard_payload(payload: Dict[str, Any], cfg: WizardConfig) -> str:
    """
    Human-readable summary for confirmation message, based on WizardConfig.
    """
    lines: List[str] = []
    for field in cfg.fields:
        label = field.summary_label or field.label or field.name
        value = payload.get(field.name)

        if value is None or (isinstance(value, str) and not value.strip()):
            if field.required:
                value_str = "_not set_"
            else:
                value_str = field.default_value if field.default_value is not None else "none"
        else:
            value_str = value

        lines.append(f"- **{label}**: {value_str}")
    return "\n".join(lines)


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

    def _lexical_gate(self, raw_text: str, refined_text: str | None = None) -> dict:
        effective_text = (refined_text or raw_text or "").strip()
        text_l = effective_text.lower()

        intent: str | None = None

        # --- HIGH-PRIORITY: explicit CRUD verbs from the user text ---
        if text_l.startswith("query "):
            intent = "read"
        elif text_l.startswith(("get ", "list ", "show ", "find ")):
            intent = "read"
        elif text_l.startswith(("create ", "insert ", "add ", "record ")):
            intent = "create"
        elif text_l.startswith(("update ", "modify ", "change ")):
            intent = "update"
        elif text_l.startswith(("delete ", "remove ")):
            intent = "delete"

        # Default intent for structured queries w/out explicit verb: read
        if intent is None and text_l:
            intent = "read"

        result = {
            "effective_text": effective_text,
            "intent": intent,
            "is_structured_query": text_l.startswith("query "),
        }

        logger.info(
            "[data_query] lexical gate (local)",
            extra={
                "event": "data_query_lexical_gate_local",
                "effective_text_preview": effective_text[:80],
                "intent": intent,
                "is_structured_query": result["is_structured_query"],
            },
        )

        return result

    # -------------------------------------------------------------------------
    # GENERIC WIZARD INTERNAL HELPERS
    # -------------------------------------------------------------------------
    def _get_wizard_state(self, context: AgentContext) -> Dict[str, Any]:
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        return exec_state.get("wizard") or {}

    def _set_wizard_state(self, context: AgentContext, state: Optional[Dict[str, Any]]) -> None:
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        if state:
            exec_state["wizard"] = state
        else:
            exec_state.pop("wizard", None)
        context.execution_state = exec_state

    def _wizard_channel_key(self, collection: Optional[str] = None) -> str:
        # Single logical channel for wizard UX, optionally namespaced by collection
        if collection:
            return f"{self.name}:wizard:{collection}"
        return f"{self.name}:wizard"

    async def _start_wizard_for_route(
        self,
        context: AgentContext,
        route: DataQueryRoute,
        base_url: str,
        entity_meta: Dict[str, Any],
    ) -> AgentContext:
        """
        Start a generic creation wizard for the given route/collection,
        based on WizardConfig. If no config exists, do nothing and return
        context unchanged.
        """
        collection = getattr(route, "collection", None)
        cfg = get_wizard_config_for_collection(collection)
        if not cfg:
            logger.info(
                "[data_query:wizard] no wizard config for collection; skipping",
                extra={
                    "event": "data_query_wizard_no_config",
                    "collection": collection,
                },
            )
            return context

        logger.info(
            "[data_query:wizard] starting wizard",
            extra={
                "event": "data_query_wizard_start",
                "collection": collection,
                "route_name": getattr(route, "name", None),
                "topic": getattr(route, "topic", None),
            },
        )

        payload: Dict[str, Any] = {
            "source": "ai_data_query",
            "base_url": base_url,
            "entity_id": entity_meta.get("id"),
            "collection": collection,
        }

        missing = _wizard_missing_fields(payload, cfg)
        next_field_name = missing[0] if missing else None

        wizard_state: Dict[str, Any] = {
            "pending_action": "collect",
            "payload": payload,
            "collection": collection,
            "current_field": next_field_name,
            "route_info": {
                "name": getattr(route, "name", None),
                "collection": collection,
                "topic": getattr(route, "topic", None),
                "resolved_path": getattr(route, "resolved_path", None),
                "base_url": base_url,
            },
        }
        self._set_wizard_state(context, wizard_state)

        channel_key = self._wizard_channel_key(collection)

        if next_field_name:
            field_cfg = cfg.field_by_name(next_field_name)
            if field_cfg and field_cfg.prompt:
                prompt = field_cfg.prompt
            else:
                # generic fallback
                prompt = f"Please provide {field_cfg.label if field_cfg else next_field_name}."

            content_str = (
                "I can create a record, but I need a few details first.\n\n" + prompt
            )
            meta_block = {
                "action": "wizard",
                "step": "collect_field",
                "collection": collection,
                "current_field": next_field_name,
                "missing_fields": missing,
            }

            context.add_agent_output(
                agent_name=channel_key,
                logical_name=self.name,  # "data_query"
                content=content_str,
                role="assistant",
                meta=meta_block,
                action="wizard_step",
                intent="action",
            )
        else:
            # Should be very rare; everything prefilled
            summary = _summarize_wizard_payload(payload, cfg)
            wizard_state["pending_action"] = "confirm"
            self._set_wizard_state(context, wizard_state)

            content_str = (
                "Here’s the record I’m ready to create:\n\n"
                f"{summary}\n\n"
                "Type 'confirm' to save this record or 'cancel' to abort."
            )
            meta_block = {
                "action": "wizard",
                "step": "confirm",
                "collection": collection,
            }

            context.add_agent_output(
                agent_name=channel_key,
                logical_name=self.name,
                content=content_str,
                role="assistant",
                meta=meta_block,
                action="wizard_step",
                intent="action",
            )

        return context

    async def _continue_wizard(
        self,
        context: AgentContext,
        wizard_state: Dict[str, Any],
        user_text: str,
    ) -> AgentContext:
        """
        Continue a generic wizard: either collect the next field or handle
        the final confirmation.
        """
        collection = wizard_state.get("collection")
        cfg = get_wizard_config_for_collection(collection)
        channel_key = self._wizard_channel_key(collection)
        pending_action = wizard_state.get("pending_action")
        payload: Dict[str, Any] = wizard_state.get("payload") or {}

        if not cfg:
            # No config anymore? Abort safely.
            self._set_wizard_state(context, None)
            context.add_agent_output(
                agent_name=channel_key,
                logical_name=self.name,
                content="Sorry, I’m missing the configuration for this wizard.",
                role="assistant",
                meta={
                    "action": "wizard",
                    "step": "error",
                    "collection": collection,
                },
                action="wizard_error",
                intent="action",
            )
            return context

        # ---------------------------------------------------------------------
        # CONFIRMATION STEP
        # ---------------------------------------------------------------------
        if pending_action == "confirm":
            answer = (user_text or "").strip().lower()
            logger.info(
                "[data_query:wizard] confirmation step",
                extra={
                    "event": "data_query_wizard_confirm",
                    "collection": collection,
                    "answer": answer,
                },
            )
            if answer in {"yes", "y", "confirm", "ok", "okay"}:
                exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
                # generic storage key: "<collection>_create_ready"
                if collection:
                    exec_state[f"{collection}_create_ready"] = payload
                context.execution_state = exec_state

                self._set_wizard_state(context, None)

                summary = _summarize_wizard_payload(payload, cfg)

                content_str = (
                    "Great, I’ve collected everything needed:\n\n"
                    f"{summary}\n\n"
                    "The payload is ready for creation in the backend."
                )
                meta_block = {
                    "action": "wizard",
                    "step": "confirmed",
                    "collection": collection,
                }

                context.add_agent_output(
                    agent_name=channel_key,
                    logical_name=self.name,
                    content=content_str,
                    role="assistant",
                    meta=meta_block,
                    action="wizard_confirmed",
                    intent="action",
                )
                return context

            # User cancelled
            self._set_wizard_state(context, None)
            context.add_agent_output(
                agent_name=channel_key,
                logical_name=self.name,
                content="Okay, I won’t create this record.",
                role="assistant",
                meta={
                    "action": "wizard",
                    "step": "cancelled",
                    "collection": collection,
                },
                action="wizard_cancelled",
                intent="action",
            )
            return context

        # ---------------------------------------------------------------------
        # FIELD COLLECTION STEP
        # ---------------------------------------------------------------------
        current_field_name = wizard_state.get("current_field")
        if not current_field_name:
            missing = _wizard_missing_fields(payload, cfg)
            current_field_name = missing[0] if missing else None
            wizard_state["current_field"] = current_field_name
            self._set_wizard_state(context, wizard_state)

        field_cfg = cfg.field_by_name(current_field_name) if current_field_name else None

        logger.info(
            "[data_query:wizard] collecting field",
            extra={
                "event": "data_query_wizard_collect_field",
                "collection": collection,
                "current_field": current_field_name,
                "user_text": user_text,
            },
        )

        answer = (user_text or "").strip()

        if field_cfg:
            # Normalize / transform if configured
            if field_cfg.normalizer:
                value = field_cfg.normalizer(answer)
            else:
                # simple convention: handle "no"/"none" for optional "notes"-like fields
                if (
                    not field_cfg.required
                    and field_cfg.name in {"notes", "comment", "comments"}
                    and answer.lower() in {"no", "none"}
                ):
                    value = ""
                elif not answer and field_cfg.default_value is not None:
                    value = field_cfg.default_value
                else:
                    value = answer
            payload[field_cfg.name] = value
        else:
            # fallback: unknown field, just store raw answer
            if current_field_name:
                payload[current_field_name] = answer

        wizard_state["payload"] = payload

        # Recompute missing required fields
        missing = _wizard_missing_fields(payload, cfg)

        if missing:
            # Ask next required field
            next_field_name = missing[0]
            next_field_cfg = cfg.field_by_name(next_field_name)
            wizard_state["current_field"] = next_field_name
            wizard_state["pending_action"] = "collect"
            self._set_wizard_state(context, wizard_state)

            if next_field_cfg and next_field_cfg.prompt:
                prompt = next_field_cfg.prompt
            else:
                prompt = f"Please provide {next_field_cfg.label if next_field_cfg else next_field_name}."

            meta_block = {
                "action": "wizard",
                "step": "collect_field",
                "collection": collection,
                "current_field": next_field_name,
                "missing_fields": missing,
            }

            context.add_agent_output(
                agent_name=channel_key,
                logical_name=self.name,
                content=prompt,
                role="assistant",
                meta=meta_block,
                action="wizard_step",
                intent="action",
            )
            return context

        # All required fields are present → move to confirmation
        wizard_state["pending_action"] = "confirm"
        wizard_state["current_field"] = None
        self._set_wizard_state(context, wizard_state)

        summary = _summarize_wizard_payload(payload, cfg)
        content_str = (
            "Here’s the record I’m ready to create:\n\n"
            f"{summary}\n\n"
            "Type 'confirm' to save this record, or 'cancel' to abort."
        )
        meta_block = {
            "action": "wizard",
            "step": "confirm",
            "collection": collection,
        }

        context.add_agent_output(
            agent_name=channel_key,
            logical_name=self.name,
            content=content_str,
            role="assistant",
            meta=meta_block,
            action="wizard_confirm",
            intent="action",
        )
        return context

    async def _run_stubbed_wizard_operation(
        self,
        context: AgentContext,
        *,
        operation: str,
        route: DataQueryRoute,
        base_url: str,
        entity_meta: Dict[str, Any],
    ) -> AgentContext:
        """
        Generic stubbed CRUD wizard operation.

        This does NOT call the backend; it just logs a dummy payload and
        emits a friendly message so you can wire up the real wizard later.
        """
        collection = getattr(route, "collection", None)
        channel_key = self._wizard_channel_key(collection)

        message = (
            f"[STUB] Would perform **{operation.upper()}** via wizard for "
            f"collection `{collection}` using base URL `{base_url}`.\n\n"
            "This is a stub implementation; no data has been changed."
        )

        payload: Dict[str, Any] = {
            "ok": True,
            "source": "wizard_stub",
            "operation": operation,
            "collection": collection,
            "entity": entity_meta,
            "base_url": base_url,
            "route": {
                "topic": getattr(route, "topic", None),
                "collection": getattr(route, "collection", None),
                "view_name": getattr(route, "view_name", None),
                "resolved_path": getattr(route, "resolved_path", None),
            },
            "message": message,
        }

        # Store stub payload in execution_state so other agents / UI can see it
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        key_collection = collection or "unknown_collection"
        exec_state[f"{key_collection}_{operation}_wizard_stub"] = payload
        context.execution_state = exec_state

        # Also expose in structured_outputs under both channel and logical agent name
        structured = exec_state.setdefault("structured_outputs", {})
        structured[channel_key] = payload
        if not isinstance(structured.get(self.name), dict):
            structured[self.name] = payload

        logger.info(
            "[data_query:wizard_stub] operation stubbed",
            extra={
                "event": "data_query_wizard_stub_operation",
                "operation": operation,
                "collection": collection,
                "topic": getattr(route, "topic", None),
                "view_name": getattr(route, "view_name", None),
            },
        )

        context.add_agent_output(
            agent_name=channel_key,
            logical_name=self.name,
            content=message,
            role="assistant",
            meta=payload,
            action=operation,
            intent="action",
        )

        return context

    async def _run_stub_create_wizard(
        self,
        context: AgentContext,
        route: DataQueryRoute,
        base_url: str,
        entity_meta: Dict[str, Any],
    ) -> AgentContext:
        """Stubbed CREATE wizard entrypoint (no real backend call yet)."""
        return await self._run_stubbed_wizard_operation(
            context,
            operation="create",
            route=route,
            base_url=base_url,
            entity_meta=entity_meta,
        )

    async def _run_stub_update_wizard(
        self,
        context: AgentContext,
        route: DataQueryRoute,
        base_url: str,
        entity_meta: Dict[str, Any],
    ) -> AgentContext:
        """Stubbed UPDATE wizard entrypoint (no real backend call yet)."""
        return await self._run_stubbed_wizard_operation(
            context,
            operation="update",
            route=route,
            base_url=base_url,
            entity_meta=entity_meta,
        )

    async def _run_stub_delete_wizard(
        self,
        context: AgentContext,
        route: DataQueryRoute,
        base_url: str,
        entity_meta: Dict[str, Any],
    ) -> AgentContext:
        """Stubbed DELETE wizard entrypoint (no real backend call yet)."""
        return await self._run_stubbed_wizard_operation(
            context,
            operation="delete",
            route=route,
            base_url=base_url,
            entity_meta=entity_meta,
        )

    # -------------------------------------------------------------------------
    # SUPPORT / QUERY EXECUTION HELPERS
    # -------------------------------------------------------------------------

    async def _enrich_person_name(
        self,
        client: BackendAPIClient,
        rows_full: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        For result rows that have a person_id field, look up each person in the
        backend API and add a 'person_name' field to each row.

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
                        "[data_query:person_enrichment] Failed to fetch person for row",
                        extra={
                            "event": "data_query_person_enrichment_fetch_failed",
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
                "[data_query:person_enrichment] enrichment complete",
                extra={
                    "event": "data_query_person_enrichment_complete",
                    "row_keys_sample": list(rows_full[0].keys()) if rows_full else [],
                },
            )

            return rows_full

        except Exception as exc:
            # Non-fatal: log and return original rows
            logger.warning(
                "[data_query:person_enrichment] Failed to enrich person_name from backend",
                extra={
                    "event": "data_query_person_enrichment_failed",
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
        - Apply any configured joins (e.g., base_collection.person_id -> persons.full_name).
        - Return enriched rows.
        """
        # 1) Fetch base rows
        base_path = getattr(route, "resolved_path", None) or getattr(route, "path", None) or ""
        base_rows = await client.get_json(base_path, params=params)  # adjust to your method name

        if not base_rows or not query_spec.joins:
            return base_rows or []

        # 2) For now, handle only the first join (you can generalize later)
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
    # MAIN EXECUTION
    # -------------------------------------------------------------------------
    async def run(self, context: AgentContext) -> AgentContext:
        """
        Main data_query entrypoint.

        Now supports:
          - lexical detection of CRUD verbs via lexical gate
          - QuerySpec-based filter parsing via `parse_text_filters`
          - merging structured filters + text-derived filters into HTTP params
          - preferring RefinerAgent's refined_query text (when available)
          - routing any 'create' intent with a WizardConfig to the create wizard
        """

        # --- EXECUTION CONFIG --------------------------------------------------
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        # ensure we can mutate and the changes persist
        exec_cfg: Dict[str, Any] = exec_state.setdefault("execution_config", {})
        dq_cfg: Dict[str, Any] = exec_cfg.setdefault("data_query", {})

        # Classifier output + ORIGINAL text (typically pre-refiner)
        classifier, initial_effective_text = _get_classifier_and_text_from_context(context)
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}

        # ---------------------------------------------------------
        # 🔧 NEW — fallback classifier hydration
        # ---------------------------------------------------------

        # 1) If context gave us nothing, try direct stored bundle
        if not classifier:
            raw_classifier = exec_state.get("classifier_result")
            classifier = raw_classifier if isinstance(raw_classifier, dict) else {}

        # 2) If still empty, unpack task+cognitive stored by classifier.run()
        if not classifier and context is not None:
            # Be VERY defensive: only use dict-like values
            try:
                raw_task = (
                    context.get_task_classification()
                    if hasattr(context, "get_task_classification")
                    else exec_state.get("task_classification")
                )
            except Exception:
                raw_task = None

            try:
                raw_cog = (
                    context.get_cognitive_classification()
                    if hasattr(context, "get_cognitive_classification")
                    else exec_state.get("cognitive_classification")
                )
            except Exception:
                raw_cog = None

            task = raw_task if isinstance(raw_task, dict) else {}
            cog = raw_cog if isinstance(raw_cog, dict) else {}

            classifier = {
                "intent": task.get("intent"),
                "topic": cog.get("topic"),
                "topics": (cog.get("topics") or []) if isinstance(cog.get("topics"), list) else [],
                "domain": cog.get("domain"),
                "confidence": task.get("confidence"),
                "topic_confidence": cog.get("topic_confidence"),
            }

        # 3) Ensure required classifier keys exist so routing never breaks
        if not isinstance(classifier, dict):
            classifier = {}

        classifier.setdefault("topic_confidence", 0.0)
        classifier.setdefault("topics", [])
        classifier.setdefault("intent", None)

        # 🔎 ORIGINAL / RAW USER INPUT (pre-refiner), if we have it
        raw_user_input = (exec_state.get("user_question") or "").strip()
        raw_user_lower = raw_user_input.lower()

        # ----------------------------------------------------------------------
        # 🔍 Pull refined_query from RefinerAgent output (if present)
        # ----------------------------------------------------------------------
        refined_text: Optional[str] = None
        try:
            refiner_output = context.get_last_output("refiner")
            refined_text = _extract_refined_text_from_refiner_output(refiner_output)
        except Exception as e:
            logger.warning(
                "[data_query:refiner] failed to extract refined_query; falling back to original text",
                extra={
                    "event": "data_query_refined_query_extract_error",
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            )
            refined_text = None

        # Effective text for routing / lexical gates:
        # prefer refined_query when available, otherwise what came from
        # _get_classifier_and_text_from_context, otherwise empty.
        effective_text = (refined_text or initial_effective_text or "").strip()
        effective_text_lower = effective_text.lower()
        raw_text_norm = effective_text
        raw_text_lower = effective_text_lower

        # Stash for observability
        exec_state["data_query_texts"] = {
            "raw_user_input": raw_user_input,
            "raw_text": raw_text_norm,
            "refined_text": refined_text,
            "effective_text": effective_text,
        }
        context.execution_state = exec_state

        logger.info(
            "[data_query:texts] resolved text variants for data_query",
            extra={
                "event": "data_query_text_variants",
                "has_raw_user_input": bool(raw_user_input),
                "has_raw_text": bool(raw_text_norm),
                "has_refined_text": bool(refined_text),
                "effective_text_preview": effective_text[:200],
            },
        )

        # Keep any structured filters passed into execution_config.data_query
        structured_filters_cfg: List[Dict[str, Any]] = dq_cfg.get("filters") or []

        # Existing wizard state → skip routing + structured gating entirely
        wizard_state = self._get_wizard_state(context)

        # ----------------------------------------------------------------------
        # 🔑 LEXICAL GATE (centralized logic)
        # ----------------------------------------------------------------------
        lexical = self._lexical_gate(
            raw_text=(raw_user_input or raw_text_norm or ""),
            refined_text=refined_text,
        )
        is_structured_query = bool(lexical.get("is_structured_query"))
        lexical_intent = lexical.get("intent")

        # 🔎 Normalize lexical_intent for downstream use
        if isinstance(lexical_intent, str):
            lexical_intent = lexical_intent.strip().lower() or None
        else:
            lexical_intent = None

        # Treat any explicit CRUD lexical intent as a reason to keep data_query active
        is_crud_lexical_intent = lexical_intent in {"create", "update", "delete"}

        # SIMPLE STRUCTURED QUERY / FORCE GATE
        force_data_query = bool(dq_cfg.get("force")) or _looks_like_database_query(
            effective_text
        )

        logger.info(
            "[data_query] lexical gate",
            extra={
                "event": "data_query_lexical_gate",
                "raw_text_preview": raw_text_norm[:200],
                "effective_text_preview": effective_text[:200],
                "raw_user_preview": raw_user_input[:200],
                "is_structured_query": is_structured_query,
                "force_data_query": force_data_query,
                "has_wizard_state": bool(wizard_state),
                "lexical_intent": lexical_intent,
                "is_crud_lexical_intent": is_crud_lexical_intent,
            },
        )

        # ---- SKIP CONDITIONS -------------------------------------------------
        # ⬇️ UPDATED: do NOT skip if lexical intent is create/update/delete
        if (
            not is_structured_query
            and not force_data_query
            and not wizard_state
            and not is_crud_lexical_intent
        ):
            logger.info(
                "[data_query:routing] skipping: no structured query, no force, "
                "no wizard state, no CRUD lexical intent",
                extra={
                    "event": "data_query_skip_non_structured",
                    "effective_text_preview": effective_text[:200],
                },
            )
            return context

        # ---- WIZARD CONTINUATION --------------------------------------------
        if wizard_state:
            logger.info(
                "[data_query:wizard] continuing existing wizard",
                extra={"event": "data_query_wizard_continue"},
            )
            return await self._continue_wizard(
                context,
                wizard_state,
                # When continuing a wizard, use whatever the user just typed;
                # fall back to effective_text as a sane default.
                effective_text or raw_user_input or raw_text_norm,
            )

        # ---- INTENT RESOLUTION ----------------------------------------------
        state_intent = getattr(context, "intent", None) or exec_state.get("intent")
        classifier_intent = (
            classifier.get("intent") if isinstance(classifier, dict) else None
        )

        # 🧠 NEW: strong CRUD lexical intent wins over a generic classifier "read"
        crud_verbs = {"create", "update", "delete"}

        if isinstance(state_intent, str):
            state_intent = state_intent.strip().lower() or None
        if isinstance(classifier_intent, str):
            classifier_intent = classifier_intent.strip().lower() or None

        if lexical_intent in crud_verbs:
            # If state intent explicitly specifies a CRUD verb, let that win.
            if state_intent in crud_verbs:
                intent_raw = state_intent
            else:
                intent_raw = lexical_intent
        else:
            # No strong CRUD signal → keep your original precedence
            intent_raw = state_intent or classifier_intent or lexical_intent

        intent = (intent_raw or "").strip().lower() or None

        topic_override = dq_cfg.get("topic")

        logger.info(
            "[data_query] run() begin",
            extra={
                "event": "data_query_run_begin",
                "intent": intent,
                "topic_override": topic_override,
                "raw_text_preview": raw_text_norm[:200],
                "refined_text_preview": (refined_text[:200] if refined_text else None),
                "effective_text_preview": effective_text[:200],
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
                "refined_text": refined_text,
                "effective_text": effective_text,
                "raw_user_input": raw_user_input,
                "classifier": classifier,
            },
        )

        # ---- ROUTE SELECTION -------------------------------------------------
        # 1️⃣ Explicit override always wins
        if topic_override:
            route = resolve_route(topic_override, intent=intent)
            route_source = "explicit_override"

        # 2️⃣ Default classifier/text routing (now uses effective_text)
        else:
            route = choose_route_for_query(effective_text or raw_text_norm, classifier)
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
                # NOTE: if QuerySpec has a sort field, clone it too
                **(
                    {"sort": list(getattr(base_spec, "sort", []))}
                    if hasattr(base_spec, "sort")
                    else {}
                ),
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
        filter_text = raw_user_input or raw_text_norm or effective_text
        if filter_text:
            # First, let the main parser attach filters/sort to the QuerySpec.
            before_count = len(query_spec.filters)
            query_spec = parse_text_filters(filter_text, query_spec)
            after_count = len(query_spec.filters)

            if after_count > before_count:
                logger.info(
                    "[data_query:filters] parsed filters from text",
                    extra={
                        "event": "data_query_filters_from_text",
                        "raw_text_preview": filter_text[:200],
                        "new_filter_count": after_count - before_count,
                        "total_filter_count": after_count,
                    },
                )

            # 🔁 NEW: normalize any "like '%...%'" equality filters into
            # contains/startswith/endswith so OP_MAP + backend filters work correctly.
            normalized_filters: List[FilterCondition] = []
            for fc in query_spec.filters:
                try:
                    normalized_filters.append(_normalize_like_filter_condition(fc))
                except Exception as e:
                    logger.warning(
                        "[data_query:filters] like-normalization failed; keeping original condition",
                        extra={
                            "event": "data_query_like_normalization_failed",
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                            "field": getattr(fc, "field", None),
                            "op": getattr(fc, "op", None),
                            "value": getattr(fc, "value", None),
                        },
                    )
                    normalized_filters.append(fc)

            query_spec.filters = normalized_filters

            # 🔁 Fallback heuristic for patterns the main parser doesn't handle
            try:
                extracted = _extract_text_filters_from_query(filter_text, route)
            except Exception as e:
                logger.warning(
                    "[data_query:filters] fallback text filter parsing failed; ignoring",
                    extra={
                        "event": "data_query_fallback_text_filter_parse_error",
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "raw_text_preview": filter_text[:200],
                    },
                )
                extracted = ExtractedTextFilters(filters=[], sort=None)

            if extracted.filters:
                logger.info(
                    "[data_query:filters] applying fallback text filters to HTTP params",
                    extra={
                        "event": "data_query_apply_fallback_filters",
                        "raw_text_preview": filter_text[:200],
                        "fallback_filter_count": len(extracted.filters),
                        "filters": extracted.filters,
                    },
                )
                params = _apply_filters_to_params(params, extracted.filters)

        # Summarize QuerySpec for observability (avoid storing full dataclass)
        dq_meta = exec_state.setdefault("data_query_step_metadata", {})
        dq_meta["query_spec_summary"] = {
            "base_collection": query_spec.base_collection,
            "projection_count": len(query_spec.projections),
            "join_count": len(query_spec.joins),
            "filter_count": len(query_spec.filters),
            "search_fields": list(query_spec.search_fields),
            # 👇 NEW: log sort info for debugging
            "sort": list(getattr(query_spec, "sort", [])),
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

        # --- SORT HANDLING ----------------------------------------------------
        # 1️⃣ Primary: honor QuerySpec.sort if parse_text_filters populated it
        sort_list: List[Tuple[str, str]] = list(getattr(query_spec, "sort", []))

        # 2️⃣ Fallback: if QuerySpec.sort is empty, try parsing sort from text ourselves
        if not sort_list and filter_text:
            sort_hint = _extract_text_sort_from_query(filter_text)
            if sort_hint:
                sort_list = [sort_hint]
                logger.info(
                    "[data_query:sort] parsed sort from text fallback",
                    extra={
                        "event": "data_query_sort_from_text_fallback",
                        "collection": query_spec.base_collection,
                        "field": sort_hint[0],
                        "direction": sort_hint[1],
                        "raw_text_preview": filter_text[:200],
                    },
                )

        if sort_list:
            sort_field, sort_dir = sort_list[0]  # first sort key only for now

            orig_dir = sort_dir
            sort_dir = (sort_dir or "asc").lower()
            if sort_dir not in {"asc", "desc"}:
                logger.warning(
                    "[data_query:sort] invalid sort direction; defaulting to asc",
                    extra={
                        "event": "data_query_invalid_sort_direction",
                        "direction": orig_dir,
                        "normalized_direction": sort_dir,
                        "field": sort_field,
                        "collection": query_spec.base_collection,
                    },
                )
                sort_dir = "asc"

            # Django-style ordering param: "-" prefix for desc
            ordering_value = f"-{sort_field}" if sort_dir == "desc" else sort_field
            params["ordering"] = ordering_value

            logger.info(
                "[data_query:sort] applied sort",
                extra={
                    "event": "data_query_sort_applied",
                    "collection": query_spec.base_collection,
                    "field": sort_field,
                    "direction": sort_dir,
                    "ordering_param": ordering_value,
                },
            )
        else:
            logger.info(
                "[data_query:sort] no sort on QuerySpec or text; using backend default",
                extra={
                    "event": "data_query_no_sort",
                    "collection": query_spec.base_collection,
                },
            )

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

        # ---- CRUD WIZARDS ----------------------------------------------------
        #
        # NEW BEHAVIOR:
        # - Any intent == "create" will attempt to start the generic create wizard
        #   for this route's collection (if a WizardConfig exists).
        # - "update" and "delete" intents go to stubbed wizards.
        if intent in {"update", "delete"}:
            logger.info(
                "[data_query:wizard_stub] routing to stubbed CRUD wizard",
                extra={
                    "event": "data_query_wizard_stub_entry",
                    "intent": intent,
                    "route_topic": getattr(route, "topic", None),
                    "route_collection": getattr(route, "collection", None),
                },
            )
            if intent == "update":
                return await self._run_stub_update_wizard(
                    context=context,
                    route=route,
                    base_url=base_url,
                    entity_meta=entity_meta,
                )
            else:  # delete
                return await self._run_stub_delete_wizard(
                    context=context,
                    route=route,
                    base_url=base_url,
                    entity_meta=entity_meta,
                )

        if intent == "create":
            collection_for_wizard = getattr(route, "collection", None)
            cfg_for_wizard = get_wizard_config_for_collection(collection_for_wizard)
            if cfg_for_wizard:
                logger.info(
                    "[data_query:wizard] starting create wizard for collection",
                    extra={
                        "event": "data_query_wizard_entry_create",
                        "route_topic": getattr(route, "topic", None),
                        "route_collection": getattr(route, "collection", None),
                    },
                )
                return await self._start_wizard_for_route(
                    context=context,
                    route=route,
                    base_url=base_url,
                    entity_meta=entity_meta,
                )
            else:
                logger.info(
                    "[data_query:wizard] no WizardConfig for collection; falling back to HTTP query",
                    extra={
                        "event": "data_query_wizard_no_config_for_create",
                        "route_topic": getattr(route, "topic", None),
                        "route_collection": getattr(route, "collection", None),
                    },
                )

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
            # Generic enrichment for any rows with person_id
            rows_full = await self._enrich_person_name(client, rows_full)

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
        # 🔧 IMPORTANT: prefer view_name so that payload + markdown share the same key.
        view_name = getattr(route, "view_name", None)
        topic_val = getattr(route, "topic", None)

        view_key = view_name.strip() if isinstance(view_name, str) else ""
        topic_key = topic_val.strip() if isinstance(topic_val, str) else ""

        if view_key:
            # e.g. "data_query:seasons"
            channel_key = f"{self.name}:{view_key}"
        elif topic_key:
            # fallback: "data_query:season"
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

        # Also expose the canonical payload under the logical agent name
        if not isinstance(structured.get(self.name), dict):
            structured[self.name] = payload

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

            # Envelope content = markdown; meta carries the rich block
            context.add_agent_output(
                agent_name=channel_key,
                logical_name=self.name,  # "data_query"
                content=md_compact,
                role="assistant",
                meta=meta_block,
                action="query",
                intent="action",
            )

            structured_outputs = context.execution_state.setdefault(
                "structured_outputs", {}
            )
            structured_outputs[channel_key] = canonical_output

            # Mirror canonical_output under logical agent name if not already set
            if not isinstance(structured_outputs.get(self.name), dict):
                structured_outputs[self.name] = canonical_output

        else:
            logger.debug(
                "[data_query:output] adding failed agent_output",
                extra={
                    "event": "data_query_output_failure",
                    "error": payload.get("error"),
                },
            )
            fail_content = f"**data_query failed**: {payload.get('error', 'unknown error')}"

            context.add_agent_output(
                agent_name=channel_key,
                logical_name=self.name,
                content=fail_content,
                role="assistant",
                meta=payload,
                action="query",
                intent="action",
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
