import json
import re
import os
from pathlib import Path


from typing import Any, Dict, List, Optional,Callable, Tuple

from OSSS.ai.agents.data_query.queryspec import QuerySpec, FilterCondition
from OSSS.ai.context import AgentContext

from OSSS.ai.agents.data_query.wizard_config import (
    WizardConfig,
    WizardFieldConfig,
)

from OSSS.ai.agents.data_query.config import (
    DataQueryRoute,
    resolve_route,
    find_route_for_text,
)

from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

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



NormalizerFn = Callable[[str], Any]


JSON_PATH = Path(__file__).resolve().parent.parent / "wizard_configs.json"



def normalize_consent_status(answer: str) -> str:
    text = (answer or "").strip().lower()
    if not text:
        return ""
    if any(w in text for w in ["grant", "granted", "yes", "yep", "allow",
                               "allowed", "approve", "approved", "ok", "okay"]):
        return "granted"
    if any(w in text for w in ["deny", "denied", "no", "nope",
                               "disallow", "refuse", "decline"]):
        return "denied"
    return text

# Map string names in JSON -> actual Python callables
_NORMALIZER_REGISTRY: Dict[str, NormalizerFn] = {
    "normalize_consent_status": normalize_consent_status,
    # add more here as you define them
}

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

def _load_wizard_configs_from_json(path: Path) -> Dict[str, WizardConfig]:
    """
    Load wizard configs from JSON.

    Supports both shapes:

      1) {
           "collections": {
             "consents": {
               "collection": "consents",
               "fields": [...]
             },
             ...
           }
         }

      2) {
           "consents": {
             "collection": "consents",
             "fields": [...]
           },
           ...
         }

    If 'collection' is missing on a config, we fall back to its dict key.
    """
    if not path.exists():
        logger.info("[wizard_config] JSON config not found at %s; using empty registry", path)
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        logger.exception(
            "[wizard_config] Failed to load JSON config; using empty registry",
            extra={"json_path": str(path)},
        )
        return {}

    if not isinstance(data, dict):
        logger.error(
            "[wizard_config] JSON root is not an object; using empty registry",
            extra={"json_type": type(data).__name__},
        )
        return {}

    # Accept either root["collections"] or the root itself as the collections map
    if "collections" in data and isinstance(data["collections"], dict):
        collections_data = data["collections"]
    else:
        collections_data = data

    result: Dict[str, WizardConfig] = {}

    for cfg_key, cfg in collections_data.items():
        if not isinstance(cfg, dict):
            logger.warning(
                "[wizard_config] Skipping non-dict config entry",
                extra={"key": cfg_key, "value_type": type(cfg).__name__},
            )
            continue

        collection_name = cfg.get("collection") or cfg_key
        raw_fields = cfg.get("fields", [])

        if not isinstance(raw_fields, list):
            logger.warning(
                "[wizard_config] 'fields' is not a list; skipping collection",
                extra={"collection": collection_name, "fields_type": type(raw_fields).__name__},
            )
            continue

        fields: List[WizardFieldConfig] = []

        for f in raw_fields:
            if not isinstance(f, dict):
                logger.warning(
                    "[wizard_config] Skipping non-dict field config",
                    extra={"collection": collection_name, "field_value_type": type(f).__name__},
                )
                continue

            name = f.get("name")
            if not name:
                logger.warning(
                    "[wizard_config] Field missing 'name'; skipping",
                    extra={"collection": collection_name, "field_config": f},
                )
                continue

            label = f.get("label") or name.replace("_", " ").title()
            required = bool(f.get("required", True))
            prompt = f.get("prompt")
            summary_label = f.get("summary_label") or label
            default_value = f.get("default_value")

            normalizer_name = f.get("normalizer")
            normalizer = None
            if isinstance(normalizer_name, str):
                normalizer = _NORMALIZER_REGISTRY.get(normalizer_name)
                if normalizer is None:
                    logger.warning(
                        "[wizard_config] Unknown normalizer; leaving as None",
                        extra={
                            "collection": collection_name,
                            "field": name,
                            "normalizer_name": normalizer_name,
                        },
                    )

            fields.append(
                WizardFieldConfig(
                    name=name,
                    label=label,
                    required=required,
                    prompt=prompt,
                    summary_label=summary_label,
                    normalizer=normalizer,
                    default_value=default_value,
                )
            )

        if not fields:
            logger.info(
                "[wizard_config] No valid fields for collection; skipping",
                extra={"collection": collection_name},
            )
            continue

        result[collection_name] = WizardConfig(
            collection=collection_name,
            fields=fields,
        )

    logger.info(
        "[wizard_config] Loaded %d wizard configs from %s",
        len(result),
        str(path),
    )
    return result

# Global registry loaded at import time
WIZARD_CONFIGS: Dict[str, WizardConfig] = _load_wizard_configs_from_json(JSON_PATH)


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

def get_wizard_config_for_collection(collection: str | None) -> Optional[WizardConfig]:
    if not collection:
        return None
    cfg = WIZARD_CONFIGS.get(collection)
    if not cfg:
        logger.debug(
            "[wizard_config] no wizard config for collection",
            extra={"collection": collection},
        )
    return cfg

def get_wizard_state(context: AgentContext) -> Optional[Dict[str, Any]]:
    exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
    return exec_state.get("wizard")  # returns dict or None


def set_wizard_state(context: AgentContext, state: Optional[Dict[str, Any]]) -> None:
    exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
    if state:
        exec_state["wizard"] = state
    else:
        exec_state.pop("wizard", None)
    context.execution_state = exec_state


def wizard_channel_key(agent_name: str, collection: Optional[str] = None) -> str:
    if collection:
        return f"{agent_name}:wizard:{collection}"
    return f"{agent_name}:wizard"


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


