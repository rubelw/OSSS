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

logger = logging.getLogger("OSSS.ai.agents.query_data.scorecard_kpis")

API_BASE = "http://host.containers.internal:8081"

# Safety cap for markdown output
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# Low-level fetch
# -------------------------------------------------------------------
async def _fetch_scorecard_kpis(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/scorecard_kpis"
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
        logger.exception("HTTP error calling scorecard_kpis API")
        raise QueryDataError(
            f"HTTP {status} error querying scorecard_kpis API: {str(e)}",
            {"scorecard_kpis_url": url, "status": status},
        ) from e

    except Exception as e:
        logger.exception("Error calling scorecard_kpis API")
        raise QueryDataError(
            f"Error querying scorecard_kpis API: {str(e)}",
            {"scorecard_kpis_url": url},
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected scorecard_kpis payload type: {type(data)!r}",
            {"scorecard_kpis_url": url},
        )

    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify_cell(value: Any, max_len: int = 120) -> str:
    """Convert a value to a trimmed, safe string for markdown tables."""
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def _order_scorecard_kpi_fields(fieldnames: List[str]) -> List[str]:
    """
    Put the most useful scorecard_kpis fields first, and move 'id' to the end
    if present, while preserving any other fields.
    """
    if not fieldnames:
        return fieldnames

    preferred_first = [
        "scorecard_id",
        "kpi_id",
        "name",
        "target_value",
        "current_value",
        "status",
        "created_at",
        "updated_at",
    ]

    ordered: List[str] = []
    for f in preferred_first:
        if f in fieldnames:
            ordered.append(f)

    # Any remaining non-id fields
    for f in fieldnames:
        if f not in ordered and f != "id":
            ordered.append(f)

    # Put id last if present
    if "id" in fieldnames:
        ordered.append("id")

    return ordered


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_scorecard_kpis_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No scorecard_kpis records were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    raw_fieldnames = list(rows[0].keys())
    if not raw_fieldnames:
        return "No scorecard_kpis records were found in the system."

    fieldnames = _order_scorecard_kpi_fields(raw_fieldnames)

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row_cells: List[str] = [_stringify_cell(idx)]
        row_cells.extend(_stringify_cell(rec.get(f, "")) for f in fieldnames)
        lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_scorecard_kpis_csv(rows: List[Dict[str, Any]]) -> str:
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
class ScorecardKpisHandler(QueryHandler):
    mode = "scorecard_kpis"
    keywords = [
        "scorecard_kpis",
        "scorecard kpis",
        "kpis on scorecards",
        "plan kpis",
        "performance indicators",
    ]
    source_label = "your DCG OSSS data service (scorecard_kpis)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_scorecard_kpis(skip=skip, limit=limit)
        return {"rows": rows, "scorecard_kpis": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_scorecard_kpis_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_scorecard_kpis_csv(rows)


# register on import
register_handler(ScorecardKpisHandler())
