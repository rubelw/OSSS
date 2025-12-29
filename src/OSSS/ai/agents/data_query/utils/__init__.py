
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from OSSS.ai.context import AgentContext
from OSSS.ai.observability import get_logger
from OSSS.ai.agents.data_query.config import DataQueryRoute, resolve_route, find_route_for_text
from OSSS.ai.agents.data_query.queryspec import QuerySpec, FilterCondition

logger = get_logger(__name__)


DEFAULT_BASE_URL_ENV_KEY = "OSSS_BACKEND_BASE_URL"


@dataclass
class ExtractedTextFilters:
    filters: List[Dict[str, Any]]
    sort: Optional[Dict[str, Any]]


OP_MAP: Dict[str, str] = {
    "contains": "contains",
    "icontains": "contains",
    "startswith": "startswith",
    "prefix": "startswith",
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
    re.compile(
        r"(?:filter|restrict)\s+"
        r"(?:to\s+)?(?:only\s+)?(?:show\s+)?"
        r"(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s+"
        r"(?:which|that)?\s*start(?:s)?\s+with"
        r"(?:\s+the\s+letter)?\s+'?(?P<value>[A-Za-z])'?",
        re.IGNORECASE,
    ),
    re.compile(
        r"restrict\s+"
        r"(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s+"
        r"to\s+those\s+starting\s+with\s+'?(?P<value>[A-Za-z])'?",
        re.IGNORECASE,
    ),
]

SORT_PATTERN = re.compile(
    r"(?:sort|sorted)\s+"  # sort / sorted
    r"("  # either:
    r"(?P<collection>[a-zA-Z_][a-zA-Z0-9_]*)\s+by\s+(?P<field>[a-zA-Z_][a-zA-Z0-9_]*)"
    r"|"  # or:
    r"(?:by\s+)?(?P<field_only>[a-zA-Z_][a-zA-Z0-9_]*)"
    r")"
    r"(?:\s+in\s+(?P<long_dir>ascending|descending)\s+order"
    r"|\s+(?P<short_dir>asc|desc))?",
    re.IGNORECASE,
)

LIKE_PATTERN_RE = re.compile(r"(?i)^(?:is\s+)?(i?like)\s+(.+)$")

REFINED_QUERY_KEY = "refined_query"


def _extract_text_filters_from_query(
    raw_text: str,
    route: Optional[DataQueryRoute],
) -> ExtractedTextFilters:
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
        break

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

    return ExtractedTextFilters(filters=filters, sort=None)


