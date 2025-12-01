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

logger = logging.getLogger("OSSS.ai.agents.query_data.student_guardians")

API_BASE = "http://host.containers.internal:8081"

SAFE_MAX_ROWS = 200  # safety limit for markdown


# -------------------------------------------------------------------
# API Fetch
# -------------------------------------------------------------------
async def _fetch_student_guardians(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/student_guardians"
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
        logger.exception("HTTP error calling student_guardians API")
        raise QueryDataError(
            f"HTTP {status} error querying student_guardians API: {str(e)}",
            student_guardians_url=url,
        ) from e

    except Exception as e:
        logger.exception("Error calling student_guardians API")
        raise QueryDataError(
            f"Error querying student_guardians API: {str(e)}",
            student_guardians_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected student_guardians payload type: {type(data)!r}",
            student_guardians_url=url,
        )

    return data


# -------------------------------------------------------------------
# Utils
# -------------------------------------------------------------------
def _stringify_cell(value: Any, max_len: int = 120) -> str:
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_student_guardians_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No student_guardians records were found in the system."

    rows = rows[:SAFE_MAX_ROWS]  # enforce safety limit

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No student_guardians records were found in the system."

    # Place id column last
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


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_student_guardians_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# -------------------------------------------------------------------
# Handler
# -------------------------------------------------------------------
class StudentGuardiansHandler(QueryHandler):
    mode = "student_guardians"
    keywords = [
        "student_guardians",
        "student guardians",
        "guardians",
        "emergency contacts",
        "parent contacts",
        "guardian info",
        "guardian information",
        "student guardian list",
        "list student guardians",
        "show student guardians",
    ]
    source_label = "your DCG OSSS data service (student_guardians)"

    async def fetch(self, ctx: AgentContext, skip: int, limit: int) -> FetchResult:
        rows = await _fetch_student_guardians(skip=skip, limit=limit)
        return {"rows": rows, "student_guardians": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_student_guardians_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_student_guardians_csv(rows)


# register on import
register_handler(StudentGuardiansHandler())
