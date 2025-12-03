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

logger = logging.getLogger("OSSS.ai.agents.query_data.course_sections")

API_BASE = os.getenv(
    "OSSS_COURSE_SECTIONS_API_BASE",
    "http://host.containers.internal:8081",
)
COURSE_SECTIONS_ENDPOINT = "/api/course_sections"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_course_sections(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch course_sections rows from the OSSS data API.
    """
    url = f"{API_BASE}{COURSE_SECTIONS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching course_sections from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode course_sections API JSON")
                raise QueryDataError(
                    f"Error decoding course_sections API JSON: {json_err}",
                    course_sections_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling course_sections API")
        raise QueryDataError(
            f"Network error querying course_sections API: {e}",
            course_sections_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("course_sections API returned HTTP %s", status)
        raise QueryDataError(
            f"course_sections API returned HTTP {status}",
            course_sections_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling course_sections API")
        raise QueryDataError(
            f"Unexpected error querying course_sections API: {e}",
            course_sections_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected course_sections payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected course_sections payload type: {type(data)!r}",
            course_sections_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in course_sections payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d course_sections records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_course_sections_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "course_id",
        "course_code",
        "course_name",
        "section_number",
        "term_id",
        "term_name",
        "school_year",
        "school_id",
        "school_name",
        "period",
        "meeting_days",
        "start_time",
        "end_time",
        "room_id",
        "room_name",
        "teacher_id",
        "teacher_name",
        "max_enrollment",
        "current_enrollment",
        "is_active",
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


def _build_course_sections_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No course_sections records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_course_sections_fields(display)
    if not fieldnames:
        return "No course_sections records were found in the system."

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
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} course section "
            "records. You can request CSV to see the full dataset._"
        )

    return table


def _build_course_sections_csv(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_course_sections_fields(display)
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
            f"{MAX_CSV_ROWS} of {total} course_sections rows\n"
        )

    return csv_text


class CourseSectionsHandler(QueryHandler):
    mode = "course_sections"
    keywords = [
        "course sections",
        "course_sections",
        "class sections",
        "sections for a course",
    ]
    source_label = "your DCG OSSS data service (course_sections)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "CourseSectionsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_course_sections(skip=skip, limit=limit)

        return {
            "rows": rows,
            "course_sections": rows,
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
        return _build_course_sections_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_course_sections_csv(rows)


# register on import
register_handler(CourseSectionsHandler())
