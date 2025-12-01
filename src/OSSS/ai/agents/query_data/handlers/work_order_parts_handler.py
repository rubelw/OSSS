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
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.work_order_parts")

API_BASE = "http://host.containers.internal:8081"


# ------------------------------------------------------------------------------
# Shared fetch helper
# ------------------------------------------------------------------------------

async def _fetch_json(url: str, params: Dict[str, Any] | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Error calling API: %s", url)
        # Keep QueryDataError simple so we don't hit unexpected kwargs issues
        raise QueryDataError(f"Error calling API {url}: {e}") from e


# ------------------------------------------------------------------------------
# Table-specific fetch helpers
# ------------------------------------------------------------------------------

async def _fetch_work_order_parts(
    skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/work_order_parts"
    data = await _fetch_json(url, {"skip": skip, "limit": limit})

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected work_order_parts payload type: {type(data)!r}"
        )
    return data


async def _fetch_work_orders() -> Dict[str, Dict[str, Any]]:
    """
    Load work_orders keyed by id for enrichment.
    """
    url = f"{API_BASE}/api/work_orders"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected work_orders payload type: {type(data)!r}"
        )
    return {row["id"]: row for row in data if isinstance(row, dict) and "id" in row}


async def _fetch_parts() -> Dict[str, Dict[str, Any]]:
    """
    Load parts keyed by id for enrichment.
    """
    url = f"{API_BASE}/api/parts"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected parts payload type: {type(data)!r}"
        )
    return {row["id"]: row for row in data if isinstance(row, dict) and "id" in row}


# ------------------------------------------------------------------------------
# Markdown / CSV builders
# ------------------------------------------------------------------------------

def _build_work_order_parts_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No work_order_parts records were found in the system."

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No work_order_parts records were found in the system."

    header = "| # | " + " | ".join(fieldnames) + " |\n"
    separator = "|---|" + "|".join(["---"] * len(fieldnames)) + "|\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_vals = [str(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {idx} | " + " | ".join(row_vals) + " |")

    return header + separator + "\n".join(lines)


def _build_work_order_parts_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ------------------------------------------------------------------------------
# Handler
# ------------------------------------------------------------------------------

class WorkOrderPartsHandler(QueryHandler):
    mode = "work_order_parts"
    keywords = [
        "work_order_parts",
        "work order parts",
        "wo parts",
        "maintenance parts used",
        "parts used on work orders",
    ]
    source_label = "your DCG OSSS data service (work_order_parts)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        # Base table
        parts_rows = await _fetch_work_order_parts(skip=skip, limit=limit)

        # Enrichment: work_orders + parts lookups
        try:
            work_orders = await _fetch_work_orders()
        except Exception:
            work_orders = {}

        try:
            parts = await _fetch_parts()
        except Exception:
            parts = {}

        enriched: List[Dict[str, Any]] = []
        for row in parts_rows:
            wo = work_orders.get(row.get("work_order_id"))
            part = parts.get(row.get("part_id"))

            enriched.append(
                {
                    **row,
                    # Enriched columns (best-effort, depends on API fields)
                    "work_order_name": (
                        wo.get("name")
                        if isinstance(wo, dict)
                        else None
                    ),
                    "part_name": (
                        part.get("name")
                        if isinstance(part, dict)
                        else None
                    ),
                    "part_sku": (
                        part.get("sku")
                        if isinstance(part, dict)
                        else None
                    ),
                }
            )

        return {
            "rows": enriched,
            "work_order_parts": enriched,
            "enrichment": {
                "work_orders_loaded": len(work_orders),
                "parts_loaded": len(parts),
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_work_order_parts_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_work_order_parts_csv(rows)


# register on import
register_handler(WorkOrderPartsHandler())
