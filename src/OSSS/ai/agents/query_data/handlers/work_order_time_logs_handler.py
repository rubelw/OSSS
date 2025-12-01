from __future__ import annotations

from typing import Any, Dict, List, Optional
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

logger = logging.getLogger("OSSS.ai.agents.query_data.work_order_time_logs")

API_BASE = "http://host.containers.internal:8081"


# ---------------------------------------------------------
# GENERIC FETCH HELPERS FOR RELATED LOOKUPS
# ---------------------------------------------------------

async def _fetch_json_list(url: str) -> List[Dict[str, Any]]:
    """Fetch a JSON list from an API, return [] if error."""
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.warning("Lookup failed for %s: %s", url, e)
        return []

    if isinstance(data, list):
        return data
    logger.warning("Lookup returned non-list: %s", url)
    return []


async def _fetch_work_order_time_logs(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/work_order_time_logs?skip={skip}&limit={limit}"
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.exception("Error calling work_order_time_logs API")
        raise QueryDataError(
            f"Error querying work_order_time_logs API: {e}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected work_order_time_logs payload type: {type(data)!r}"
        )
    return data


# ---------------------------------------------------------
# ENRICHMENT: JOIN work_order_time_logs → work_orders + users
# ---------------------------------------------------------

async def _enrich_logs(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return rows

    # Gather foreign keys
    work_order_ids = {r.get("work_order_id") for r in rows if r.get("work_order_id")}
    user_ids = {r.get("user_id") for r in rows if r.get("user_id")}

    # Fetch related records
    work_orders = await _fetch_json_list(f"{API_BASE}/api/work_orders?skip=0&limit=5000")
    users = await _fetch_json_list(f"{API_BASE}/api/users?skip=0&limit=5000")

    # Convert to lookup maps
    wo_map = {wo.get("id"): wo for wo in work_orders}
    user_map = {u.get("id"): u for u in users}

    enriched = []
    for r in rows:
        wo = wo_map.get(r.get("work_order_id"))
        user = user_map.get(r.get("user_id"))

        r2 = dict(r)  # copy

        # Add enriched fields
        r2["work_order_title"] = wo.get("title") if wo else None
        r2["work_order_number"] = wo.get("number") if wo else None
        r2["user_name"] = f"{user.get('first_name','')} {user.get('last_name','')}".strip() if user else None
        r2["user_email"] = user.get("email") if user else None

        enriched.append(r2)

    return enriched


# ---------------------------------------------------------
# MARKDOWN + CSV BUILDERS
# ---------------------------------------------------------

def _build_work_order_time_logs_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No work_order_time_logs records found."

    # Put enriched fields first if they exist
    enriched_fields = [
        "work_order_title",
        "work_order_number",
        "user_name",
        "user_email",
    ]

    raw_fields = [f for f in rows[0].keys() if f not in enriched_fields]
    fieldnames = enriched_fields + raw_fields

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_cells = [str(idx)] + [str(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


def _build_work_order_time_logs_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    enriched_fields = [
        "work_order_title",
        "work_order_number",
        "user_name",
        "user_email",
    ]
    raw_fields = [f for f in rows[0].keys() if f not in enriched_fields]
    fieldnames = enriched_fields + raw_fields

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------
# HANDLER
# ---------------------------------------------------------

class WorkOrderTimeLogsHandler(QueryHandler):
    mode = "work_order_time_logs"
    keywords = [
        "work order time logs",
        "work_order_time_logs",
        "time logs",
        "work order logs",
        "maintenance logs",
    ]
    source_label = "your DCG OSSS data service (work_order_time_logs)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_work_order_time_logs(skip=skip, limit=limit)
        rows = await _enrich_logs(rows)

        return {
            "rows": rows,
            "work_order_time_logs": rows,
            "joined": True,
            "join_note": "Enriched with work_orders and users",
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_work_order_time_logs_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_work_order_time_logs_csv(rows)


# register on import
register_handler(WorkOrderTimeLogsHandler())
