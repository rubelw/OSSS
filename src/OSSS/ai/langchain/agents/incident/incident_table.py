from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
from collections import Counter

from pydantic import BaseModel, Field

from OSSS.ai.agents.query_data.query_data_registry import get_handler

logger = logging.getLogger("OSSS.ai.langchain.incidents_table")

SAFE_MAX_ROWS = 200


# ---------------------------------------------------------------------------
# Filters (expand later with dates, severity, etc.)
# ---------------------------------------------------------------------------

class IncidentsFilters(BaseModel):
    """
    Filters for incidents listings.
    All fields are optional.
    """
    behavior_code: Optional[List[str]] = Field(
        default=None,
        description="Only include incidents whose behavior_code matches any of these values.",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce_list(payload: Any, *, label: str) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("items", "data", "results", "rows", "incidents"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        logger.warning(
            "[incidents_table] %s payload dict had no list key. keys=%s",
            label,
            list(payload.keys())[:30],
        )
        return []
    logger.warning(
        "[incidents_table] %s payload unexpected type=%s",
        label,
        type(payload).__name__,
    )
    return []


async def _fetch_incident_rows(*, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Prefer QueryData handler 'incidents'.
    """
    handler = get_handler("incidents")
    if handler is None:
        logger.error("[incidents_table] No QueryData handler registered for mode='incidents'")
        return []

    result = await handler.fetch(ctx=None, skip=skip, limit=limit)
    rows = result.get("rows") or result.get("incidents") or []
    return _coerce_list(rows, label="incidents")


def _apply_filters(
    rows: List[Dict[str, Any]],
    filters: Optional[IncidentsFilters],
) -> List[Dict[str, Any]]:
    if not filters:
        return rows

    behavior_codes = {c.upper() for c in (filters.behavior_code or [])}

    def keep(r: Dict[str, Any]) -> bool:
        code = str(r.get("behavior_code") or "").upper()
        if behavior_codes and code not in behavior_codes:
            return False
        return True

    return [r for r in rows if keep(r)]


def _build_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No incident records matched your request."

    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |"
    sep = "| " + " | ".join(["---"] * len(header_cells)) + " |"
    lines = [header, sep]

    for i, r in enumerate(rows, start=1):
        cells = [str(i)]
        for f in fieldnames:
            v = r.get(f, "")
            s = "" if v is None else str(v)
            if len(s) > 120:
                s = s[:117] + "..."
            cells.append(s)
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public runners (same pattern as staff_info)
# ---------------------------------------------------------------------------

async def run_incidents_table_structured(
    *,
    filters: Optional[IncidentsFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    logger.info(
        "[incidents_table] called filters=%s",
        filters.model_dump() if filters else None,
    )

    rows = await _fetch_incident_rows(skip=skip, limit=limit)
    filtered = _apply_filters(rows, filters)

    by_behavior = Counter()
    for r in filtered:
        by_behavior[r.get("behavior_code") or "UNKNOWN"] += 1

    summary_lines = [
        f"I found {len(filtered)} incident records.",
        "",
        "By behavior code:",
        *[f"- {k}: {v}" for k, v in by_behavior.most_common()],
        "",
        "Sample (first 50):",
        "",
        _build_markdown_table(filtered[:50]),
    ]

    return {
        "reply": "\n".join(summary_lines),
        "rows": filtered,
        "filters": filters.model_dump() if filters else None,
    }


async def run_incidents_table_markdown_only(
    *,
    filters: Optional[IncidentsFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> str:
    result = await run_incidents_table_structured(
        filters=filters,
        session_id=session_id,
        skip=skip,
        limit=limit,
    )
    return result["reply"]
