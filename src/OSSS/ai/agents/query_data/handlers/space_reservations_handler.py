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

logger = logging.getLogger("OSSS.ai.agents.query_data.space_reservations")

API_BASE = "http://host.containers.internal:8081"

# Safety cap for markdown output
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# API Fetch
# -------------------------------------------------------------------
async def _fetch_space_reservations(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call the OSSS data service for space_reservations records.

    Returns a list of dicts, each representing one space_reservations row.
    Raises QueryDataError on HTTP / payload issues.
    """
    url = f"{API_BASE}/api/space_reservations"
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
        logger.exception("HTTP error calling space_reservations API")
        # Keep QueryDataError simple/compatible: single message argument
        raise QueryDataError(
            f"HTTP {status} error querying space_reservations API: {str(e)}"
        ) from e

    except Exception as e:
        logger.exception("Error calling space_reservations API")
        raise QueryDataError(
            f"Error querying space_reservations API: {str(e)}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected space_reservations payload type: {type(data)!r}"
        )

    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """
    Convert a value to a trimmed, safe string for markdown tables.
    Prevents huge blobs from wrecking the chat view.
    """
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_space_reservations_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No space_reservations records were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No space_reservations records were found in the system."

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
def _build_space_reservations_csv(rows: List[Dict[str, Any]]) -> str:
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
class SpaceReservationsHandler(QueryHandler):
    mode = "space_reservations"
    keywords = [
        "space_reservations",
        "space reservations",
        "facility reservations",
        "room reservations",
        "gym reservations",
        "auditorium reservations",
    ]
    source_label = "your DCG OSSS data service (space_reservations)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_space_reservations(skip=skip, limit=limit)
        # Expose both generic "rows" and a typed key
        return {"rows": rows, "space_reservations": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_space_reservations_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_space_reservations_csv(rows)


# register on import
register_handler(SpaceReservationsHandler())
