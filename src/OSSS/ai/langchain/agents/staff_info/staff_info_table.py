from __future__ import annotations

from typing import Any, Dict, List, Optional
from collections import Counter
import logging

from pydantic import BaseModel, Field

from OSSS.ai.agents.query_data.query_data_registry import get_handler

logger = logging.getLogger("OSSS.ai.langchain.staff_info_table")

SAFE_MAX_ROWS = 200


class StaffInfoFilters(BaseModel):
    """
    Filters for staff directory listings.
    All fields are optional; when omitted, that filter is not applied.
    """
    employee_number_prefix: Optional[str] = Field(
        default=None,
        description="Only include staff whose employee_number starts with this prefix (case-insensitive).",
    )
    title_contains: Optional[List[str]] = Field(
        default=None,
        description="Only include staff whose title contains ANY of these phrases (case-insensitive). Example: ['teacher','assistant']",
    )


def _coerce_list(payload: Any, *, label: str) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("items", "data", "results", "rows", "staff", "staffs"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        logger.warning("[staff_info_table] %s payload dict had no list key. keys=%s", label, list(payload.keys())[:30])
        return []
    logger.warning("[staff_info_table] %s payload unexpected type=%s", label, type(payload).__name__)
    return []


async def _fetch_staff_rows(*, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Prefer QueryData handler 'staff'. Falls back to empty list if missing.
    """
    handler = get_handler("staff")
    if handler is None:
        logger.error("[staff_info_table] No QueryData handler registered for mode='staff'")
        return []

    result = await handler.fetch(ctx=None, skip=skip, limit=limit)
    rows = result.get("rows") or result.get("staff") or result.get("staffs") or []
    return _coerce_list(rows, label="staff")


def _apply_filters(rows: List[Dict[str, Any]], filters: Optional[StaffInfoFilters]) -> List[Dict[str, Any]]:
    if not filters:
        return rows

    emp_pref = (filters.employee_number_prefix or "").strip().lower()
    title_terms = [t.strip().lower() for t in (filters.title_contains or []) if t and t.strip()]

    def keep(r: Dict[str, Any]) -> bool:
        emp = str(r.get("employee_number") or "").lower()
        title = str(r.get("title") or "").lower()

        if emp_pref and not emp.startswith(emp_pref):
            return False

        if title_terms and not any(term in title for term in title_terms):
            return False

        return True

    return [r for r in rows if keep(r)]


def _build_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No staff records matched your request."

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
            # protect the UI
            if len(s) > 120:
                s = s[:117] + "..."
            cells.append(s)
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


async def run_staff_info_table_structured(
    *,
    filters: Optional[StaffInfoFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    logger.info("[staff_info_table] called filters=%s", filters.model_dump() if filters else None)

    rows = await _fetch_staff_rows(skip=skip, limit=limit)
    filtered = _apply_filters(rows, filters)

    by_title = Counter()
    for r in filtered:
        by_title[r.get("title") or "UNKNOWN"] += 1

    summary_lines = [
        f"I found {len(filtered)} staff records.",
        "",
        "By title (top 10):",
        *[f"- {t}: {c}" for t, c in by_title.most_common(10)],
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


async def run_staff_info_table_markdown_only(
    *,
    filters: Optional[StaffInfoFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> str:
    result = await run_staff_info_table_structured(
        filters=filters, session_id=session_id, skip=skip, limit=limit
    )
    return result["reply"]
