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

logger = logging.getLogger("OSSS.ai.agents.query_data.data_quality_issues")

API_BASE = os.getenv(
    "OSSS_DATA_QUALITY_ISSUES_API_BASE",
    "http://host.containers.internal:8081",
)
DATA_QUALITY_ISSUES_ENDPOINT = "/api/data_quality_issues"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_data_quality_issues(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch data_quality_issues rows from the OSSS data API.
    """
    url = f"{API_BASE}{DATA_QUALITY_ISSUES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching data_quality_issues from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode data_quality_issues API JSON")
                raise QueryDataError(
                    f"Error decoding data_quality_issues API JSON: {json_err}",
                    data_quality_issues_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling data_quality_issues API")
        raise QueryDataError(
            f"Network error querying data_quality_issues API: {e}",
            data_quality_issues_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("data_quality_issues API returned HTTP %s", status)
        raise QueryDataError(
            f"data_quality_issues API returned HTTP {status}",
            data_quality_issues_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling data_quality_issues API")
        raise QueryDataError(
            f"Unexpected error querying data_quality_issues API: {e}",
            data_quality_issues_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected data_quality_issues payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected data_quality_issues payload type: {type(data)!r}",
            data_quality_issues_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in data_quality_issues payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d data_quality_issues records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_data_quality_issues_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "source_system",
        "table_name",
        "record_id",
        "field_name",
        "issue_type",            # missing, invalid, duplicate, etc.
        "severity",              # low, medium, high, critical
        "category",              # enrollment, attendance, grades, etc.
        "description",
        "detected_at",
        "resolved_at",
        "resolution_status",     # open, in_progress, resolved, wont_fix
        "resolution_notes",
        "assignee_id",
        "assignee_name",
        "school_id",
        "school_name",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered = [k for k in preferred_order if k in all_keys]
    ordered.extend([k for k in all_keys if k not in ordered])
    return ordered


def _build_data_quality_issues_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No data_quality_issues records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_data_quality_issues_fields(display)
    if not fieldnames:
        return "No data_quality_issues records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"
    lines: List[str] = []

    for idx, r in enumerate(display, start=1):
        row_cells = [_escape_md(idx)] + [_escape_md(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {' | '.join(row_cells)} |")

    table = header + separator + "\n".join(lines)
    if total > MAX_MARKDOWN_ROWS:
        table += (
            "\n\n_Showing first "
            f"{MAX_MARKDOWN_ROWS} of {total} data quality issue records. "
            "You can request CSV to see the full dataset._"
        )

    return table


def _build_data_quality_issues_csv(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_data_quality_issues_fields(display)
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
            f"{MAX_CSV_ROWS} of {total} data_quality_issue rows\n"
        )

    return csv_text


class DataQualityIssuesHandler(QueryHandler):
    mode = "data_quality_issues"
    keywords = [
        "data quality issues",
        "data_quality_issues",
        "dq issues",
        "data validation issues",
        "data quality problems",
    ]
    source_label = "your DCG OSSS data service (data_quality_issues)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "DataQualityIssuesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )
        rows = await _fetch_data_quality_issues(skip=skip, limit=limit)
        return {
            "rows": rows,
            "data_quality_issues": rows,
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
        return _build_data_quality_issues_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_data_quality_issues_csv(rows)


# register on import
register_handler(DataQualityIssuesHandler())
