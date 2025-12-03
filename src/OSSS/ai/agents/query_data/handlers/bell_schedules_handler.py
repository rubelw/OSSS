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

logger = logging.getLogger("OSSS.ai.agents.query_data.bell_schedules")

API_BASE = os.getenv(
    "OSSS_BELL_SCHEDULES_API_BASE",
    "http://host.containers.internal:8081",
)
BELL_SCHEDULES_ENDPOINT = "/api/bell_schedules"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_bell_schedules(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch bell_schedules rows from the OSSS data API.
    """
    url = f"{API_BASE}{BELL_SCHEDULES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching bell_schedules from %s with params skip=%s, limit=%s",
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
                logger.exception(
                    "Failed to decode bell_schedules API JSON"
                )
                raise QueryDataError(
                    f"Error decoding bell_schedules API JSON: {json_err}",
                    bell_schedules_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling bell_schedules API")
        raise QueryDataError(
            f"Network error querying bell_schedules API: {e}",
            bell_schedules_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("bell_schedules API returned HTTP %s", status)
        raise QueryDataError(
            f"bell_schedules API returned HTTP {status}",
            bell_schedules_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling bell_schedules API")
        raise QueryDataError(
            f"Unexpected error querying bell_schedules API: {e}",
            bell_schedules_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected bell_schedules payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected bell_schedules payload type: {type(data)!r}",
            bell_schedules_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in bell_schedules payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d bell_schedules records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_bell_schedules_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "schedule_code",
        "name",
        "short_name",
        "description",
        "school_id",
        "school_name",
        "calendar_id",
        "calendar_code",
        "schedule_type",       # regular, late start, early release, etc.
        "period_count",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered = [k for k in preferred_order if k in all_keys]
    ordered.extend(k for k in all_keys if k not in ordered)
    return ordered


def _build_bell_schedules_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No bell_schedules records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_bell_schedules_fields(display)
    if not fieldnames:
        return "No bell_schedules records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"

    lines: List[str] = []
    for idx, r in enumerate(display, start=1):
        row_cells = [_escape_md(idx)] + [
            _escape_md(r.get(f, "")) for f in fieldnames
        ]
        lines.append(f"| {' | '.join(row_cells)} |")

    table = header + separator + "\n".join(lines)
    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} bell schedule "
            "records. You can request CSV to see the full dataset._"
        )
    return table


def _build_bell_schedules_csv(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_bell_schedules_fields(display)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(display)
    csv_text = output.getvalue()

    if total > MAX_CSV_ROWS:
        csv_text += (
            "# Truncated to first "
            f"{MAX_CSV_ROWS} of {total} bell_schedules rows\n"
        )
    return csv_text


class BellSchedulesHandler(QueryHandler):
    mode = "bell_schedules"
    keywords = [
        "bell schedules",
        "bell_schedules",
        "daily schedule",
        "period schedule",
    ]
    source_label = "your DCG OSSS data service (bell_schedules)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "BellSchedulesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )
        rows = await _fetch_bell_schedules(skip=skip, limit=limit)
        return {
            "rows": rows,
            "bell_schedules": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_bell_schedules_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_bell_schedules_csv(rows)


# register on import
register_handler(BellSchedulesHandler())
