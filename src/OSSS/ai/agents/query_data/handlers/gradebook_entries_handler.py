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

logger = logging.getLogger("OSSS.ai.agents.query_data.gradebook_entries")

API_BASE = os.getenv(
    "OSSS_GRADEBOOK_ENTRIES_API_BASE",
    "http://host.containers.internal:8081",
)
GRADEBOOK_ENTRIES_ENDPOINT = "/api/gradebook_entrys"

# Safety limits so we don't blow up markdown or CSV exports.
MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_gradebook_entries(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch gradebook_entries rows from the OSSS data API with robust error handling.
    """
    url = f"{API_BASE}{GRADEBOOK_ENTRIES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching gradebook_entries from %s with params skip=%s, limit=%s",
        url,
        skip,
        limit,
    )

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            verify=False,  # internal network; TLS handled elsewhere
        ) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode gradebook_entries API JSON")
                raise QueryDataError(
                    f"Error decoding gradebook_entries API JSON: {json_err}",
                    gradebook_entries_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling gradebook_entries API")
        raise QueryDataError(
            f"Network error querying gradebook_entries API: {e}",
            gradebook_entries_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("gradebook_entries API returned HTTP %s", status)
        raise QueryDataError(
            f"gradebook_entries API returned HTTP {status}",
            gradebook_entries_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling gradebook_entries API")
        raise QueryDataError(
            f"Unexpected error querying gradebook_entries API: {e}",
            gradebook_entries_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected gradebook_entries payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected gradebook_entries payload type: {type(data)!r}",
            gradebook_entries_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in gradebook_entries payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d gradebook_entries records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    """
    Escape markdown-unfriendly characters for safe table rendering.
    """
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_gradebook_entries_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    """
    Choose a stable, user-friendly column ordering, but gracefully
    include any extra keys that the API returns.
    """
    if not rows:
        return []

    # Adjust this preferred order to whatever your gradebook_entries schema actually is.
    preferred_order = [
        "id",
        "student_id",
        "student_number",
        "student_name",
        "section_id",
        "section_name",
        "course_code",
        "course_name",
        "assignment_id",
        "assignment_name",
        "category",
        "date_assigned",
        "date_due",
        "date_submitted",
        "points_earned",
        "points_possible",
        "score_pct",
        "letter_grade",
        "is_missing",
        "is_excused",
        "grading_period_id",
        "grading_period_code",
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


def _build_gradebook_entries_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    """
    Render gradebook_entries rows as a markdown table with row limits
    and a friendly truncation notice.
    """
    if not rows:
        return "No gradebook_entries records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_gradebook_entries_fields(display)
    if not fieldnames:
        return "No gradebook_entries records were found in the system."

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
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} "
            "gradebook entry records. You can request CSV to see the full dataset._"
        )

    return table


def _build_gradebook_entries_csv(
    rows: List[Dict[str, Any]],
) -> str:
    """
    Render gradebook_entries rows as CSV with a cap and comment-based truncation notice.
    """
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_gradebook_entries_fields(display)
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
            f"# Truncated to first {MAX_CSV_ROWS} of {total} gradebook entry rows\n"
        )

    return csv_text


class GradebookEntriesHandler(QueryHandler):
    mode = "gradebook_entries"
    keywords = [
        "gradebook entries",
        "gradebook_entries",
        "gradebook",
        "student grades",
        "student scores",
        "assignment grades",
        "assignment scores",
        "test scores",
        "quiz scores",
        "exam scores",
        "points earned",
        "points possible",
        "grade details",
    ]
    source_label = "your DCG OSSS data service (gradebook_entries)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        """
        Load gradebook_entries data and attach some simple metadata for the agent layer.
        """
        logger.debug(
            "GradebookEntriesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_gradebook_entries(skip=skip, limit=limit)

        return {
            "rows": rows,
            "gradebook_entries": rows,
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
        return _build_gradebook_entries_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_gradebook_entries_csv(rows)


# register on import
register_handler(GradebookEntriesHandler())
