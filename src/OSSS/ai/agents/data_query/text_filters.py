# src/OSSS/ai/agents/data_query/text_filters.py

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from OSSS.ai.agents.data_query.queryspec import (
    QuerySpec,
    FilterCondition,
    FilterOp,
)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

def parse_text_filters(user_text: str, spec: QuerySpec) -> QuerySpec:
    """
    Parse a simple 'where ...' clause from user_text and append FilterCondition
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

    This function mutates and returns `spec` for convenience.
    """
    where_clause = _extract_where_clause(user_text)
    if not where_clause:
        return spec

    conditions = _split_conditions(where_clause)

    for cond in conditions:
        fc = _parse_single_condition(cond, spec)
        if fc:
            spec.filters.append(fc)

    return spec


# ---------------------------------------------------------------------------
# Step 1: extract the WHERE clause
# ---------------------------------------------------------------------------

_WHERE_RE = re.compile(r"\bwhere\b(.*)$", re.IGNORECASE | re.DOTALL)


def _extract_where_clause(text: str) -> Optional[str]:
    """
    Return the substring after 'where' if present, else None.
    """
    m = _WHERE_RE.search(text)
    if not m:
        return None
    clause = m.group(1).strip()
    return clause or None


# ---------------------------------------------------------------------------
# Step 2: split 'a and b and c' into individual condition strings
# ---------------------------------------------------------------------------

def _split_conditions(where_clause: str) -> List[str]:
    """
    Naive split on 'and' for now. You can extend to OR/parentheses later.
    """
    parts = re.split(r"\band\b", where_clause, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


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

    # 2) resolve field phrase to an actual field/path using synonyms + heuristics
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
# Step 4: resolve "last name" -> "last_name" or "person.full_name"
# ---------------------------------------------------------------------------

def _resolve_field_name(field_phrase: str, spec: QuerySpec) -> Optional[str]:
    """
    Resolve a natural language field phrase to a concrete field or path.

    Strategies:
      1) Exact match in spec.synonyms keys (case-insensitive)
      2) Normalized key (spaces -> underscores) in synonyms
      3) Direct match against projection field names
      4) Direct match against search_fields
    """
    raw = field_phrase.strip()
    lowered = raw.lower()

    # 1) Direct synonym lookup (case-insensitive)
    for k, v in spec.synonyms.items():
        if k.lower() == lowered:
            return v

    # 2) Normalized form: 'last name' -> 'last_name'
    normalized_key = lowered.replace(" ", "_")
    for k, v in spec.synonyms.items():
        if k.lower().replace(" ", "_") == normalized_key:
            return v

    # 3) Direct match against projection fields
    for proj in spec.projections:
        if proj.field.lower() == lowered:
            return proj.field
        if proj.field.lower().replace(" ", "_") == normalized_key:
            return proj.field

    # 4) Direct match against search_fields
    for sf in spec.search_fields:
        if sf.lower() == lowered:
            return sf
        if sf.lower().replace(" ", "_") == normalized_key:
            return sf

    # As a last resort, return normalized raw if it looks column-like
    if " " in raw:
        return normalized_key

    return None
