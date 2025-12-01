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

logger = logging.getLogger("OSSS.ai.agents.query_data.teacher_section_assignments")

API_BASE = "http://host.containers.internal:8081"

# Limit markdown output so responses never exceed token budgets
SAFE_MAX_ROWS = 200


async def _fetch_teacher_section_assignments(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch records from /api/teacher_section_assignments.
    Produces helpful debugging logs and wraps exceptions in QueryDataError.
    """
    url = f"{API_BASE}/api/teacher_section_assignments"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP status error calling teacher_section_assignments API")
        status = e.response.status_code if e.response is not None else "unknown"
        raise QueryDataError(
            f"Error querying teacher_section_assignments API (HTTP {status}): {e}"
        ) from e

    except Exception as e:
        logger.exception("Error calling teacher_section_assignments API")
        raise QueryDataError(
            f"Error querying teacher_section_assignments API: {e}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected teacher_section_assignments payload type: {type(data)!r}"
        )

    return data


def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """
    Safely stringify a table cell value, trimming large values.
    """
    if value is None:
        return ""
    s = str(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _build_teacher_section_assignments_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No teacher_section_assignments records were found in the system."

    # Trim number of displayed rows to prevent runaway output
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No teacher_section_assignments records were found in the system."

    # Prefer ID field last so relevant fields show earlier
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, record in enumerate(rows, start=1):
        row_cells = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(record.get(f, "")) for f in fieldnames)
        lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


def _build_teacher_section_assignments_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class TeacherSectionAssignmentsHandler(QueryHandler):
    """
    QueryData handler for teacher_section_assignments.

    Trigger examples:
      - "show teacher section assignments"
      - "list teacher_section_assignments"
      - "export teacher section assignments as csv"
    """

    mode = "teacher_section_assignments"
    keywords = [
        "teacher_section_assignments",
        "teacher section assignments",
        "teacher-section assignments",
        "teacher assignment sections",
        "teacher assignments by section",
    ]
    source_label = "your DCG OSSS data service (teacher_section_assignments)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_teacher_section_assignments(skip=skip, limit=limit)
        return {"rows": rows, "teacher_section_assignments": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_teacher_section_assignments_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_teacher_section_assignments_csv(rows)


# Register on import
register_handler(TeacherSectionAssignmentsHandler())
