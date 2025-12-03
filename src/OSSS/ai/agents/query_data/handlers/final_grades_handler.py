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

logger = logging.getLogger("OSSS.ai.agents.query_data.final_grades")

API_BASE = os.getenv(
    "OSSS_FINAL_GRADES_API_BASE",
    "http://host.containers.internal:8081",
)
FINAL_GRADES_ENDPOINT = "/api/final_grades"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_final_grades(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch final_grades rows from the OSSS data API with robust error handling.
    """
    url = f"{API_BASE}{FINAL_GRADES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching final_grades from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode final_grades API JSON")
                raise QueryDataError(
                    f"Error decoding final_grades API JSON: {json_err}",
                    final_grades_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling final_grades API")
        raise QueryDataError(
            f"Network error querying final_grades API: {e}",
            final_grades_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("final_grades API returned HTTP %s", status)
        raise QueryDataError(
            f"final_grades API returned HTTP {status}",
            final_grades_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling final_grades API")
        raise QueryDataError(
            f"Unexpected error querying final_grades API: {e}",
            final_grades_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected final_grades payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected final_grades payload type: {type(data)!r}",
            final_grades_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in final_grades payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d final_grades records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_final_grades_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "student_id",
        "student_number",
        "student_name",
        "course_id",
        "course_code",
        "course_name",
        "section_id",
        "section_code",
        "school_year",
        "term",
        "grading_period_id",
        "grading_period_code",
        "final_mark",
        "final_score",
        "final_percentage",
        "grade_scale_id",
        "grade_scale_name",
        "credits_attempted",
        "credits_earned",
        "is_final",
        "is_posted",
        "posted_at",
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


def _build_final_grades_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No final_grades records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_final_grades_fields(display)
    if not fieldnames:
        return "No final_grades records were found in the system."

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
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} final grade records. "
            "You can request CSV to see the full dataset._"
        )
    return table


def _build_final_grades_csv(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_final_grades_fields(display)
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
            f"# Truncated to first {MAX_CSV_ROWS} of {total} final_grade rows\n"
        )
    return csv_text


class FinalGradesHandler(QueryHandler):
    mode = "final_grades"
    keywords = [
        "final grades",
        "final_grades",
        "final marks",
        "report card grades",
        "end of term grades",
        "posted grades",
    ]
    source_label = "your DCG OSSS data service (final_grades)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "FinalGradesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )
        rows = await _fetch_final_grades(skip=skip, limit=limit)
        return {
            "rows": rows,
            "final_grades": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_final_grades_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_final_grades_csv(rows)


register_handler(FinalGradesHandler())
