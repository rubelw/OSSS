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

logger = logging.getLogger("OSSS.ai.agents.query_data.behavior_codes")

API_BASE = os.getenv(
    "OSSS_BEHAVIOR_CODES_API_BASE",
    "http://host.containers.internal:8081",
)
BEHAVIOR_CODES_ENDPOINT = "/api/behavior_codes"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_behavior_codes(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch behavior_codes rows from the OSSS data API.
    """
    url = f"{API_BASE}{BEHAVIOR_CODES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching behavior_codes from %s with params skip=%s, limit=%s",
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
                logger.exception(
                    "Failed to decode behavior_codes API JSON"
                )
                raise QueryDataError(
                    f"Error decoding behavior_codes API JSON: {json_err}",
                    behavior_codes_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling behavior_codes API")
        raise QueryDataError(
            f"Network error querying behavior_codes API: {e}",
            behavior_codes_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("behavior_codes API returned HTTP %s", status)
        raise QueryDataError(
            f"behavior_codes API returned HTTP {status}",
            behavior_codes_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling behavior_codes API")
        raise QueryDataError(
            f"Unexpected error querying behavior_codes API: {e}",
            behavior_codes_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected behavior_codes payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected behavior_codes payload type: {type(data)!r}",
            behavior_codes_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in behavior_codes payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d behavior_codes records (skip=%s, limit=%s)",
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


def _select_behavior_codes_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    """
    Choose a stable, user-friendly column ordering, but include extra keys.
    """
    if not rows:
        return []

    preferred_order = [
        "id",
        "code",
        "short_code",
        "description",
        "category",          # minor, major, etc.
        "severity_level",
        "state_code",
        "is_suspension",
        "is_expulsion",
        "is_referral",
        "is_active",
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


def _build_behavior_codes_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    """
    Render behavior_codes rows as a markdown table with row limits.
    """
    if not rows:
        return "No behavior_codes records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_behavior_codes_fields(display)
    if not fieldnames:
        return "No behavior_codes records were found in the system."

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
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} behavior code "
            "records. You can request CSV to see the full dataset._"
        )

    return table


def _build_behavior_codes_csv(
    rows: List[Dict[str, Any]],
) -> str:
    """
    Render behavior_codes rows as CSV with a cap and truncation notice.
    """
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_behavior_codes_fields(display)
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
            f"# Truncated to first {MAX_CSV_ROWS} of {total} behavior_codes rows\n"
        )

    return csv_text


class BehaviorCodesHandler(QueryHandler):
    mode = "behavior_codes"
    keywords = [
        "behavior codes",
        "behavior_codes",
        "discipline codes",
        "incident codes",
    ]
    source_label = "your DCG OSSS data service (behavior_codes)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        """
        Load behavior_codes data and attach some simple metadata.
        """
        logger.debug(
            "BehaviorCodesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_behavior_codes(skip=skip, limit=limit)

        return {
            "rows": rows,
            "behavior_codes": rows,
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
        return _build_behavior_codes_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_behavior_codes_csv(rows)


# register on import
register_handler(BehaviorCodesHandler())
