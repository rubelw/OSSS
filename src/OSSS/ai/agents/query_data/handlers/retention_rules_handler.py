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

logger = logging.getLogger("OSSS.ai.agents.query_data.retention_rules")

API_BASE = "http://host.containers.internal:8081"

# Safety limit for Markdown table rows
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# API Fetch
# -------------------------------------------------------------------
async def _fetch_retention_rules(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/retention_rules"
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
        logger.exception("HTTP error calling retention_rules API")
        raise QueryDataError(
            f"HTTP {status} error querying retention_rules API: {str(e)}"
        ) from e

    except Exception as e:
        logger.exception("Error calling retention_rules API")
        raise QueryDataError(
            f"Error querying retention_rules API: {str(e)}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected retention_rules payload type: {type(data)!r}"
        )
    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify_cell(value: Any, max_len: int = 140) -> str:
    """Converts a value to a string with trimming."""
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown Builder
# -------------------------------------------------------------------
def _build_retention_rules_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No retention_rules records were found in the system."

    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    body_lines: List[str] = []
    for idx, rec in enumerate(rows, start=1):
        row = [_stringify_cell(idx)]
        row.extend(_stringify_cell(rec.get(f, "")) for f in fieldnames)
        body_lines.append("| " + " | ".join(row) + " |")

    return header + separator + "\n".join(body_lines)


# -------------------------------------------------------------------
# CSV Builder
# -------------------------------------------------------------------
def _build_retention_rules_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    first = rows[0]

    # Normal FastAPI list-of-dicts response
    if isinstance(first, dict):
        fieldnames = list(first.keys())
    else:
        # handle object / weird payload
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


# -------------------------------------------------------------------
# Handler
# -------------------------------------------------------------------
class RetentionRulesHandler(QueryHandler):
    mode = "retention_rules"

    keywords = [
        "retention rules",
        "retention_rules",
        "data retention rules",
        "record retention",
        "policy retention rules",
        "how long do we retain",
        "retention schedule",
        "retention policy",
    ]

    source_label = "your DCG OSSS data service (retention_rules)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_retention_rules(skip=skip, limit=limit)
        return {"rows": rows, "retention_rules": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_retention_rules_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_retention_rules_csv(rows)


# Register
register_handler(RetentionRulesHandler())
