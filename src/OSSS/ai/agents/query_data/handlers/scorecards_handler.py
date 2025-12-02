# OSSS/ai/agents/query_data/handlers/scorecards_handler.py
from __future__ import annotations

from typing import Any, Dict, List
import csv
import httpx
import io
import logging

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.scorecards")

API_BASE = "http://host.containers.internal:8081"

# Safety cap for markdown output
SAFE_MAX_ROWS = 200


# ---------------------------------------------------------------------------
# Low-level fetch
# ---------------------------------------------------------------------------
async def _fetch_scorecards(
    *, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    scorecards_url = f"{API_BASE}/api/scorecards"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(scorecards_url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        status = (
            e.response.status_code
            if getattr(e, "response", None) is not None
            else "unknown"
        )
        logger.exception("HTTP error calling scorecards API")
        raise QueryDataError(
            f"HTTP {status} error querying scorecards API: {str(e)}",
            {"scorecards_url": scorecards_url, "status": status},
        ) from e
    except Exception as e:
        logger.exception("Error calling scorecards API")
        raise QueryDataError(
            f"Error querying scorecards API: {str(e)}",
            {"scorecards_url": scorecards_url},
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected scorecards payload type: {type(data)!r}",
            {"scorecards_url": scorecards_url},
        )

    return data


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """Convert a value to a trimmed, safe string for markdown tables."""
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def _order_scorecard_fields(fieldnames: List[str]) -> List[str]:
    """
    Put the most useful scorecard fields first, and move 'id' to the end
    if present, while preserving any other fields.
    """
    if not fieldnames:
        return fieldnames

    preferred_first = [
        "name",
        "plan_id",
        "created_at",
        "updated_at",
    ]

    ordered: List[str] = []
    for f in preferred_first:
        if f in fieldnames:
            ordered.append(f)

    for f in fieldnames:
        if f not in ordered and f != "id":
            ordered.append(f)

    if "id" in fieldnames:
        ordered.append("id")

    return ordered


# ---------------------------------------------------------------------------
# Markdown Builder
# ---------------------------------------------------------------------------
def _build_scorecard_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No scorecards were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    raw_fieldnames = list(rows[0].keys())
    if not raw_fieldnames:
        return "No scorecards were found in the system."

    fieldnames = _order_scorecard_fields(raw_fieldnames)

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body_lines: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row_cells: List[str] = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(rec.get(f, "")) for f in fieldnames)
        body_lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body_lines)


# ---------------------------------------------------------------------------
# CSV Builder
# ---------------------------------------------------------------------------
def _build_scorecard_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Handler implementation
# ---------------------------------------------------------------------------
class ScorecardsHandler(QueryHandler):
    mode = "scorecards"
    keywords = [
        "scorecard",
        "scorecards",
        "plan scores",
        "plan scorecards",
    ]
    source_label = "your DCG OSSS data service (scorecards)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_scorecards(skip=skip, limit=limit)
        return {
            "rows": rows,
            "scorecards": rows,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_scorecard_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_scorecard_csv(rows)


# register on import
register_handler(ScorecardsHandler())
