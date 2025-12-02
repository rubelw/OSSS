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
from OSSS.ai.ai_rules.intent_rules import IntentHeuristicRule

logger = logging.getLogger("OSSS.ai.agents.query_data.report_cards")

API_BASE = "http://host.containers.internal:8081"

# Safety cap for markdown output
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# API Fetch
# -------------------------------------------------------------------
async def _fetch_report_cards(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Call the backend report_cards API and return a list of dict rows.

    Expected payload (example):

    [
      {
        "student_id": "6eff14cc-a22d-5b3f-806f-516ae7a06f98",
        "term_id": "ce1b7447-3806-57cd-997f-a0adb99964b2",
        "published_at": "2025-09-05T18:25:42+00:00",
        "created_at": "2025-09-05T18:25:42+00:00",
        "updated_at": "2025-09-05T18:25:42+00:00",
        "id": "e505a3a9-ead8-561c-aa4b-0f18cc1f24a3"
      }
    ]

    Raises:
        QueryDataError: if the HTTP call fails or the payload is not a list.
    """
    url = f"{API_BASE}/api/report_cards"
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
        logger.exception("HTTP error calling report_cards API")
        raise QueryDataError(
            f"HTTP {status} error querying report_cards API: {str(e)}"
        ) from e

    except Exception as e:
        logger.exception("Error calling report_cards API")
        raise QueryDataError(
            f"Error querying report_cards API: {str(e)}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected report_cards payload type: {type(data)!r}"
        )

    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """
    Convert a value to a trimmed, safe string for markdown tables.
    """
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_report_cards_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """
    Build a markdown table for report_cards.

    Applies SAFE_MAX_ROWS and trims cell length to keep output readable.
    """
    if not rows:
        return "No report_cards records were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No report_cards records were found in the system."

    # Put id last if present, for readability
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body_lines: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row_cells: List[str] = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(rec.get(f, "")) for f in fieldnames)
        body_lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(body_lines)


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_report_cards_csv(rows: List[Dict[str, Any]]) -> str:
    """
    Build a CSV string from report_cards rows.

    Assumes rows is a list of dict-like objects (standard FastAPI/ORM JSON).
    """
    if not rows:
        return ""

    first = rows[0]

    if isinstance(first, dict):
        fieldnames = list(first.keys())
    else:
        # Extremely defensive fallback: try to treat it like an object
        try:
            fieldnames = list(first.__dict__.keys())
            # Map objects to dicts for DictWriter
            rows = [getattr(r, "__dict__", {"value": r}) for r in rows]
        except Exception:
            # Last-ditch: stringify the whole object in a single column
            fieldnames = ["value"]
            rows = [{"value": r} for r in rows]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# -------------------------------------------------------------------
# Handler
# -------------------------------------------------------------------
class ReportCardsHandler(QueryHandler):
    """
    QueryData handler for report_cards.

    Exposes:
      - mode: 'report_cards'
      - data keys: 'rows', 'report_cards'
    """

    mode = "report_cards"
    keywords = [
        "report_cards",
        "report cards",
        "show report cards",
        "list report cards",
        "student report cards",
        "grade report cards",
        "dcg report cards",
        "osss report cards",
    ]
    source_label = "your DCG OSSS data service (report_cards)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_report_cards(skip=skip, limit=limit)
        # Only report_cards data; no students/persons join here.
        return {"rows": rows, "report_cards": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_report_cards_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_report_cards_csv(rows)


# register on import
register_handler(ReportCardsHandler())