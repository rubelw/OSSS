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

logger = logging.getLogger("OSSS.ai.agents.query_data.work_order_tasks")

API_BASE = "http://host.containers.internal:8081"


# ------------------------------------------------------------------------------
# FETCH HELPERS
# ------------------------------------------------------------------------------

async def _fetch_json(url: str, params: dict | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Error calling API: %s", url)
        raise QueryDataError(f"Error calling API: {url} -> {e}")


async def _fetch_work_order_tasks(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/work_order_tasks"
    data = await _fetch_json(url, {"skip": skip, "limit": limit})

    if not isinstance(data, list):
        raise QueryDataError(f"Unexpected work_order_tasks response type: {type(data)}")

    return data


async def _fetch_work_orders() -> Dict[str, Dict[str, Any]]:
    """Return work_orders as a dict keyed by id."""
    url = f"{API_BASE}/api/work_orders"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    return {row["id"]: row for row in data if "id" in row}


async def _fetch_users() -> Dict[str, Dict[str, Any]]:
    """Return users as dict keyed by id."""
    url = f"{API_BASE}/api/users"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    return {row["id"]: row for row in data if "id" in row}


# ------------------------------------------------------------------------------
# TABLE BUILDERS
# ------------------------------------------------------------------------------

def _build_work_order_tasks_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No work_order_tasks records were found in the system."

    fieldnames = list(rows[0].keys())

    header = "| # | " + " | ".join(fieldnames) + " |\n"
    separator = "|---|" + "|".join(["---"] * len(fieldnames)) + "|\n"

    body_lines = []
    for idx, r in enumerate(rows, start=1):
        body = " | ".join(str(r.get(f, "")) for f in fieldnames)
        body_lines.append(f"| {idx} | {body} |")

    return header + separator + "\n".join(body_lines)


def _build_work_order_tasks_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# ------------------------------------------------------------------------------
# QUERY HANDLER
# ------------------------------------------------------------------------------

class WorkOrderTasksHandler(QueryHandler):
    mode = "work_order_tasks"
    keywords = [
        "work_order_tasks",
        "work order tasks",
        "wo tasks",
        "maintenance tasks",
        "work order task list",
    ]
    source_label = "your DCG OSSS data service (work_order_tasks)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:

        rows = await _fetch_work_order_tasks(skip=skip, limit=limit)

        # ------------------------------------------------------------------
        # Optional enrichment: Join work_order + user information
        # ------------------------------------------------------------------

        try:
            work_orders = await _fetch_work_orders()
        except Exception:
            work_orders = {}

        try:
            users = await _fetch_users()
        except Exception:
            users = {}

        enriched = []
        for r in rows:
            wo = work_orders.get(r.get("work_order_id"))
            user = users.get(r.get("user_id"))

            enriched.append({
                **r,
                "work_order_name": wo.get("name") if wo else None,
                "user_name": user.get("name") if user else None,
            })

        return {
            "rows": enriched,
            "work_order_tasks": enriched,
            "enrichment": {
                "work_orders_loaded": len(work_orders),
                "users_loaded": len(users)
            }
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_work_order_tasks_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_work_order_tasks_csv(rows)


# auto-register on import
register_handler(WorkOrderTasksHandler())
