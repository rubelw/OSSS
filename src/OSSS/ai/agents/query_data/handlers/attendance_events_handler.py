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

logger = logging.getLogger("OSSS.ai.agents.query_data.attendances")

API_BASE = os.getenv(
    "OSSS_ATTENDANCE_EVENTS_API_BASE",
    "http://host.containers.internal:8081",
)
ATTENDANCE_EVENTS_ENDPOINT = "/api/attendance_events"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_attendance_events(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch attendance_events rows from the OSSS data API.
    """
    url = f"{API_BASE}{ATTENDANCE_EVENTS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching attendance_events from %s with params skip=%s, limit=%s",
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
                    "Failed to decode attendance_events API JSON"
                )
                raise QueryDataError(
                    "Error decoding attendance_events API JSON: "
                    f"{json_err}",
                    attendance_events_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling attendance_events API")
        raise QueryDataError(
            f"Network error querying attendance_events API: {e}",
            attendance_events_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("attendance_events API returned HTTP %s", status)
        raise QueryDataError(
            f"attendance_events API returned HTTP {status}",
            attendance_events_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling attendance_events API")
        raise QueryDataError(
            "Unexpected error querying attendance_events API: "
            f"{e}",
            attendance_events_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error(
            "Unexpected attendance_events payload type: %r",
            type(data),
        )
        raise QueryDataError(
            "Unexpected attendance_events payload type: "
            f"{type(data)!r}",
            attendance_events_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in "
                "attendance_events payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d attendance_events records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_attendance_events_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "student_id",
        "student_number",
        "student_name",
        "event_timestamp",
        "event_type",          # check-in, check-out, tardy, etc.
        "source",              # kiosk, office, manual, etc.
        "school_id",
        "school_name",
        "section_id",
        "section_code",
        "notes",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r:
            if k not in all_keys:
                all_keys.append(k)

    ordered = [k for k in preferred_order if k in all_keys]
    ordered.extend(k for k in all_keys if k not in ordered)
    return ordered


def _build_attendance_events_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No attendance_events records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_attendance_events_fields(display)
    if not fieldnames:
        return "No attendance_events records were found in the system."

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
            "\n\n_Showing first "
            f"{MAX_MARKDOWN_ROWS} of {total} attendance event records. "
            "You can request CSV to see the full dataset._"
        )
    return table


def _build_attendance_events_csv(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_attendance_events_fields(display)
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
            f"{MAX_CSV_ROWS} of {total} attendance_events rows\n"
        )
    return csv_text


class AttendanceEventsHandler(QueryHandler):
    mode = "attendance_events"
    keywords = [
        "attendance events",
        "attendance_events",
        "check in",
        "check out",
    ]
    source_label = "your DCG OSSS data service (attendance_events)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "AttendanceEventsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_attendance_events(skip=skip, limit=limit)

        return {
            "rows": rows,
            "attendance_events": rows,
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
        return _build_attendance_events_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_attendance_events_csv(rows)


# register on import
register_handler(AttendanceEventsHandler())
