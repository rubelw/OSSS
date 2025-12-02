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

logger = logging.getLogger("OSSS.ai.agents.query_data.section_meetings")

API_BASE = "http://host.containers.internal:8081"
SAFE_MAX_ROWS = 200


# -------------------------------------------------------------------
# Fetch
# -------------------------------------------------------------------
async def _fetch_section_meetings(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/section_meetings"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except httpx.HTTPStatusError as e:
        code = e.response.status_code if getattr(e, "response", None) else "unknown"
        logger.exception("HTTP error calling section_meetings API")
        raise QueryDataError(
            f"HTTP {code} error querying section_meetings API: {str(e)}"
        ) from e

    except Exception as e:
        logger.exception("Error calling section_meetings API")
        raise QueryDataError(
            f"Error querying section_meetings API: {str(e)}"
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected section_meetings payload type: {type(data)!r}"
        )
    return data


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _stringify(value: Any, max_len: int = 120) -> str:
    if value is None:
        return ""
    s = str(value)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


# -------------------------------------------------------------------
# Markdown
# -------------------------------------------------------------------
def _build_section_meetings_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No section_meetings records were found in the system."

    rows = rows[:SAFE_MAX_ROWS]

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No section_meetings records were found in the system."

    # Pretty: move id to last if it exists
    if "id" in fieldnames:
        fieldnames = [f for f in fieldnames if f != "id"] + ["id"]

    header = "| # | " + " | ".join(fieldnames) + " |\n"
    separator = "|" + " --- |" * (len(fieldnames) + 1) + "\n"

    lines = []
    for idx, rec in enumerate(rows, start=1):
        row = [str(idx)] + [_stringify(rec.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(row) + " |")

    return header + separator + "\n".join(lines)


# -------------------------------------------------------------------
# CSV
# -------------------------------------------------------------------
def _build_section_meetings_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    fieldnames = list(rows[0].keys())

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


# -------------------------------------------------------------------
# Handler
# -------------------------------------------------------------------
class SectionMeetingsHandler(QueryHandler):
    mode = "section_meetings"
    keywords = [
        "section meetings",
        "section_meetings",
        "class meeting times",
        "when does this section meet",
    ]
    source_label = "your DCG OSSS data service (section_meetings)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_section_meetings(skip=skip, limit=limit)
        return {"rows": rows, "section_meetings": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_section_meetings_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_section_meetings_csv(rows)


register_handler(SectionMeetingsHandler())
