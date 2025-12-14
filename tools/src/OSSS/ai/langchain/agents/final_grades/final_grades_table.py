# Auto-generated from QueryData handler mode="final_grades"
from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from pydantic import BaseModel, Field

from OSSS.ai.agents.query_data.query_data_registry import get_handler

logger = logging.getLogger("OSSS.ai.langchain.final_grades_table")

SAFE_MAX_ROWS = 200


class FinalGradesFilters(BaseModel):
    """Optional filters (extend later)."""
    q: Optional[str] = Field(default=None, description="Optional free-text filter (not applied by default).")


def _coerce_list(payload: Any, *, label: str) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("items", "data", "results", "rows", "final_grades"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        logger.warning("[%s_table] %s payload dict had no list key. keys=%s", "final_grades", label, list(payload.keys())[:30])
        return []
    logger.warning("[%s_table] %s payload unexpected type=%s", "final_grades", label, type(payload).__name__)
    return []


async def _fetch_rows(*, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    handler = get_handler("final_grades")
    if handler is None:
        logger.error("[%s_table] No QueryData handler registered for mode=%r", "final_grades", "final_grades")
        return []

    result = await handler.fetch(ctx=None, skip=skip, limit=limit)
    rows = result.get("rows") or result.get("final_grades") or []
    return _coerce_list(rows, label="final_grades")


def _build_markdown_table(rows: List[Dict[str, Any]], *, max_rows: int = 50) -> str:
    if not rows:
        return "No records matched your request."

    rows = rows[:max_rows]
    fieldnames = list(rows[0].keys())

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


async def run_final_grades_table_structured(
    *,
    filters: Optional[FinalGradesFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    logger.info("[%s_table] called filters=%s", "final_grades", filters.model_dump() if filters else None)

    rows = await _fetch_rows(skip=skip, limit=limit)
    rows = rows[:SAFE_MAX_ROWS]

    summary = [
        f"I found {len(rows)} final grades records.",
        "",
        "Sample (first 50):",
        "",
        _build_markdown_table(rows, max_rows=50),
    ]

    return {
        "reply": "\n".join(summary),
        "rows": rows,
        "filters": filters.model_dump() if filters else None,
    }


async def run_final_grades_table_markdown_only(
    *,
    filters: Optional[FinalGradesFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> str:
    result = await run_final_grades_table_structured(filters=filters, session_id=session_id, skip=skip, limit=limit)
    return result["reply"]
