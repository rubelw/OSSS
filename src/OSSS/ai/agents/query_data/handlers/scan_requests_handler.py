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

logger = logging.getLogger("OSSS.ai.agents.query_data.scan_requests")

API_BASE = "http://host.containers.internal:8081"

# Safety cap for markdown output
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# Low-level API fetch
# -------------------------------------------------------------------
async def _fetch_scan_requests(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch scan_requests from the backend API.

    Wraps errors in QueryDataError so QueryDataAgent can handle them
    and surface a friendly error back to the user.
    """
    url = f"{API_BASE}/api/scan_requests"
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
        logger.exception("HTTP error calling scan_requests API")
        raise QueryDataError(
            f"HTTP {status} error querying scan_requests API: {str(e)}"
        ) from e

    except Exception as e:
        logger.exception("Error calling scan_requests API")
        raise QueryDataError(
            f"Error querying scan_requests API: {str(e)}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected scan_requests payload type: {type(data)!r}"
        )

    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify(value: Any, max_len: int = 140) -> str:
    """
    Convert a value to a safe, trimmed string for markdown/csv.
    """
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_scan_requests_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No scan_requests records were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No scan_requests records were found in the system."

    # Put id last if present (more human-friendly)
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body_lines: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row_cells: List[str] = [_stringify(idx)]
        row_cells.extend(_stringify(rec.get(f, "")) for f in fieldnames)
        body_lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body_lines)


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_scan_requests_csv(rows: List[Dict[str, Any]]) -> str:
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
class ScanRequestsHandler(QueryHandler):
    """
    Handler for scan_requests records.

    Example questions this is meant to power:
      - "Show scan requests"
      - "List all scan requests"
      - "What scans have been requested?"
    """

    mode = "scan_requests"
    keywords = [
        "scan_requests",
        "scan requests",
        "scan queue",
        "queued scans",
        "requested scans",
        "pending scans",
        "scheduled scans",
    ]
    source_label = "your DCG OSSS data service (scan_requests)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_scan_requests(skip=skip, limit=limit)
        return {"rows": rows, "scan_requests": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_scan_requests_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_scan_requests_csv(rows)


# register on import
register_handler(ScanRequestsHandler())
