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

logger = logging.getLogger("OSSS.ai.agents.query_data.student_section_enrollments")

API_BASE = "http://host.containers.internal:8081"

# keep markdown tables sane
SAFE_MAX_ROWS = 200


async def _fetch_student_section_enrollments(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """Call /api/student_section_enrollments with strong protection."""
    url = f"{API_BASE}/api/student_section_enrollments"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response else "unknown"
        logger.exception("HTTP status error calling student_section_enrollments API")
        raise QueryDataError(
            f"HTTP {status} error querying student_section_enrollments API: {str(e)}",
            student_section_enrollments_url=url,
        ) from e

    except Exception as e:
        logger.exception("Error calling student_section_enrollments API")
        raise QueryDataError(
            f"Error querying student_section_enrollments API: {str(e)}",
            student_section_enrollments_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected student_section_enrollments payload type: {type(data)!r}",
            student_section_enrollments_url=url,
        )

    return data


def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """Convert to safe short strings."""
    if value is None:
        return ""
    s = str(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _build_student_section_enrollments_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No student_section_enrollments records were found in the system."

    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No student_section_enrollments records were found in the system."

    # Put "id" last for readability
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row_cells = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(rec.get(f, "")) for f in fieldnames)
        body.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body)


def _build_student_section_enrollments_csv(rows: List[Dict[str, Any]]) -> str:
    """Export CSV."""
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


class StudentSectionEnrollmentsHandler(QueryHandler):
    """
    QueryData handler for student_section_enrollments.

    Example prompts:
      - "show student section enrollments"
      - "list section enrollments"
      - "get student schedule enrollments"
    """

    mode = "student_section_enrollments"
    keywords = [
        "student_section_enrollments",
        "student section enrollments",
        "section enrollments",
        "student schedule enrollments",
        "student class enrollments",
        "student enrollment list",
        "class enrollments",
        "show section enrollments",
        "list student enrollments",
    ]
    source_label = "your DCG OSSS data service (student_section_enrollments)"

    async def fetch(self, ctx: AgentContext, skip: int, limit: int) -> FetchResult:
        rows = await _fetch_student_section_enrollments(skip=skip, limit=limit)
        return {"rows": rows, "student_section_enrollments": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_student_section_enrollments_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_student_section_enrollments_csv(rows)


# Register handler
register_handler(StudentSectionEnrollmentsHandler())
