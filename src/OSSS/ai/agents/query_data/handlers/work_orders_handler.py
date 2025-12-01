from __future__ import annotations

from typing import Any, Dict, List
import httpx
import csv
import io
import logging

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError  # optional

logger = logging.getLogger("OSSS.ai.agents.query_data.work_orders")

API_BASE = "http://host.containers.internal:8081"


# ---------------------------------------------------------------------------
# Low-level fetch
# ---------------------------------------------------------------------------
async def _fetch_work_orders(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Call the FastAPI /api/work_orders endpoint and return a list of dict rows.
    """
    url = f"{API_BASE}/api/work_orders"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.exception("Error calling work_orders API")
        # NOTE: QueryDataError only takes a message, so no extra kwargs.
        raise QueryDataError(f"Error querying work_orders API: {e}") from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected work_orders payload type: {type(data)!r}"
        )

    return data


# ---------------------------------------------------------------------------
# Helpers for table formatting
# ---------------------------------------------------------------------------
def _preferred_field_order(all_fields: List[str]) -> List[str]:
    """
    Reorder columns so the most useful work-order fields appear first.
    We keep any unknown fields at the end in their original order.
    """
    preferred = [
        "id",
        "title",
        "status",
        "priority",
        "asset_id",
        "location_id",
        "requester_id",
        "assigned_to_id",
        "created_at",
        "updated_at",
    ]

    ordered: List[str] = []
    for f in preferred:
        if f in all_fields and f not in ordered:
            ordered.append(f)

    for f in all_fields:
        if f not in ordered:
            ordered.append(f)

    return ordered


def _sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort newest work orders first if created_at is present.
    Otherwise, return rows as-is.
    """
    if not rows:
        return rows

    if "created_at" in rows[0]:
        try:
            return sorted(
                rows,
                key=lambda r: (r.get("created_at") or ""),
                reverse=True,
            )
        except Exception:
            # If something weird happens with created_at formats, don't blow up.
            logger.debug("Could not sort work_orders by created_at; returning unsorted.")
            return rows

    return rows


# ---------------------------------------------------------------------------
# Markdown & CSV builders
# ---------------------------------------------------------------------------
def _build_work_orders_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No work_orders records were found in the system."

    rows = _sort_rows(rows)
    raw_fieldnames = list(rows[0].keys())
    if not raw_fieldnames:
        return "No work_orders records were found in the system."

    fieldnames = _preferred_field_order(raw_fieldnames)

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_cells = [str(idx)] + [str(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


def _build_work_orders_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    rows = _sort_rows(rows)
    raw_fieldnames = list(rows[0].keys())
    if not raw_fieldnames:
        return ""

    fieldnames = _preferred_field_order(raw_fieldnames)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
class WorkOrdersHandler(QueryHandler):
    mode = "work_orders"
    keywords = [
        "work_orders",
        "work orders",
        "maintenance work orders",
        "maintenance tickets",
        "wo list",
    ]
    source_label = "your DCG OSSS data service (work_orders)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        """
        Fetch raw work_orders rows. If you later add enrichment
        (e.g., joining to assets/locations), you can expand this dict.
        """
        rows = await _fetch_work_orders(skip=skip, limit=limit)
        rows = _sort_rows(rows)

        return {
            "rows": rows,
            "work_orders": rows,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_work_orders_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_work_orders_csv(rows)


# register on import
register_handler(WorkOrdersHandler())
