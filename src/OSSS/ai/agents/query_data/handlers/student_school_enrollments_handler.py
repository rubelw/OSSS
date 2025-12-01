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

logger = logging.getLogger("OSSS.ai.agents.query_data.student_school_enrollments")

API_BASE = "http://host.containers.internal:8081"

# Cap markdown rows so responses stay readable
SAFE_MAX_ROWS = 200


async def _fetch_student_school_enrollments(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call /api/student_school_enrollments with defensive error handling.
    """
    url = f"{API_BASE}/api/student_school_enrollments"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        logger.exception("HTTP status error calling student_school_enrollments API")
        raise QueryDataError(
            f"HTTP {status} error querying student_school_enrollments API: {str(e)}",
            student_school_enrollments_url=url,
        ) from e

    except Exception as e:
        logger.exception("Error calling student_school_enrollments API")
        raise QueryDataError(
            f"Error querying student_school_enrollments API: {str(e)}",
            student_school_enrollments_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected student_school_enrollments payload type: {type(data)!r}",
            student_school_enrollments_url=url,
        )

    return data


def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """Convert values to trimmed strings for markdown tables."""
    if value is None:
        return ""
    s = str(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _build_student_school_enrollments_markdown_table(
    rows: List[Dict[str, Any]]
) -> str:
    if not rows:
        return "No student_school_enrollments records were found in the system."

    # avoid massive tables in chat
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No student_school_enrollments records were found in the system."

    # put id last if present
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


def _build_student_school_enrollments_csv(rows: List[Dict[str, Any]]) -> str:
    """Return CSV representation of the result set."""
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


class StudentSchoolEnrollmentsHandler(QueryHandler):
    """
    QueryData handler for student_school_enrollments.

    Example user prompts:
      - "show student school enrollments"
      - "list school enrollments for students"
      - "student enrollment by school"
    """

    mode = "student_school_enrollments"
    keywords = [
        "student_school_enrollments",
        "student school enrollments",
        "school enrollments",
        "student school enrollment list",
        "student enrollment by school",
        "student building enrollments",
        "school-level student enrollments",
        "show student school enrollments",
        "list student school enrollments",
    ]
    source_label = "your DCG OSSS data service (student_school_enrollments)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_student_school_enrollments(skip=skip, limit=limit)
        return {"rows": rows, "student_school_enrollments": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_student_school_enrollments_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_student_school_enrollments_csv(rows)


# register on import
register_handler(StudentSchoolEnrollmentsHandler())
