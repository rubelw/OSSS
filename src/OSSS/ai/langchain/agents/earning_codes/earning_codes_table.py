# Auto-generated from QueryData handler mode="earning_codes"
from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from pydantic import BaseModel, Field

from OSSS.ai.agents.query_data.query_data_registry import get_handler

logger = logging.getLogger("OSSS.ai.langchain.earning_codes_table")

SAFE_MAX_ROWS = 200
MAX_MARKDOWN_ROWS = 50


class EarningCodesFilters(BaseModel):
    """Optional filters (extend later)."""
    q: Optional[str] = Field(
        default=None,
        description="Optional free-text filter (not applied by default).",
    )


def _coerce_list(payload: Any, *, label: str) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("items", "data", "results", "rows", "earning_codes"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        logger.warning(
            "[%s_table] %s payload dict had no list key. keys=%s",
            "earning_codes",
            label,
            list(payload.keys())[:30],
        )
        return []
    logger.warning(
        "[%s_table] %s payload unexpected type=%s",
        "earning_codes",
        label,
        type(payload).__name__,
    )
    return []


async def _fetch_rows(*, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    handler = get_handler("earning_codes")
    if handler is None:
        logger.error(
            "[%s_table] No QueryData handler registered for mode=%r",
            "earning_codes",
            "earning_codes",
        )
        return []

    result = await handler.fetch(ctx=None, skip=skip, limit=limit)
    rows = result.get("rows") or result.get("earning_codes") or []
    return _coerce_list(rows, label="earning_codes")


def _escape_md(value: Any) -> str:
    """
    Escape markdown-unfriendly characters for safe table rendering.
    """
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _build_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """
    Proper multi-line markdown table (avoids the "one-liner" rendering issue).
    """
    if not rows:
        return "No records matched your request."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    # stable-ish column order: first row keys, but push id to the end if present
    fieldnames = list(display[0].keys())
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"

    lines: List[str] = []
    for idx, r in enumerate(display, start=1):
        row_cells = [_escape_md(idx)] + [_escape_md(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {' | '.join(row_cells)} |")

    table = header + separator + "\n".join(lines)

    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} earning codes "
            "records. You can request CSV to see the full dataset._"
        )

    return table


async def run_earning_codes_table_structured(
    *,
    filters: Optional[EarningCodesFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    logger.info(
        "[%s_table] called filters=%s",
        "earning_codes",
        filters.model_dump() if filters else None,
    )

    rows = await _fetch_rows(skip=skip, limit=limit)
    rows = rows[:SAFE_MAX_ROWS]

    reply = "\n".join(
        [
            f"I found {len(rows)} earning codes records.",
            "",
            "Sample (first 50):",
            "",
            _build_markdown_table(rows),
        ]
    )

    return {
        "reply": reply,
        "rows": rows,
        "filters": filters.model_dump() if filters else None,
    }


async def run_earning_codes_table_markdown_only(
    *,
    filters: Optional[EarningCodesFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> str:
    result = await run_earning_codes_table_structured(
        filters=filters,
        session_id=session_id,
        skip=skip,
        limit=limit,
    )
    return result["reply"]
