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

logger = logging.getLogger("OSSS.ai.agents.query_data.subjects")

API_BASE = "http://host.containers.internal:8081"

# Keep markdown result sizes sane
SAFE_MAX_ROWS = 200


async def _fetch_subjects(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call /api/subjects with basic pagination and robust error handling.
    """
    url = f"{API_BASE}/api/subjects"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP status error calling subjects API")
        status = e.response.status_code if e.response else "unknown"
        raise QueryDataError(
            f"Error querying subjects API (HTTP {status}): {e}"
        ) from e

    except Exception as e:
        logger.exception("Error calling subjects API")
        raise QueryDataError(f"Error querying subjects API: {e}") from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected subjects payload type: {type(data)!r}"
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


def _build_subjects_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No subjects records were found in the system."

    # Limit how many rows we render into markdown
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No subjects records were found in the system."

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


def _build_subjects_csv(rows: List[Dict[str, Any]]) -> str:
    """
    Build a CSV export of subjects.
    """
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


class SubjectsHandler(QueryHandler):
    """
    QueryData handler for subjects.

    Example prompts:
      - "show subjects"
      - "list course subjects"
      - "export subjects"
    """

    mode = "subjects"
    keywords = [
        "subjects",
        "course subjects",
        "subject list",
        "list subjects",
        "show subjects",
        "all subjects",
    ]
    source_label = "your DCG OSSS data service (subjects)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_subjects(skip=skip, limit=limit)
        return {"rows": rows, "subjects": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_subjects_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_subjects_csv(rows)


# Register on import
register_handler(SubjectsHandler())
