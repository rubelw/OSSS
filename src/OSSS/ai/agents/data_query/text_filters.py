# src/OSSS/ai/agents/data_query/text_filters.py

from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

from OSSS.ai.agents.data_query.queryspec import (
    QuerySpec,
    FilterCondition,
    FilterOp,
)

log = logging.getLogger("OSSS.ai.agents.data_query.text_filters")

# ---------------------------------------------------------------------------
# Field aliases + normalization helpers
# ---------------------------------------------------------------------------

# Hand-rolled aliases for common human phrases → DB field names
FIELD_ALIASES = {
    "last name": "last_name",
    "lastname": "last_name",
    "surname": "last_name",

    "first name": "first_name",
    "firstname": "first_name",

    # Extend as needed:
    # "student id": "student_id",
    # "grade level": "grade_level",
}


def _normalize_field_name(raw: str, spec: QuerySpec) -> Optional[str]:
    """
    Map a human-ish field name ("last name") to a canonical DB field
    ("last_name") using:

      1. Hard-coded FIELD_ALIASES
      2. QuerySpec.synonyms (supports both styles):
         a) { "last name": "last_name" }
         b) { "last_name": ["last name", "surname"] }
      3. Snake-case fallback (spaces → underscores)

    Returns the normalized field name or None.
    """
    key = (raw or "").strip().lower()
    if not key:
        return None

    # 1) Explicit aliases first
    if key in FIELD_ALIASES:
        return FIELD_ALIASES[key]

    synonyms = getattr(spec, "synonyms", {}) or {}

    # 2a) Synonyms style A: {human_phrase: canonical}
    for k, v in synonyms.items():
        if str(k).lower() == key:
            return str(v)

    # 2b) Synonyms style B: {canonical: [aliases...]} (or a single alias)
    for canonical, aliases in synonyms.items():
        canonical_str = str(canonical).lower()
        if key == canonical_str:
            return str(canonical)

        if isinstance(aliases, (list, tuple, set)):
            alias_lower = {str(a).lower() for a in aliases}
            if key in alias_lower:
                return str(canonical)
        else:
            # Single string alias
            if key == str(aliases).lower():
                return str(canonical)

    # 3) Fallback: snake-case the raw key
    return key.replace(" ", "_")


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def parse_text_filters(user_text: str, spec: QuerySpec) -> QuerySpec:
    """
    Parse simple filter expressions from user_text and append FilterCondition
    objects to the given QuerySpec.

    Supported patterns (case-insensitive):
      - where last name starts with "R"
      - where last name starts with R
      - where status = active
      - where status is active
      - where created after 2024-01-01
      - where created before 2024-01-01

    Multiple conditions can be chained with 'and':
      - where status = active and last name starts with "R"

    NEW (inline without 'where'):
      - show me students with last name starting with "R"

    Also supports "filter" as a pseudo-where:
      - ... filter consent_type to start with 'D'

    This function mutates and returns `spec` for convenience.
    """
    text = (user_text or "").strip()
    if not text:
        return spec

    before_filters = len(spec.filters)

    # --- Classic WHERE / FILTER-clause parsing ------------------------------
    where_clause = _extract_where_clause(text)
    if where_clause:
        conditions = _split_conditions(where_clause)

        for cond in conditions:
            norm = _normalize_condition_text(cond)
            fc = _parse_single_condition(norm, spec)
            if fc:
                spec.filters.append(fc)

    # --- Inline "with ... starting with ..." pattern (no 'where' needed) ----
    # Only apply if the WHERE/FILTER-based parser didn't add anything new.
    if len(spec.filters) == before_filters:
        inline_fc = _parse_inline_startswith(text, spec)
        if inline_fc:
            spec.filters.append(inline_fc)

    added = len(spec.filters) - before_filters
    if added > 0:
        log.info(
            "[text_filters] Parsed %d filter(s) from text",
            added,
            extra={
                "event": "data_query_filters_parsed",
                "filters_count": added,
            },
        )
    else:
        log.info(
            "[text_filters] No filters parsed from text",
            extra={"event": "data_query_no_filters_parsed"},
        )

    return spec


