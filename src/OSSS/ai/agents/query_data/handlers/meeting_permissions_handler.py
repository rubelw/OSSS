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

logger = logging.getLogger("OSSS.ai.agents.query_data.meeting_permissions")

API_BASE = "http://host.containers.internal:8081"


async def _fetch_meeting_permissions(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/meeting_permissions"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.exception("Error calling meeting_permissions API")
        raise QueryDataError(
            f"Error querying meeting_permissions API: {e}",
            meeting_permissions_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected meeting_permissions payload type: {type(data)!r}",
            meeting_permissions_url=url,
        )
    return data


def _build_meeting_permissions_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No meeting_permissions records were found in the system."

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No meeting_permissions records were found in the system."

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_cells = [str(idx)] + [str(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


def _build_meeting_permissions_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class MeetingPermissionsHandler(QueryHandler):
    mode = "meeting_permissions"
    keywords = [
        "meeting_permissions",
        "meeting permissions",
    ]
    source_label = "your DCG OSSS data service (meeting_permissions)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_meeting_permissions(skip=skip, limit=limit)
        return {"rows": rows, "meeting_permissions": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_meeting_permissions_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_meeting_permissions_csv(rows)


# register on import
register_handler(MeetingPermissionsHandler())
