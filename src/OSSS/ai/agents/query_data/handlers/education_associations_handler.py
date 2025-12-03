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

logger = logging.getLogger("OSSS.ai.agents.query_data.education_associations")

API_BASE = os.getenv(
    "OSSS_EDUCATION_ASSOCIATIONS_API_BASE",
    "http://host.containers.internal:8081",
)
EDU_ASSOC_ENDPOINT = "/api/education_associations"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2000


# ---------------------------------------------------------------------------
# Fetch Function
# ---------------------------------------------------------------------------
async def _fetch_education_associations(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch education_associations rows with robust error handling,
    logging, type validation, and cleaning.
    """
    url = f"{API_BASE}{EDU_ASSOC_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching education associations from %s with skip=%s, limit=%s",
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
                logger.exception("Failed to decode JSON from education_associations API")
                raise QueryDataError(
                    f"Error decoding education_associations API JSON: {json_err}",
                    education_associations_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling education_associations API")
        raise QueryDataError(
            f"Network error querying education_associations API: {e}",
            education_associations_url=url,
        ) from e

    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("education_associations API returned HTTP %s", status)
        raise QueryDataError(
            f"education_associations API returned HTTP {status}",
            education_associations_url=url,
        ) from e

    except Exception as e:
        logger.exception("Unexpected error calling education_associations API")
        raise QueryDataError(
            f"Unexpected error querying education_associations API: {e}",
            education_associations_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error(
            "Unexpected education_associations payload type: %r",
            type(data)
        )
        raise QueryDataError(
            f"Unexpected education_associations payload type: {type(data)!r}",
            education_associations_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item in education_associations at index %s: %r",
                i, type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d education_associations records",
        len(cleaned),
    )
    return cleaned


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def _escape_md(value: Any) -> str:
    """Escape markdown-sensitive characters."""
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_fields(rows: Sequence[Dict[str, Any]]) -> List[str]:
    """
    Field ordering heuristic: preferred order + any additional fields.
    """
    if not rows:
        return []

    preferred_order = [
        "id",
        "name",
        "contact",
        "attributes",
        "created_at",
        "updated_at",
    ]

    all_keys = []
    for r in rows:
        for k in r.keys():
            if k not in all_keys:
                all_keys.append(k)

    ordered = [k for k in preferred_order if k in all_keys]
    ordered.extend(k for k in all_keys if k not in ordered)
    return ordered


# ---------------------------------------------------------------------------
# Markdown Table Builder
# ---------------------------------------------------------------------------
def _build_education_associations_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No education_associations records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_fields(display)
    if not fieldnames:
        return "No education_associations records were found in the system."

    header = f"| # | {' | '.join(fieldnames)} |\n"
    separator = f"|---|{'|'.join(['---'] * len(fieldnames))}|\n"

    lines = []
    for idx, r in enumerate(display, start=1):
        row_cells = [str(idx)] + [_escape_md(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {' | '.join(row_cells)} |")

    table = header + separator + "\n".join(lines)

    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} "
            "education_associations records. Request CSV for full results._"
        )

    return table


# ---------------------------------------------------------------------------
# CSV Builder
# ---------------------------------------------------------------------------
def _build_education_associations_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    display = rows[:MAX_CSV_ROWS]
    fieldnames = _select_fields(display)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(display)

    csv_text = output.getvalue()
    if len(rows) > MAX_CSV_ROWS:
        csv_text += (
            f"# Truncated to first {MAX_CSV_ROWS} of {len(rows)} "
            "education_associations rows\n"
        )

    return csv_text


# ---------------------------------------------------------------------------
# Handler Class
# ---------------------------------------------------------------------------
class EducationAssociationsHandler(QueryHandler):
    mode = "education_associations"

    keywords = [
        "education associations",
        "education_associations",
        "school associations",
        "district associations",
        "academic associations",
    ]

    source_label = "your DCG OSSS data service (education_associations)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        rows = await _fetch_education_associations(skip=skip, limit=limit)
        return {
            "rows": rows,
            "education_associations": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_education_associations_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_education_associations_csv(rows)


register_handler(EducationAssociationsHandler())
