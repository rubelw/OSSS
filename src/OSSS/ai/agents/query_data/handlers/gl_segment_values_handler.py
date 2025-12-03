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

logger = logging.getLogger("OSSS.ai.agents.query_data.gl_segment_values")

API_BASE = os.getenv(
    "OSSS_GL_SEGMENT_VALUES_API_BASE",
    "http://host.containers.internal:8081",
)
GL_SEGMENT_VALUES_ENDPOINT = "/api/gl_segment_values"

# Output safety limits
MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_gl_segment_values(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch gl_segment_values rows from the OSSS data API with robust error handling.
    """
    url = f"{API_BASE}{GL_SEGMENT_VALUES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching gl_segment_values from %s with params skip=%s, limit=%s",
        url, skip, limit,
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
                logger.exception("Failed to decode gl_segment_values API JSON")
                raise QueryDataError(
                    f"Error decoding gl_segment_values API JSON: {json_err}",
                    gl_segment_values_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling gl_segment_values API")
        raise QueryDataError(
            f"Network error querying gl_segment_values API: {e}",
            gl_segment_values_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("gl_segment_values API returned HTTP %s", status)
        raise QueryDataError(
            f"gl_segment_values API returned HTTP {status}",
            gl_segment_values_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling gl_segment_values API")
        raise QueryDataError(
            f"Unexpected error querying gl_segment_values API: {e}",
            gl_segment_values_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected gl_segment_values payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected gl_segment_values payload type: {type(data)!r}",
            gl_segment_values_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in gl_segment_values payload: %r",
                i, type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d gl_segment_values records (skip=%s, limit=%s)",
        len(cleaned), skip, limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    """Escape markdown-sensitive characters."""
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_gl_segment_values_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    """
    Select stable, user-friendly column ordering while including all API fields.
    """
    if not rows:
        return []

    # Adjust this based on your actual data schema
    preferred_order = [
        "id",
        "gl_segment_id",
        "segment_code",
        "segment_name",
        "value_code",
        "value_name",
        "description",
        "is_default",
        "is_active",
        "sort_order",
        "start_date",
        "end_date",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in all_keys:
                all_keys.append(key)

    ordered = [k for k in preferred_order if k in all_keys]
    ordered.extend(k for k in all_keys if k not in ordered)
    return ordered


def _build_gl_segment_values_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No gl_segment_values records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_gl_segment_values_fields(display)
    if not fieldnames:
        return "No gl_segment_values records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"

    lines = []
    for idx, row in enumerate(display, start=1):
        row_cells = [_escape_md(idx)] + [_escape_md(row.get(f, "")) for f in fieldnames]
        lines.append(f"| {' | '.join(row_cells)} |")

    table = header + separator + "\n".join(lines)

    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} GL segment value records. "
            "Request CSV to see the full dataset._"
        )

    return table


def _build_gl_segment_values_csv(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_gl_segment_values_fields(display)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(display)

    csv_text = output.getvalue()

    if total > MAX_CSV_ROWS:
        csv_text += (
            f"# Truncated to first {MAX_CSV_ROWS} of {total} gl_segment_values rows\n"
        )

    return csv_text


class GlSegmentValuesHandler(QueryHandler):
    mode = "gl_segment_values"
    keywords = [
        "gl segment values",
        "gl_segment_values",
        "general ledger segment values",
        "accounting segment values",
        "chart of accounts values",
        "segment value list",
        "coas segment values",
    ]
    source_label = "your DCG OSSS data service (gl_segment_values)"

    async def fetch(self, ctx: AgentContext, skip: int, limit: int) -> FetchResult:
        logger.debug(
            "GlSegmentValuesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip, limit, getattr(ctx, "user_id", None),
        )

        rows = await _fetch_gl_segment_values(skip=skip, limit=limit)

        return {
            "rows": rows,
            "gl_segment_values": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_gl_segment_values_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_gl_segment_values_csv(rows)


# register on import
register_handler(GlSegmentValuesHandler())
