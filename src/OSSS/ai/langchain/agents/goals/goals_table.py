from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
from collections import Counter

from pydantic import BaseModel, Field

from OSSS.ai.agents.query_data.query_data_registry import get_handler

logger = logging.getLogger("OSSS.ai.langchain.goals_table")

SAFE_MAX_ROWS = 200


class GoalsFilters(BaseModel):
    """
    Filters for goals listings (all optional).
    Keep this lightweight and expand as your goals schema stabilizes.
    """
    plan_id: Optional[List[str]] = Field(
        default=None,
        description="Only include goals whose plan_id matches any of these values.",
    )
    status: Optional[List[str]] = Field(
        default=None,
        description="Only include goals whose status matches any of these values (case-insensitive).",
    )
    school_year: Optional[List[str]] = Field(
        default=None,
        description="Only include goals whose school_year matches any of these values.",
    )


def _coerce_list(payload: Any, *, label: str) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("items", "data", "results", "rows", "goals"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        logger.warning(
            "[goals_table] %s payload dict had no list key. keys=%s",
            label,
            list(payload.keys())[:30],
        )
        return []
    logger.warning(
        "[goals_table] %s payload unexpected type=%s",
        label,
        type(payload).__name__,
    )
    return []


async def _fetch_goal_rows(*, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Prefer QueryData handler 'goals' (mode='goals').
    """
    handler = get_handler("goals")
    if handler is None:
        logger.error("[goals_table] No QueryData handler registered for mode='goals'")
        return []

    # NOTE: QueryData handlers in OSSS generally accept ctx=None; keep consistent with incidents_table.
    result = await handler.fetch(ctx=None, skip=skip, limit=limit)
    rows = result.get("rows") or result.get("goals") or []
    return _coerce_list(rows, label="goals")


def _apply_filters(rows: List[Dict[str, Any]], filters: Optional[GoalsFilters]) -> List[Dict[str, Any]]:
    if not filters:
        return rows

    plan_ids = {str(x).strip().lower() for x in (filters.plan_id or []) if str(x).strip()}
    statuses = {str(x).strip().lower() for x in (filters.status or []) if str(x).strip()}
    school_years = {str(x).strip().lower() for x in (filters.school_year or []) if str(x).strip()}

    def keep(r: Dict[str, Any]) -> bool:
        pid = str(r.get("plan_id") or "").strip().lower()
        st = str(r.get("status") or "").strip().lower()
        sy = str(r.get("school_year") or "").strip().lower()

        if plan_ids and pid not in plan_ids:
            return False
        if statuses and st not in statuses:
            return False
        if school_years and sy not in school_years:
            return False
        return True

    return [r for r in rows if keep(r)]


def _build_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No goal records matched your request."

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


async def run_goals_table_structured(
    *,
    filters: Optional[GoalsFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    logger.info(
        "[goals_table] called filters=%s",
        filters.model_dump() if filters else None,
    )

    rows = await _fetch_goal_rows(skip=skip, limit=limit)
    filtered = _apply_filters(rows, filters)

    by_plan = Counter()
    for r in filtered:
        by_plan[str(r.get("plan_id") or "UNKNOWN")] += 1

    summary_lines = [
        f"I found {len(filtered)} goal records.",
        "",
        "By plan_id:",
        *[f"- {k}: {v}" for k, v in by_plan.most_common()],
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


async def run_goals_table_markdown_only(
    *,
    filters: Optional[GoalsFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> str:
    result = await run_goals_table_structured(
        filters=filters,
        session_id=session_id,
        skip=skip,
        limit=limit,
    )
    return result["reply"]
