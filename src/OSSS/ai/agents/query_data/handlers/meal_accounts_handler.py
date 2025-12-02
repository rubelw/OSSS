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

logger = logging.getLogger("OSSS.ai.agents.query_data.meal_accounts")

API_BASE = os.getenv(
    "OSSS_MEAL_ACCOUNTS_API_BASE",
    "http://host.containers.internal:8081",
)
MEAL_ACCOUNTS_ENDPOINT = "/api/meal_accounts"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_meal_accounts(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}{MEAL_ACCOUNTS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching meal_accounts from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode meal_accounts API JSON")
                raise QueryDataError(
                    f"Error decoding meal_accounts API JSON: {json_err}",
                    meal_accounts_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling meal_accounts API")
        raise QueryDataError(
            f"Network error querying meal_accounts API: {e}",
            meal_accounts_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("meal_accounts API returned HTTP %s", status)
        raise QueryDataError(
            f"meal_accounts API returned HTTP {status}",
            meal_accounts_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling meal_accounts API")
        raise QueryDataError(
            f"Unexpected error querying meal_accounts API: {e}",
            meal_accounts_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected meal_accounts payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected meal_accounts payload type: {type(data)!r}",
            meal_accounts_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in meal_accounts payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d meal_accounts records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_meal_accounts_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "account_code",
        "meal_account_code",
        "student_id",
        "student_code",
        "student_name",
        "household_id",
        "household_code",
        "balance",
        "status",
        "last_transaction_at",
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


def _build_meal_accounts_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No meal_accounts records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]
    fieldnames = _select_meal_accounts_fields(display)
    if not fieldnames:
        return "No meal_accounts records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"

    lines: List[str] = []
    for idx, r in enumerate(display, start=1):
        cells = [_escape_md(idx)] + [_escape_md(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {' | '.join(cells)} |")

    table = header + separator + "\n".join(lines)

    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of "
            f"{total} meal account records. "
            "You can request CSV to see the full dataset._"
        )

    return table


def _build_meal_accounts_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]
    fieldnames = _select_meal_accounts_fields(display)
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
            f"# Truncated to first {MAX_CSV_ROWS} of "
            f"{total} meal account rows\n"
        )
    return csv_text


class MealAccountsHandler(QueryHandler):
    mode = "meal_accounts"
    keywords = [
        "meal accounts",
        "meal_accounts",
        "lunch accounts",
        "cafeteria accounts",
        "dcg meal accounts",
    ]
    source_label = "DCG OSSS data service (meal_accounts)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "MealAccountsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_meal_accounts(skip=skip, limit=limit)
        return {
            "rows": rows,
            "meal_accounts": rows,
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
        return _build_meal_accounts_markdown_table(rows)

    def to_csv(
        self,
        rows: List[Dict[str, Any]],
    ) -> str:
        return _build_meal_accounts_csv(rows)


register_handler(MealAccountsHandler())