# ---------------------------------------------------------------------------
# Step 1: extract the WHERE / FILTER clause
# ---------------------------------------------------------------------------

_WHERE_RE = re.compile(r"\bwhere\b(.*)$", re.IGNORECASE | re.DOTALL)
_FILTER_RE = re.compile(r"\bfilter\b(.*)$", re.IGNORECASE | re.DOTALL)


def _extract_where_clause(text: str) -> Optional[str]:
    """
    Return the substring after 'where' or 'filter' if present, else None.

    Priority:
      1) 'where ...'
      2) 'filter ...'
    """
    # Prefer explicit WHERE
    m = _WHERE_RE.search(text)
    if m:
        clause = m.group(1).strip()
        return clause or None

    # Fallback: treat 'filter ...' as a where-clause
    m = _FILTER_RE.search(text)
    if m:
        clause = m.group(1).strip()
        return clause or None

    return None


# ---------------------------------------------------------------------------
# Step 2: split 'a and b and c' into individual condition strings
# ---------------------------------------------------------------------------

def _split_conditions(where_clause: str) -> List[str]:
    """
    Naive split on 'and' for now. You can extend to OR/parentheses later.
    """
    parts = re.split(r"\band\b", where_clause, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _normalize_condition_text(cond: str) -> str:
    """
    Normalize loose natural language into something closer to our
    supported patterns.

    Examples:
      "filter consent_type to start with 'D'"
        -> "consent_type starts with 'D'"

      "filter to only show consent_type which start with 'D'"
        -> "consent_type starts with 'D'"
    """
    s = cond.strip()

    # Drop leading "filter" / "and filter"
    s = re.sub(r"^\s*(and\s+)?filter\s+", "", s, flags=re.IGNORECASE)

    # Common phrases → "starts with"
    s = re.sub(r"\bto\s+start\s+with\b", "starts with", s, flags=re.IGNORECASE)
    s = re.sub(r"\bwhich\s+start\s+with\b", "starts with", s, flags=re.IGNORECASE)
    s = re.sub(r"\bthat\s+start\s+with\b", "starts with", s, flags=re.IGNORECASE)

    return s


# ---------------------------------------------------------------------------
# Step 3: parse a single condition into FilterCondition
# ---------------------------------------------------------------------------

# order matters: we want to match multi-word ops first
_OPERATOR_PATTERNS: List[Tuple[re.Pattern, FilterOp]] = [
    # textual operators
    (re.compile(r"\bstarts?\s+with\b", re.IGNORECASE), "startswith"),
    (re.compile(r"\bcontains?\b", re.IGNORECASE), "contains"),
    (re.compile(r"\bis\s+not\b", re.IGNORECASE), "neq"),
    (re.compile(r"\bis\b", re.IGNORECASE), "eq"),
    (re.compile(r"\bon\s+or\s+after\b", re.IGNORECASE), "gte"),
    (re.compile(r"\bon\s+or\s+before\b", re.IGNORECASE), "lte"),
    (re.compile(r"\bafter\b", re.IGNORECASE), "gt"),
    (re.compile(r"\bbefore\b", re.IGNORECASE), "lt"),
    # symbolic operators
    (re.compile(r">=", re.IGNORECASE), "gte"),
    (re.compile(r"<=", re.IGNORECASE), "lte"),
    (re.compile(r">", re.IGNORECASE), "gt"),
    (re.compile(r"<", re.IGNORECASE), "lt"),
    (re.compile(r"==", re.IGNORECASE), "eq"),
    (re.compile(r"=", re.IGNORECASE), "eq"),
]


def _parse_single_condition(cond_text: str, spec: QuerySpec) -> Optional[FilterCondition]:
    """
    Parse one condition string like:
        "last name starts with \"R\""
        "status = active"
        "created after 2024-01-01"
    into a FilterCondition, or None if it can't be parsed.
    """
    cond_text = cond_text.strip()

    # 1) find the operator phrase
    match, op = _find_operator(cond_text)
    if not match:
        return None

    start, end = match.span()
    field_phrase = cond_text[:start].strip()
    value_phrase = cond_text[end:].strip()

    if not field_phrase or not value_phrase:
        return None

    # strip quotes around the value if present
    value = _strip_quotes(value_phrase)

    # 2) resolve field phrase to an actual field/path using aliases, synonyms, etc.
    resolved_field = _resolve_field_name(field_phrase, spec)
    if not resolved_field:
        return None

    return FilterCondition(field=resolved_field, op=op, value=value)


def _find_operator(cond_text: str) -> Tuple[Optional[re.Match], Optional[FilterOp]]:
    """
    Find the first matching operator pattern in the condition text.
    Returns (match, FilterOp) or (None, None).
    """
    for pattern, op in _OPERATOR_PATTERNS:
        m = pattern.search(cond_text)
        if m:
            return m, op
    return None, None


def _strip_quotes(value: str) -> str:
    """
    Remove surrounding single/double quotes if present.
    """
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


# ---------------------------------------------------------------------------
# Extra: inline "with ... starting with ..." (no 'where')
# ---------------------------------------------------------------------------

_INLINE_STARTS_WITH_RE = re.compile(
    r"\bwith\s+"
    r"(?P<field>[A-Za-z_][A-Za-z0-9_ ]*?)\s+"
    r"starting\s+with\s+'?(?P<value>[^\s']+)'?",
    re.IGNORECASE,
)


def _parse_inline_startswith(text: str, spec: QuerySpec) -> Optional[FilterCondition]:
    """
    Handle queries like:
        "show me students with last name starting with R"
        "students with last_name starting with 'Sm'"

    Returns a single FilterCondition or None.
    """
    m = _INLINE_STARTS_WITH_RE.search(text)
    if not m:
        return None

    raw_field = m.group("field")
    raw_value = m.group("value")

    field = _resolve_field_name(raw_field, spec)
    if not field:
        return None

    value = _strip_quotes(raw_value)
    if not value:
        return None

    return FilterCondition(field=field, op="startswith", value=value)


# ---------------------------------------------------------------------------
# Step 4: resolve "last name" -> "last_name" or "person.full_name"
# ---------------------------------------------------------------------------

def _resolve_field_name(field_phrase: str, spec: QuerySpec) -> Optional[str]:
    """
    Resolve a natural language field phrase to a concrete field or path.

    Strategies:
      1) FIELD_ALIASES + QuerySpec.synonyms via _normalize_field_name
      2) Direct match against projection field names
      3) Direct match against search_fields
      4) As a last resort, normalized "snake_case" of the raw phrase
         (no spaces in the final field name).
    """
    raw = (field_phrase or "").strip()
    if not raw:
        return None


    lowered = raw.lower()
    normalized_key = lowered.replace(" ", "_")

    # 1) Use alias + synonym-based normalization first
    normalized = _normalize_field_name(raw, spec)
    if normalized:
        # Ensure we never return a field with spaces, even from aliases.
        return normalized.replace(" ", "_")

    log.debug(
        "[text_filters] resolve_field_name",
        extra={
            "raw": raw,
            "lowered": lowered,
            "normalized_key": normalized_key,
        },
    )

    # 2) Direct match against projection fields
    for proj in getattr(spec, "projections", []) or []:
        pf = getattr(proj, "field", None)
        if not pf:
            continue
        pf_lower = pf.lower()

        # Exact match on raw, normalized, or their snake-case equivalents
        if (
            pf_lower == lowered
            or pf_lower == normalized_key
            or pf_lower.replace(" ", "_") == normalized_key
        ):
            return pf

    # 3) Direct match against search_fields
    for sf in getattr(spec, "search_fields", []) or []:
        sf_lower = sf.lower()
        if (
            sf_lower == lowered
            or sf_lower == normalized_key
            or sf_lower.replace(" ", "_") == normalized_key
        ):
            return sf

    # 4) As a last resort, ALWAYS return a snake_cased version
    #    so we never emit "consent type" as a field.
    return normalized_key
