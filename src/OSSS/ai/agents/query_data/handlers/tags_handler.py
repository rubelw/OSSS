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

logger = logging.getLogger("OSSS.ai.agents.query_data.tags")

API_BASE = "http://host.containers.internal:8081"

# Limit rows returned in markdown so answers never exceed token budgets
SAFE_MAX_ROWS = 200


async def _fetch_tags(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch records from /api/tags with robust error handling.
    """
    url = f"{API_BASE}/api/tags"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        logger.exception("HTTP status error calling tags API")
        status = e.response.status_code if e.response else "unknown"
        raise QueryDataError(
            f"Error querying tags API (HTTP {status}): {e}"
        ) from e

    except Exception as e:
        logger.exception("Error calling tags API")
        raise QueryDataError(f"Error querying tags API: {e}") from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected tags payload type: {type(data)!r}"
        )

    return data


def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """
    Stringify a table cell, trimming very long values for safer markdown.
    """
    if value is None:
        return ""
    s = str(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _build_tags_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No tags records were found in the system."

    # Cap number of rows displayed
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())

    # Move "id" field to end if present (readability)
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


def _build_tags_csv(rows: List[Dict[str, Any]]) -> str:
    """
    Create a CSV export of the tags records.
    """
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


class TagsHandler(QueryHandler):
    """
    QueryData handler for tags.

    Useful for quick tag lookups:
      - "show tags"
      - "list all tags"
      - "export tags"
    """

    mode = "tags"
    keywords = [
        "tags",
        "list tags",
        "tag list",
        "show tags",
        "all tags",
    ]

    source_label = "your DCG OSSS data service (tags)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_tags(skip=skip, limit=limit)
        return {"rows": rows, "tags": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_tags_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_tags_csv(rows)


# Register on import
register_handler(TagsHandler())
