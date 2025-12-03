from __future__ import annotations

from typing import Any, Dict, List, Sequence
import csv
import httpx
import io
import logging
import os

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    FetchResult,
    QueryHandler,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.incidents")

API_BASE = os.getenv(
    "OSSS_INCIDENTS_API_BASE",
    "http://host.containers.internal:8081",
)
INCIDENTS_ENDPOINT = "/api/incidents"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_incidents(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}{INCIDENTS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching incidents from %s with params skip=%s, limit=%s",
        url,
        skip,
        limit,
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            verify=False,
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode incidents API JSON")
                raise QueryDataError(
                    f"Error decoding incidents API JSON: {json_err}",
                    incidents_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling incidents API")
        raise QueryDataError(
            f"Network error querying incidents API: {e}",
            incidents_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("incidents API returned HTTP %s", status)
        raise QueryDataError(
            f"incidents API returned HTTP {status}",
            incidents_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling incidents API")
        raise QueryDataError(
            f"Unexpected error querying incidents API: {e}",
            incidents_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected incidents payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected incidents payload type: {type(data)!r}",
            incidents_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in incidents payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d incidents records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_incidents_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "incident_code",
        "incident_type",
        "severity",
        "status",
        "student_id",
        "student_code",
        "student_name",
        "location",
        "building",
        "room",
        "date",
        "time",
        "reported_by",
        "reported_by_name",
        "description",
        "action_taken",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered = [k for k in preferred_order if k in all_keys]
    ordered.extend(x for x in all_keys if x not in ordered)
    return ordered


def _build_incidents_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No incidents records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_incidents_fields(display)
    if not fieldnames:
        return "No incidents records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"

    lines: List[str] = []
    for idx, r in enumerate(display, start=1):
        cells = [_escape_md(idx)] + [
            _escape_md(r.get(f, "")) for f in fieldnames
        ]
        lines.append(f"| {' | '.join(cells)} |")

    table = header + separator + "\n".join(lines)
    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} incident records. "
            "You can request CSV to see the full dataset._"
        )
    return table


def _build_incidents_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_incidents_fields(display)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=fieldnames, extrasaction="ignore"
    )
    writer.writeheader()
    writer.writerows(display)

    csv_text = output.getvalue()
    if total > MAX_CSV_ROWS:
        csv_text += (
            f"# Truncated to first {MAX_CSV_ROWS} of {total} incident rows\n"
        )
    return csv_text


class IncidentsHandler(QueryHandler):
    mode = "incidents"
    keywords = [
        "incidents",
        "discipline incidents",
        "behavior incidents",
        "student incidents",
        "incident log",
    ]
    source_label = "your DCG OSSS data service (incidents)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "IncidentsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )
        rows = await _fetch_incidents(skip=skip, limit=limit)
        return {
            "rows": rows,
            "incidents": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_incidents_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_incidents_csv(rows)


register_handler(IncidentsHandler())
