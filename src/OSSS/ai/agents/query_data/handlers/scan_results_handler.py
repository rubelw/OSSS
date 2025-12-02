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

logger = logging.getLogger("OSSS.ai.agents.query_data.scan_results")

API_BASE = "http://host.containers.internal:8081"

# Safety limit to prevent massive UI output
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# Low-level API fetch
# -------------------------------------------------------------------
async def _fetch_scan_results(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch scan results from the backend API.

    Wraps errors in QueryDataError so the QueryDataAgent can gracefully respond.
    """
    url = f"{API_BASE}/api/scan_results"
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
        logger.exception("HTTP error calling scan_results API")
        raise QueryDataError(
            f"HTTP {status} error querying scan_results API: {str(e)}"
        ) from e

    except Exception as e:
        logger.exception("Error calling scan_results API")
        raise QueryDataError(
            f"Error querying scan_results API: {str(e)}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected scan_results payload type: {type(data)!r}"
        )

    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify(value: Any, max_len: int = 140) -> str:
    """
    Convert to safe, trimmed string to avoid UI blowouts.
    """
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown Table Builder
# -------------------------------------------------------------------
def _build_scan_results_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No scan_results records were found in the system."

    # Safety limit
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No scan_results records were found in the system."

    # Move id to the end if present
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row_cells = [_stringify(idx)]
        row_cells.extend(_stringify(rec.get(f, "")) for f in fieldnames)
        body.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body)


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_scan_results_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    return output.getvalue()


# -------------------------------------------------------------------
# Handler Implementation
# -------------------------------------------------------------------
class ScanResultsHandler(QueryHandler):
    """
    Handler for scan_results records.
    Powers prompts like:
      - "show scan results"
      - "list all scan results"
      - "scan findings"
    """

    mode = "scan_results"
    keywords = [
        "scan_results",
        "scan results",
        "security scans",
        "scan findings",
        "scan output",
        "scanner results",
    ]
    source_label = "your DCG OSSS data service (scan_results)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_scan_results(skip=skip, limit=limit)
        return {"rows": rows, "scan_results": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_scan_results_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_scan_results_csv(rows)


# Register on import
register_handler(ScanResultsHandler())
