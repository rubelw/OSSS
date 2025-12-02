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

logger = logging.getLogger("OSSS.ai.agents.query_data.publications")

API_BASE = "http://host.containers.internal:8081"

# Safety cap for markdown output
SAFE_MAX_ROWS = 200


# ----------------------------------------------------------------------
# Low-level fetch
# ----------------------------------------------------------------------
async def _fetch_publications(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/publications"
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
        logger.exception("HTTP error calling publications API")
        raise QueryDataError(
            f"HTTP {status} error querying publications API: {e}"
        ) from e

    except Exception as e:
        logger.exception("Error calling publications API")
        raise QueryDataError(
            f"Error querying publications API: {e}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected publications payload type: {type(data)!r}",
            publications_url=url,
        )

    return data


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _stringify_cell(value: Any, max_len: int = 140) -> str:
    """Convert a value to a trimmed, safe string for markdown tables."""
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# ----------------------------------------------------------------------
# Markdown builder
# ----------------------------------------------------------------------
def _build_publications_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No publications records were found in the system."

    # Enforce safety limit
    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No publications records were found in the system."

    # Put id last if present
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


# ----------------------------------------------------------------------
# CSV builder
# ----------------------------------------------------------------------
def _build_publications_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    first = rows[0]

    if isinstance(first, dict):
        fieldnames = list(first.keys())
    else:
        # Fallbacks if we ever get non-dict row objects
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
class PublicationsHandler(QueryHandler):
    mode = "publications"

    keywords = [
        "publications",
        "board publications",
        "district publications",
        "policy publications",
        "meeting publications",
        "dcg publications",
        "osss publications",
    ]

    source_label = "your DCG OSSS data service (publications)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_publications(skip=skip, limit=limit)
        return {"rows": rows, "publications": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_publications_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_publications_csv(rows)


# register on import
register_handler(PublicationsHandler())