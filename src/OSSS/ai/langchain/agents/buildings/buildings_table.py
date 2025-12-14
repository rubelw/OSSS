from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
from pydantic import BaseModel, Field

from OSSS.ai.agents.query_data.query_data_registry import get_handler

logger = logging.getLogger("OSSS.ai.langchain.buildings_table")

SAFE_MAX_ROWS = 200


# ---------------------------------------------------------------------------
# Filters (expand later: use_type, year_built ranges, etc.)
# ---------------------------------------------------------------------------

class BuildingsFilters(BaseModel):
    code: Optional[List[str]] = Field(
        default=None,
        description="Only include buildings whose code matches any of these values.",
    )
    use_type: Optional[List[str]] = Field(
        default=None,
        description="Only include buildings whose use_type matches any of these values (e.g., academic).",
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
        for k in ("items", "data", "results", "rows", "buildings"):
            v = payload.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        logger.warning(
            "[buildings_table] %s payload dict had no list key. keys=%s",
            label,
            list(payload.keys())[:30],
        )
        return []
    logger.warning(
        "[buildings_table] %s payload unexpected type=%s",
        label,
        type(payload).__name__,
    )
    return []


async def _fetch_building_rows(*, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Prefer QueryData handler 'buildings' (mode='buildings').
    """
    handler = get_handler("buildings")
    if handler is None:
        logger.error("[buildings_table] No QueryData handler registered for mode='buildings'")
        return []

    # NOTE: your incidents_table passes ctx=None; keep consistent
    result = await handler.fetch(ctx=None, skip=skip, limit=limit)

    # Handler returns {"rows": rows, "buildings": rows, "meta": {...}}
    rows = result.get("rows") or result.get("buildings") or []
    return _coerce_list(rows, label="buildings")


def _apply_filters(
    rows: List[Dict[str, Any]],
    filters: Optional[BuildingsFilters],
) -> List[Dict[str, Any]]:
    if not filters:
        return rows

    codes = {c.upper() for c in (filters.code or [])}
    use_types = {u.lower() for u in (filters.use_type or [])}

    def keep(r: Dict[str, Any]) -> bool:
        code = str(r.get("code") or r.get("building_code") or "").upper()
        ut = str(r.get("use_type") or r.get("building_type") or "").lower()

        if codes and code not in codes:
            return False
        if use_types and ut not in use_types:
            return False
        return True

    return [r for r in rows if keep(r)]


def _build_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No building records matched your request."

    rows = rows[:SAFE_MAX_ROWS]

    # prefer a sane field order if those keys exist; otherwise fall back to whatever comes back
    preferred = [
        "code",
        "name",
        "address",
        "use_type",
        "year_built",
        "floors_count",
        "gross_sqft",
        "facility_id",
        "id",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    fieldnames = [k for k in preferred if k in all_keys]
    fieldnames.extend(k for k in all_keys if k not in fieldnames)

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
            cells.append(s.replace("|", r"\|"))
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public runners (same pattern as incidents_table)
# ---------------------------------------------------------------------------

async def run_buildings_table_structured(
    *,
    filters: Optional[BuildingsFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    logger.info(
        "[buildings_table] called filters=%s",
        filters.model_dump() if filters else None,
    )

    rows = await _fetch_building_rows(skip=skip, limit=limit)
    filtered = _apply_filters(rows, filters)

    summary_lines = [
        f"I found {len(filtered)} building records.",
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


async def run_buildings_table_markdown_only(
    *,
    filters: Optional[BuildingsFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> str:
    result = await run_buildings_table_structured(
        filters=filters,
        session_id=session_id,
        skip=skip,
        limit=limit,
    )
    return result["reply"]
