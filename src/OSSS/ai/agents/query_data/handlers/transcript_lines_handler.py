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

logger = logging.getLogger("OSSS.ai.agents.query_data.transcript_lines")

API_BASE = "http://host.containers.internal:8081"

# Keep tables from blowing up the UI
SAFE_MAX_ROWS = 200


async def _fetch_transcript_lines(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call the backend /api/transcript_lines endpoint and return a list of records.

    Raises QueryDataError if the HTTP request fails or if the payload is not a list.
    """
    url = f"{API_BASE}/api/transcript_lines"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.exception("HTTP error calling transcript_lines API")
        status = e.response.status_code if e.response is not None else "unknown"
        raise QueryDataError(
            f"Error querying transcript_lines API (HTTP {status}): {e}"
        ) from e
    except Exception as e:
        logger.exception("Error calling transcript_lines API")
        raise QueryDataError(
            f"Error querying transcript_lines API: {e}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected transcript_lines payload type: {type(data)!r}"
        )

    return data


def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """
    Make values safe for markdown; truncate long strings so tables stay readable.
    """
    if value is None:
        return ""
    s = str(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _build_transcript_lines_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No transcript_lines records were found in the system."

    # Trim to a safe size for display
    rows = rows[:SAFE_MAX_ROWS]

    # Use the keys from the first row as our canonical column order
    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No transcript_lines records were found in the system."

    # Optional: move 'id' to the end so the interesting fields come first
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_cells = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(r.get(f, "")) for f in fieldnames)
        lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


def _build_transcript_lines_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class TranscriptLinesHandler(QueryHandler):
    """
    QueryData handler for the transcript_lines table.

    Example trigger phrases:
      - "show transcript lines"
      - "list transcript_lines"
      - "export transcript lines as csv"
    """

    mode = "transcript_lines"
    keywords = [
        "transcript_lines",
        "transcript lines",
    ]
    source_label = "your DCG OSSS data service (transcript_lines)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_transcript_lines(skip=skip, limit=limit)
        # You can hang extra things off the result later (e.g., aggregates)
        return {"rows": rows, "transcript_lines": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_transcript_lines_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_transcript_lines_csv(rows)


# register on import
register_handler(TranscriptLinesHandler())
