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

logger = logging.getLogger("OSSS.ai.agents.query_data.state_reporting_snapshots")

API_BASE = "http://host.containers.internal:8081"


async def _fetch_state_reporting_snapshots(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/state_reporting_snapshots"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.exception("Error calling state_reporting_snapshots API")
        raise QueryDataError(
            f"Error querying state_reporting_snapshots API: {e}",
            state_reporting_snapshots_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected state_reporting_snapshots payload type: {type(data)!r}",
            state_reporting_snapshots_url=url,
        )
    return data


def _build_state_reporting_snapshots_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No state_reporting_snapshots records were found in the system."

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No state_reporting_snapshots records were found in the system."

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_cells = [str(idx)] + [str(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


def _build_state_reporting_snapshots_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class StateReportingSnapshotsHandler(QueryHandler):
    mode = "state_reporting_snapshots"
    keywords = [
        "state_reporting_snapshots",
        "state reporting snapshots",
    ]
    source_label = "your DCG OSSS data service (state_reporting_snapshots)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_state_reporting_snapshots(skip=skip, limit=limit)
        return {"rows": rows, "state_reporting_snapshots": rows}

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_state_reporting_snapshots_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_state_reporting_snapshots_csv(rows)


# register on import
register_handler(StateReportingSnapshotsHandler())
