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

logger = logging.getLogger("OSSS.ai.agents.query_data.roles")

API_BASE = "http://host.containers.internal:8081"

SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# Fetch API
# -------------------------------------------------------------------
async def _fetch_roles(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/roles"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        status = (
            e.response.status_code
            if getattr(e, "response", None)
            else "unknown"
        )
        logger.exception("HTTP error calling roles API")
        raise QueryDataError(
            f"HTTP {status} error querying roles API: {str(e)}"
        ) from e

    except Exception as e:
        logger.exception("Error calling roles API")
        raise QueryDataError(
            f"Error querying roles API: {str(e)}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected roles payload type: {type(data)!r}"
        )

    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify(value: Any, max_len: int = 120) -> str:
    """Trim long cell values to avoid blowing up tables."""
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_roles_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No roles records were found in the system."

    rows = rows[:SAFE_MAX_ROWS]  # safety limit

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No roles records were found in the system."

    # Put id last
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body = []
    for idx, row in enumerate(rows, start=1):
        cells = [_stringify(idx)]
        cells.extend(_stringify(row.get(f, "")) for f in fieldnames)
        body.append("| " + " | ".join(cells) + " |")

    return header + separator + "\n".join(body)


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_roles_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    return output.getvalue()


# -------------------------------------------------------------------
# Handler
# -------------------------------------------------------------------
class RolesHandler(QueryHandler):
    mode = "roles"

    keywords = [
        "roles",
        "role list",
        "user roles",
        "permission roles",
        "system roles",
        "district roles",
        "what roles",
        "which roles",
        "show roles",
        "list roles",
    ]

    source_label = "your DCG OSSS data service (roles)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:

        rows = await _fetch_roles(skip=skip, limit=limit)
        return {"rows": rows, "roles": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_roles_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_roles_csv(rows)


# Register handler on import
register_handler(RolesHandler())
