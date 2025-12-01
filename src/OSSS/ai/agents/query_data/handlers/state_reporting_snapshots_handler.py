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
MAX_MARKDOWN_ROWS = 50  # avoid massive tables in chat


async def _fetch_state_reporting_snapshots(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Call the OSSS /api/state_reporting_snapshots endpoint and return a list of rows.

    Raises QueryDataError with helpful context if anything goes wrong.
    """
    if skip < 0:
        logger.warning(
            "Negative skip passed to _fetch_state_reporting_snapshots, normalizing to 0",
            extra={"skip": skip},
        )
        skip = 0

    # Put a sane upper bound on limit so we don't flood the agent output.
    if limit <= 0:
        limit = 100
    limit = min(limit, 500)

    url = f"{API_BASE}/api/state_reporting_snapshots"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.exception(
            "HTTP error calling state_reporting_snapshots API",
            extra={"url": url, "params": params},
        )
        raise QueryDataError(
            f"HTTP error querying state_reporting_snapshots API: {e}",
            state_reporting_snapshots_url=url,
            state_reporting_snapshots_params=params,
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error calling state_reporting_snapshots API",
            extra={"url": url, "params": params},
        )
        raise QueryDataError(
            f"Unexpected error querying state_reporting_snapshots API: {e}",
            state_reporting_snapshots_url=url,
            state_reporting_snapshots_params=params,
        ) from e

    if not isinstance(data, list):
        logger.error(
            "Unexpected payload type from state_reporting_snapshots API",
            extra={
                "url": url,
                "params": params,
                "payload_type": type(data).__name__,
            },
        )
        raise QueryDataError(
            f"Unexpected state_reporting_snapshots payload type: {type(data)!r}",
            state_reporting_snapshots_url=url,
            state_reporting_snapshots_params=params,
        )

    return data


def _build_state_reporting_snapshots_markdown_table(
    rows: List[Dict[str, Any]],
    max_rows: int = MAX_MARKDOWN_ROWS,
) -> str:
    """
    Render state_reporting_snapshots rows as a markdown table.

    We cap the rendered rows for readability and add a note when truncation occurs.
    """
    if not rows:
        return "No state_reporting_snapshots records were found in the system."

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No state_reporting_snapshots records were found in the system."

    display_rows = rows[:max_rows]
    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(display_rows, start=1):
        row_cells = [str(idx)] + [str(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(row_cells) + " |")

    body = header + separator + "\n".join(lines)

    # Append truncation + provenance info
    notes: List[str] = []

    if len(rows) > max_rows:
        notes.append(
            f"_Showing the first {max_rows} of {len(rows)} "
            "state_reporting_snapshots records returned by the service._"
        )

    notes.append(
        "This data is coming from your DCG OSSS data service (state_reporting_snapshots)."
    )

    return body + "\n\n" + "\n".join(notes)


def _build_state_reporting_snapshots_csv(rows: List[Dict[str, Any]]) -> str:
    """
    Render state_reporting_snapshots rows as CSV for download / export.
    """
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


class StateReportingSnapshotsHandler(QueryHandler):
    """
    QueryData handler that fetches state_reporting_snapshots from the OSSS API
    and renders them in markdown / CSV form for the OSSS agents.
    """

    mode = "state_reporting_snapshots"
    keywords = [
        "state_reporting_snapshots",
        "state reporting snapshots",
        "state reporting snapshot",
        "state reporting export",
        "state reporting submission",
    ]
    source_label = "your DCG OSSS data service (state_reporting_snapshots)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        """
        Fetch rows for this query mode.

        Returns a FetchResult that includes both a generic 'rows' key and a
        domain-specific key so other agents can access it explicitly.
        """
        rows = await _fetch_state_reporting_snapshots(skip=skip, limit=limit)
        return {
            "rows": rows,
            "state_reporting_snapshots": rows,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_state_reporting_snapshots_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_state_reporting_snapshots_csv(rows)


# register on import
register_handler(StateReportingSnapshotsHandler())
