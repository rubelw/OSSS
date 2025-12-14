from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
from collections import Counter

from pydantic import BaseModel, Field

from OSSS.ai.agents.query_data.query_data_registry import get_handler

logger = logging.getLogger("OSSS.ai.langchain.assets_table")

SAFE_MAX_ROWS = 200


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

class AssetsFilters(BaseModel):
    category: Optional[List[str]] = Field(
        default=None,
        description="Only include assets in these categories",
    )
    status: Optional[List[str]] = Field(
        default=None,
        description="Only include assets with these statuses",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce_list(payload: Any) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("rows", "assets", "items", "data"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


async def _fetch_asset_rows(skip: int, limit: int) -> List[Dict[str, Any]]:
    handler = get_handler("assets")
    if handler is None:
        logger.error("No QueryData handler registered for mode='assets'")
        return []

    result = await handler.fetch(ctx=None, skip=skip, limit=limit)
    rows = result.get("rows") or result.get("assets") or []
    return _coerce_list(rows)


def _apply_filters(
    rows: List[Dict[str, Any]],
    filters: Optional[AssetsFilters],
) -> List[Dict[str, Any]]:
    if not filters:
        return rows

    categories = {c.lower() for c in (filters.category or [])}
    statuses = {s.lower() for s in (filters.status or [])}

    def keep(r: Dict[str, Any]) -> bool:
        if categories and str(r.get("category", "")).lower() not in categories:
            return False
        if statuses and str(r.get("status", "")).lower() not in statuses:
            return False
        return True

    return [r for r in rows if keep(r)]


def _build_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No asset records matched your request."

    rows = rows[:SAFE_MAX_ROWS]

    preferred = [
        "asset_tag",
        "name",
        "category",
        "subcategory",
        "status",
        "manufacturer",
        "model",
        "serial_number",
        "building_id",
        "room_id",
        "assigned_to_staff_name",
        "assigned_to_student_name",
        "purchase_date",
        "purchase_price",
        "warranty_expiration",
        "is_active",
        "created_at",
        "updated_at",
        "id",
    ]

    keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in keys:
                keys.append(k)

    fieldnames = [k for k in preferred if k in keys] + [k for k in keys if k not in preferred]

    header = "| # | " + " | ".join(fieldnames) + " |"
    sep = "|---|" + "|".join(["---"] * len(fieldnames)) + "|"
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
# Public runners
# ---------------------------------------------------------------------------

async def run_assets_table_structured(
    *,
    filters: Optional[AssetsFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    rows = await _fetch_asset_rows(skip=skip, limit=limit)
    filtered = _apply_filters(rows, filters)

    by_category = Counter(r.get("category") or "UNKNOWN" for r in filtered)
    by_status = Counter(r.get("status") or "UNKNOWN" for r in filtered)

    reply = "\n".join(
        [
            f"I found {len(filtered)} asset records.",
            "",
            "By category:",
            *[f"- {k}: {v}" for k, v in by_category.most_common()],
            "",
            "By status:",
            *[f"- {k}: {v}" for k, v in by_status.most_common()],
            "",
            _build_markdown_table(filtered[:50]),
        ]
    )

    return {
        "reply": reply,
        "rows": filtered,
        "filters": filters.model_dump() if filters else None,
    }


async def run_assets_table_markdown_only(
    *,
    filters: Optional[AssetsFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> str:
    result = await run_assets_table_structured(
        filters=filters,
        session_id=session_id,
        skip=skip,
        limit=limit,
    )
    return result["reply"]
