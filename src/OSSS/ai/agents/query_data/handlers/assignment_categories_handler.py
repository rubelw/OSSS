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

logger = logging.getLogger(
    "OSSS.ai.agents.query_data.assignment_categories"
)

API_BASE = os.getenv(
    "OSSS_ASSIGNMENT_CATEGORIES_API_BASE",
    "http://host.containers.internal:8081",
)
ASSIGNMENT_CATEGORIES_ENDPOINT = "/api/assignment_categorys"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_assignment_categories(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch assignment_categories rows from the OSSS data API.
    """
    url = f"{API_BASE}{ASSIGNMENT_CATEGORIES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching assignment_categories from %s with params skip=%s, limit=%s",
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
                    "Failed to decode assignment_categories API JSON"
                )
                raise QueryDataError(
                    "Error decoding assignment_categories API JSON: "
                    f"{json_err}",
                    assignment_categories_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception(
            "Network error calling assignment_categories API"
        )
        raise QueryDataError(
            "Network error querying assignment_categories API: "
            f"{e}",
            assignment_categories_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception(
            "assignment_categories API returned HTTP %s",
            status,
        )
        raise QueryDataError(
            "assignment_categories API returned HTTP "
            f"{status}",
            assignment_categories_url=url,
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error calling assignment_categories API"
        )
        raise QueryDataError(
            "Unexpected error querying assignment_categories API: "
            f"{e}",
            assignment_categories_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error(
            "Unexpected assignment_categories payload type: %r",
            type(data),
        )
        raise QueryDataError(
            "Unexpected assignment_categories payload type: "
            f"{type(data)!r}",
            assignment_categories_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in "
                "assignment_categories payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d assignment_categories records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_assignment_categories_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "category_code",
        "name",
        "short_name",
        "description",
        "grading_scale_id",
        "grading_scale_name",
        "weight",
        "drop_lowest_count",
        "is_default",
        "is_active",
        "school_id",
        "school_name",
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


def _build_assignment_categories_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return (
            "No assignment_categories records were found in the system."
        )

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_assignment_categories_fields(display)
    if not fieldnames:
        return (
            "No assignment_categories records were found in the system."
        )

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = (
        f"| {' | '.join(['---'] * len(header_cells))} |\n"
    )

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
            f"{MAX_MARKDOWN_ROWS} of {total} assignment category records. "
            "You can request CSV to see the full dataset._"
        )
    return table


def _build_assignment_categories_csv(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_assignment_categories_fields(display)
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
            f"{MAX_CSV_ROWS} of {total} assignment_categories rows\n"
        )
    return csv_text


class AssignmentCategoriesHandler(QueryHandler):
    mode = "assignment_categories"
    keywords = [
        "assignment categories",
        "assignment_categories",
        "gradebook categories",
        "grading categories",
    ]
    source_label = (
        "your DCG OSSS data service (assignment_categories)"
    )

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "AssignmentCategoriesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_assignment_categories(skip=skip, limit=limit)

        return {
            "rows": rows,
            "assignment_categories": rows,
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
        return _build_assignment_categories_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_assignment_categories_csv(rows)


# register on import
register_handler(AssignmentCategoriesHandler())
