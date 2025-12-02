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

logger = logging.getLogger("OSSS.ai.agents.query_data.round_decisions")

API_BASE = "http://host.containers.internal:8081"

# Safety cap for markdown output
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# Low-level API fetch
# -------------------------------------------------------------------
async def _fetch_round_decisions(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch round_decisions from the backend API.

    Wraps errors in QueryDataError so QueryDataAgent can handle them
    and surface a friendly error back to the user.
    """
    url = f"{API_BASE}/api/round_decisions"
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
        logger.exception("HTTP error calling round_decisions API")
        raise QueryDataError(
            f"HTTP {status} error querying round_decisions API: {str(e)}"
        ) from e

    except Exception as e:
        logger.exception("Error calling round_decisions API")
        raise QueryDataError(
            f"Error querying round_decisions API: {str(e)}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected round_decisions payload type: {type(data)!r}"
        )

    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify(value: Any, max_len: int = 140) -> str:
    """
    Convert a value to a safe, trimmed string for markdown/csv.
    """
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_round_decisions_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No round_decisions records were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No round_decisions records were found in the system."

    # Put id last if present, a bit more human-friendly
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body_lines: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row_cells: List[str] = [_stringify(idx)]
        row_cells.extend(_stringify(rec.get(f, "")) for f in fieldnames)
        body_lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body_lines)


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_round_decisions_csv(rows: List[Dict[str, Any]]) -> str:
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
class RoundDecisionsHandler(QueryHandler):
    """
    Handler for round_decisions (review round decisions, e.g., approved / revisions / rejected).

    Example questions this is meant to power:
      - "Show round decisions for proposals"
      - "List all round decisions"
      - "What decisions were made in the last review round?"
    """

    mode = "round_decisions"
    keywords = [
        "round_decisions",
        "round decisions",
        "review round decisions",
        "round review decisions",
        "decision rounds",
    ]
    source_label = "your DCG OSSS data service (round_decisions)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_round_decisions(skip=skip, limit=limit)
        return {"rows": rows, "round_decisions": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_round_decisions_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_round_decisions_csv(rows)


# register on import
register_handler(RoundDecisionsHandler())
