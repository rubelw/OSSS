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

logger = logging.getLogger("OSSS.ai.agents.query_data.section_room_assignments")

API_BASE = "http://host.containers.internal:8081"

# Safety cap for markdown output
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# API Fetch
# -------------------------------------------------------------------
async def _fetch_section_room_assignments(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call the OSSS data service for section_room_assignments records.

    Returns a list of dicts, each representing one section_room_assignments row.
    Raises QueryDataError on HTTP / payload issues.
    """
    url = f"{API_BASE}/api/section_room_assignments"
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
        logger.exception("HTTP error calling section_room_assignments API")
        # Keep QueryDataError simple/compatible: single message argument
        raise QueryDataError(
            f"HTTP {status} error querying section_room_assignments API: {str(e)}"
        ) from e

    except Exception as e:
        logger.exception("Error calling section_room_assignments API")
        raise QueryDataError(
            f"Error querying section_room_assignments API: {str(e)}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected section_room_assignments payload type: {type(data)!r}"
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
def _build_section_room_assignments_markdown_table(
    rows: List[Dict[str, Any]]
) -> str:
    if not rows:
        return "No section_room_assignments records were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No section_room_assignments records were found in the system."

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
def _build_section_room_assignments_csv(rows: List[Dict[str, Any]]) -> str:
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
class SectionRoomAssignmentsHandler(QueryHandler):
    mode = "section_room_assignments"
    keywords = [
        "section_room_assignments",
        "section room assignments",
        "room assignments by section",
        "which room is this section in",
        "classroom assignments",
        "section classroom assignments",
        "schedule room assignments",
        "show section room assignments",
        "list section room assignments",
    ]
    source_label = "your DCG OSSS data service (section_room_assignments)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_section_room_assignments(skip=skip, limit=limit)
        # Expose both generic "rows" and a typed key
        return {"rows": rows, "section_room_assignments": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_section_room_assignments_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_section_room_assignments_csv(rows)


# register on import
register_handler(SectionRoomAssignmentsHandler())
