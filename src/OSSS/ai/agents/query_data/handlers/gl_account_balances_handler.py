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

logger = logging.getLogger("OSSS.ai.agents.query_data.gl_account_balances")

API_BASE = os.getenv(
    "OSSS_GL_ACCOUNT_BALANCES_API_BASE",
    "http://host.containers.internal:8081",
)
GL_ACCOUNT_BALANCES_ENDPOINT = "/api/gl_account_balances"

# Safety limits so we don't blow up markdown or CSV exports.
MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_gl_account_balances(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch gl_account_balances rows from the OSSS data API with robust error handling.
    """
    url = f"{API_BASE}{GL_ACCOUNT_BALANCES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching gl_account_balances from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode gl_account_balances API JSON")
                raise QueryDataError(
                    f"Error decoding gl_account_balances API JSON: {json_err}",
                    gl_account_balances_url=url,
                ) from json_err

    except httpx.RequestError as e:
        logger.exception("Network error calling gl_account_balances API")
        raise QueryDataError(
            f"Network error querying gl_account_balances API: {e}",
            gl_account_balances_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("gl_account_balances API returned HTTP %s", status)
        raise QueryDataError(
            f"gl_account_balances API returned HTTP {status}",
            gl_account_balances_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling gl_account_balances API")
        raise QueryDataError(
            f"Unexpected error querying gl_account_balances API: {e}",
            gl_account_balances_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected gl_account_balances payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected gl_account_balances payload type: {type(data)!r}",
            gl_account_balances_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in gl_account_balances payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d gl_account_balances records (skip=%s, limit=%s)",
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


def _select_gl_account_balances_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    """
    Choose a stable, user-friendly column ordering, but gracefully
    include any extra keys that the API returns.
    """
    if not rows:
        return []

    # Adjust this preferred order to match your actual gl_account_balances schema.
    preferred_order = [
        "id",
        "gl_account_id",
        "account_number",
        "account_name",
        "fiscal_year_id",
        "fiscal_year_code",
        "fiscal_period_id",
        "fiscal_period_code",
        "as_of_date",
        "beginning_balance",
        "debits",
        "credits",
        "net_activity",
        "ending_balance",
        "fund",
        "function",
        "program",
        "project",
        "location",
        "is_closed",
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


def _build_gl_account_balances_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    """
    Render gl_account_balances rows as a markdown table with row limits
    and a friendly truncation notice.
    """
    if not rows:
        return "No gl_account_balances records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_gl_account_balances_fields(display)
    if not fieldnames:
        return "No gl_account_balances records were found in the system."

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
            "GL account balance records. You can request CSV to see the full dataset._"
        )

    return table


def _build_gl_account_balances_csv(
    rows: List[Dict[str, Any]],
) -> str:
    """
    Render gl_account_balances rows as CSV with a cap and comment-based truncation notice.
    """
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_gl_account_balances_fields(display)
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
            f"# Truncated to first {MAX_CSV_ROWS} of {total} gl_account_balance rows\n"
        )

    return csv_text


class GlAccountBalancesHandler(QueryHandler):
    mode = "gl_account_balances"
    keywords = [
        "gl account balances",
        "gl_account_balances",
        "general ledger balances",
        "account balances",
        "trial balance",
        "ending balances",
        "ledger balances",
    ]
    source_label = "your DCG OSSS data service (gl_account_balances)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        """
        Load gl_account_balances data and attach some simple metadata for the agent layer.
        """
        logger.debug(
            "GlAccountBalancesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_gl_account_balances(skip=skip, limit=limit)

        return {
            "rows": rows,
            "gl_account_balances": rows,
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
        return _build_gl_account_balances_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_gl_account_balances_csv(rows)


# register on import
register_handler(GlAccountBalancesHandler())
