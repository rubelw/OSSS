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

logger = logging.getLogger("OSSS.ai.agents.query_data.student_transportation_assignments")

API_BASE = "http://host.containers.internal:8081"

# Keep markdown result sizes sane
SAFE_MAX_ROWS = 200


async def _fetch_student_transportation_assignments(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call /api/student_transportation_assignments with pagination
    and robust error handling.
    """
    url = f"{API_BASE}/api/student_transportation_assignments"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        logger.exception(
            "HTTP status error calling student_transportation_assignments API"
        )
        status = e.response.status_code if e.response else "unknown"
        raise QueryDataError(
            f"Error querying student_transportation_assignments API (HTTP {status}): {e}"
        ) from e

    except Exception as e:
        logger.exception("Error calling student_transportation_assignments API")
        raise QueryDataError(
            f"Error querying student_transportation_assignments API: {e}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected student_transportation_assignments payload type: {type(data)!r}"
        )

    return data


def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """
    Stringify and truncate cell values to keep tables readable.
    """
    if value is None:
        return ""
    s = str(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _build_student_transportation_assignments_markdown_table(
    rows: List[Dict[str, Any]]
) -> str:
    if not rows:
        return "No student_transportation_assignments records were found in the system."

    # Limit how many rows we render into markdown
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No student_transportation_assignments records were found in the system."

    # Prefer to show 'id' at the end if present
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body_lines: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row_cells = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(rec.get(f, "")) for f in fieldnames)
        body_lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body_lines)


def _build_student_transportation_assignments_csv(
    rows: List[Dict[str, Any]]
) -> str:
    """
    Build a CSV export of student_transportation_assignments.
    """
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


class StudentTransportationAssignmentsHandler(QueryHandler):
    """
    QueryData handler for student transportation assignments.

    Example prompts:
      - "show student transportation assignments"
      - "list transportation assignments"
      - "show bus assignments for students"
    """

    mode = "student_transportation_assignments"
    keywords = [
        "student_transportation_assignments",
        "student transportation assignments",
        "transportation assignments",
        "bus assignments",
        "student bus assignments",
        "show transportation assignments",
        "list student transportation",
    ]
    source_label = "your DCG OSSS data service (student_transportation_assignments)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_student_transportation_assignments(skip=skip, limit=limit)
        return {"rows": rows, "student_transportation_assignments": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_student_transportation_assignments_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_student_transportation_assignments_csv(rows)


# register on import
register_handler(StudentTransportationAssignmentsHandler())
