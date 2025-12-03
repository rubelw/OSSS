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

logger = logging.getLogger("OSSS.ai.agents.query_data.gpa_calculations")

API_BASE = os.getenv(
    "OSSS_GPA_CALCULATIONS_API_BASE",
    "http://host.containers.internal:8081",
)
GPA_CALCULATIONS_ENDPOINT = "/api/gpa_calculations"

# Output safety limits
MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_gpa_calculations(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch gpa_calculations rows from the OSSS data API with robust error handling.
    """
    url = f"{API_BASE}{GPA_CALCULATIONS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching gpa_calculations from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode gpa_calculations API JSON")
                raise QueryDataError(
                    f"Error decoding gpa_calculations API JSON: {json_err}",
                    gpa_calculations_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling gpa_calculations API")
        raise QueryDataError(
            f"Network error querying gpa_calculations API: {e}",
            gpa_calculations_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("gpa_calculations API returned HTTP %s", status)
        raise QueryDataError(
            f"gpa_calculations API returned HTTP {status}",
            gpa_calculations_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling gpa_calculations API")
        raise QueryDataError(
            f"Unexpected error querying gpa_calculations API: {e}",
            gpa_calculations_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected gpa_calculations payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected gpa_calculations payload type: {type(data)!r}",
            gpa_calculations_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in gpa_calculations payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d gpa_calculations records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    """Escape markdown-sensitive characters."""
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_gpa_calculations_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    """
    Choose a stable, user-friendly column ordering.
    Automatically include any extra keys returned by the API.
    """
    if not rows:
        return []

    # Update as needed to match your real schema
    preferred_order = [
        "id",
        "student_id",
        "student_number",
        "student_name",
        "school_year",
        "term",
        "gpa_type",            # weighted, unweighted, cumulative, etc.
        "grade_points",
        "credits_attempted",
        "credits_earned",
        "calculated_gpa",
        "gpa_scale_id",
        "gpa_scale_name",
        "is_cumulative",
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


def _build_gpa_calculations_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    """Render rows as markdown with truncation."""
    if not rows:
        return "No gpa_calculations records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_gpa_calculations_fields(display)
    if not fieldnames:
        return "No gpa_calculations records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"

    lines = []
    for idx, r in enumerate(display, start=1):
        row_cells = [_escape_md(idx)] + [_escape_md(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {' | '.join(row_cells)} |")

    table = header + separator + "\n".join(lines)

    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} "
            "GPA calculation records. Request CSV for full dataset._"
        )

    return table


def _build_gpa_calculations_csv(
    rows: List[Dict[str, Any]],
) -> str:
    """Render rows as CSV with truncation notice."""
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_gpa_calculations_fields(display)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(display)

    csv_text = output.getvalue()

    if total > MAX_CSV_ROWS:
        csv_text += (
            f"# Truncated to first {MAX_CSV_ROWS} of {total} gpa_calculation rows\n"
        )

    return csv_text


class GpaCalculationsHandler(QueryHandler):
    mode = "gpa_calculations"
    keywords = [
        "gpa calculations",
        "gpa_calculations",
        "calculate gpa",
        "student gpa",
        "weighted gpa",
        "unweighted gpa",
        "cumulative gpa",
        "term gpa",
        "gpa result",
    ]
    source_label = "your DCG OSSS data service (gpa_calculations)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "GpaCalculationsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_gpa_calculations(skip=skip, limit=limit)

        return {
            "rows": rows,
            "gpa_calculations": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_gpa_calculations_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_gpa_calculations_csv(rows)


# Register on import
register_handler(GpaCalculationsHandler())
