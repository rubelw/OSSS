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

logger = logging.getLogger("OSSS.ai.agents.query_data.report_cards")

API_BASE = "http://host.containers.internal:8081"

SAFE_MAX_ROWS = 200


# ----------------------------------------------------------------------
# Fetcher
# ----------------------------------------------------------------------
async def _fetch_report_cards(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
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
            f"HTTP {status} error querying report_cards API: {e}"
        ) from e

    except Exception as e:
        logger.exception("Error calling report_cards API")
        raise QueryDataError(
            f"Error querying report_cards API: {e}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected report_cards payload type: {type(data)!r}",
            report_cards_url=url,
        )

    return data


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _stringify_cell(value: Any, max_len: int = 140) -> str:
    """Safe trimming of long table cell values."""
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else (s[: max_len - 3] + "...")


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------
def _build_report_cards_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No report_cards records were found in the system."

    # Cap output to protect the UI
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No report_cards records were found in the system."

    # Move id to the end
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        rowvals = [_stringify_cell(idx)]
        rowvals.extend(_stringify_cell(rec.get(f, "")) for f in fieldnames)
        body.append("| " + " | ".join(rowvals) + " |")

    return header + separator + "\n".join(body)


# ----------------------------------------------------------------------
# CSV
# ----------------------------------------------------------------------
def _build_report_cards_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    first = rows[0]

    if isinstance(first, dict):
        fieldnames = list(first.keys())
    else:
        try:
            fieldnames = list(first.__dict__.keys())
            rows = [getattr(r, "__dict__", {"value": r}) for r in rows]
        except Exception:
            fieldnames = ["value"]
            rows = [{"value": r} for r in rows]

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    return output.getvalue()


# ----------------------------------------------------------------------
# Handler
# ----------------------------------------------------------------------
class ReportCardsHandler(QueryHandler):
    mode = "report_cards"

    keywords = [
        "report_cards",
        "report cards",
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
        return {"rows": rows, "report_cards": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_report_cards_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_report_cards_csv(rows)


# Register handler
register_handler(ReportCardsHandler())