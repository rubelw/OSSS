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

logger = logging.getLogger("OSSS.ai.agents.query_data.resolutions")

API_BASE = "http://host.containers.internal:8081"

# Safety limit for markdown tables
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# API Fetch
# -------------------------------------------------------------------
async def _fetch_resolutions(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/resolutions"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        status = (
            e.response.status_code
            if getattr(e, "response", None) is not None
            else "unknown"
        )
        logger.exception("HTTP error calling resolutions API")
        raise QueryDataError(
            f"HTTP {status} error querying resolutions API: {str(e)}"
        ) from e

    except Exception as e:
        logger.exception("Error calling resolutions API")
        raise QueryDataError(
            f"Error querying resolutions API: {str(e)}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected resolutions payload type: {type(data)!r}"
        )
    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify_cell(value: Any, max_len: int = 140) -> str:
    """Convert a value to a trimmed, safe string for markdown tables."""
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_resolutions_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No resolutions records were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No resolutions records were found in the system."

    # Put id last if present
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body_lines: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row_cells: List[str] = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(rec.get(f, "")) for f in fieldnames)
        body_lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body_lines)


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_resolutions_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    first = rows[0]

    # Normal case: list of dicts from FastAPI
    if isinstance(first, dict):
        fieldnames = list(first.keys())
    else:
        # Fallbacks for object-like rows
        try:
            fieldnames = list(first.__dict__.keys())
            rows = [getattr(r, "__dict__", {"value": r}) for r in rows]
        except Exception:
            fieldnames = ["value"]
            rows = [{"value": r} for r in rows]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# -------------------------------------------------------------------
# Handler
# -------------------------------------------------------------------
class ResolutionsHandler(QueryHandler):
    mode = "resolutions"

    keywords = [
        "resolutions",
        "board resolutions",
        "policy resolutions",
        "meeting resolutions",
        "dcg resolutions",
        "osss resolutions",
        "adopted resolutions",
        "approved resolutions",
        "resolution records",
        "list resolutions",
        "show resolutions",
    ]

    source_label = "your DCG OSSS data service (resolutions)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_resolutions(skip=skip, limit=limit)
        return {"rows": rows, "resolutions": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_resolutions_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_resolutions_csv(rows)


# register on import
register_handler(ResolutionsHandler())