def _looks_like_database_query(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return False
    if t.startswith("query ") or t.startswith("select "):
        return True
    KEYWORDS = (" database", " table", " tables", " row ", " rows ", " records ", "schema")
    return any(kw in t for kw in KEYWORDS)


def _extract_refined_text_from_refiner_output(refiner_output: object) -> Optional[str]:
    if (
        refiner_output is not None
        and not isinstance(refiner_output, (dict, str))
        and hasattr(refiner_output, "text")
    ):
        try:
            text_value = getattr(refiner_output, "text", None)
            if isinstance(text_value, str):
                return _extract_refined_text_from_refiner_output(text_value)
        except Exception:
            pass

    if isinstance(refiner_output, dict):
        val = refiner_output.get(REFINED_QUERY_KEY)
        if isinstance(val, str):
            return val.strip()

    if isinstance(refiner_output, str):
        text = refiner_output.strip()

        if text.startswith("{") and REFINED_QUERY_KEY in text:
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None

            if isinstance(parsed, dict):
                val = parsed.get(REFINED_QUERY_KEY)
                if isinstance(val, str):
                    return val.strip()

        if REFINED_QUERY_KEY in text:
            m = re.search(
                r'"refined_query"\s*:\s*"([^"]*)"',
                text,
                flags=re.DOTALL,
            )
            if m:
                return m.group(1).strip()

            m_single = re.search(
                r"[\"']refined_query[\"']\s*:\s*'([^']*)'",
                text,
                flags=re.DOTALL,
            )
            if m_single:
                return m_single.group(1).strip()

        return text

    return None


def _get_classifier_and_text_from_context(
    context: AgentContext,
) -> Tuple[Dict[str, Any], str]:
    get_clf = getattr(context, "get_classifier_result", None)
    if callable(get_clf):
        classifier = get_clf() or {}
    else:
        exec_state: dict = getattr(context, "execution_state", {}) or {}
        classifier = exec_state.get("classifier_result") or {}
        if not isinstance(classifier, dict):
            classifier = {}

    get_uq = getattr(context, "get_user_question", None)
    if callable(get_uq):
        raw_user_query = get_uq()
    else:
        exec_state = getattr(context, "execution_state", {}) or {}
        raw_user_query = (
            exec_state.get("original_query")
            or exec_state.get("user_question")
            or ""
        )

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


def _normalize_like_filter_condition(fc: FilterCondition) -> FilterCondition:
    if fc.op not in {"eq", "equals"}:
        return fc
    if not isinstance(fc.value, str):
        return fc

    text = fc.value.strip()
    m = LIKE_PATTERN_RE.match(text)
    if not m:
        return fc

    pattern = m.group(2).strip()
    if len(pattern) >= 2 and pattern[0] == pattern[-1] and pattern[0] in {"'", '"'}:
        pattern = pattern[1:-1]

    if not pattern:
        return fc

    starts_pct = pattern.startswith("%")
    ends_pct = pattern.endswith("%")
    core = pattern.strip("%")
    if not core:
        return fc

    if starts_pct and ends_pct:
        new_op = "contains"
    elif starts_pct:
        new_op = "endswith"
    elif ends_pct:
        new_op = "startswith"
    else:
        return fc

    return FilterCondition(field=fc.field, op=new_op, value=core)


def _extract_text_sort_from_query(text: str) -> Optional[Tuple[str, str]]:
    if not text:
        return None

    m = SORT_PATTERN.search(text)
    if not m:
        return None

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

        if isinstance(value, str):
            v = value.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in {"'", '"'}:
                value = v[1:-1]

        if op in {"eq", "equals"}:
            key = field
        elif op in {"in", "one_of"}:
            suffix = OP_MAP.get(op, "in")
            key = f"{field}__{suffix}"
            if isinstance(value, list):
                value = ",".join(str(v) for v in value)
        else:
            suffix = OP_MAP.get(op, op)
            key = f"{field}__{suffix}"

        params[key] = value

    return params


def _rows_to_markdown_table(
    rows: List[Dict[str, Any]],
    *,
    columns: Optional[List[str]] = None,
    max_rows: int = 20,
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


def _shrink_to_ui_defaults(
    rows_full: List[Dict[str, Any]],
    query_spec: QuerySpec,
) -> List[Dict[str, Any]]:
    if not rows_full:
        return []

    if query_spec.projections:
        raw_keys = list(query_spec.projections)
    else:
        raw_keys = list(rows_full[0].keys())

    base_keys: List[str] = []
    for k in raw_keys:
        if isinstance(k, str):
            base_keys.append(k)
            continue

        alias = getattr(k, "alias", None)
        name = (
            alias
            or getattr(k, "field", None)
            or getattr(k, "column", None)
            or getattr(k, "name", None)
        )

        if isinstance(name, str):
            base_keys.append(name)

    seen: set[str] = set()
    deduped_keys: List[str] = []
    for k in base_keys:
        if k not in seen:
            seen.add(k)
            deduped_keys.append(k)
    base_keys = deduped_keys

    sample_row = rows_full[0]
    extra_name_keys: List[str] = []
    for k in sample_row.keys():
        if isinstance(k, str) and k.endswith("_name") and k not in base_keys:
            extra_name_keys.append(k)

    if extra_name_keys:
        base_keys.extend(extra_name_keys)

    name_keys = {k for k in base_keys if k.endswith("_name")}
    id_keys_to_drop = set()
    for name_key in name_keys:
        stem = name_key[:-5]
        id_key = f"{stem}_id"
        if id_key in base_keys:
            id_keys_to_drop.add(id_key)

    if id_keys_to_drop:
        base_keys = [k for k in base_keys if k not in id_keys_to_drop]

    logger.info(
        "[data_query:render] compact column selection",
        extra={
            "event": "data_query_compact_columns_selected",
            "base_collection": query_spec.base_collection,
            "columns": base_keys,
        },
    )

    compact_rows: List[Dict[str, Any]] = []
    for row in rows_full:
        compact_rows.append({k: row.get(k) for k in base_keys if k in row})

    return compact_rows


def choose_route_for_query(
    raw_text: str,
    classifier: Dict[str, Any],
    *,
    min_topic_confidence: float,
) -> DataQueryRoute:
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
            "min_topic_confidence": min_topic_confidence,
            "classifier": classifier,
        },
    )

    if topic_primary and topic_conf >= min_topic_confidence:
        logger.info(
            "[data_query:routing] classifier topic_confidence high enough, trying topics first",
            extra={
                "event": "data_query_use_classifier_topics",
                "topic_primary": topic_primary,
                "topics_all": topics_all,
                "topic_confidence": topic_conf,
                "min_topic_confidence": min_topic_confidence,
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
                    "[data_query:routing] using classifier‑derived topic via resolve_route",
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
        logger.info(
            "[data_query:routing] classifier topic_confidence too low; falling back to text heuristic",
            extra={
                "event": "data_query_skip_classifier_topics_low_conf",
                "topic_primary": topic_primary,
                "topics_all": topics_all,
                "topic_confidence": topic_conf,
                "min_topic_confidence": min_topic_confidence,
                "raw_text_preview": raw_text[:200],
            },
        )

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
