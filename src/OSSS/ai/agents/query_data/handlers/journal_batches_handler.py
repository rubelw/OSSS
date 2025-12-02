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

logger = logging.getLogger("OSSS.ai.agents.query_data.journal_batches")

API_BASE = os.getenv(
    "OSSS_JOURNAL_BATCHES_API_BASE",
    "http://host.containers.internal:8081",
)
JOURNAL_BATCHES_ENDPOINT = "/api/journal_batchs"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_journal_batches(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}{JOURNAL_BATCHES_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching journal_batches from %s with params skip=%s, limit=%s",
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
                    "Failed to decode journal_batches API JSON",
                )
                raise QueryDataError(
                    "Error decoding journal_batches API JSON: "
                    f"{json_err}",
                    journal_batches_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling journal_batches API")
        raise QueryDataError(
            f"Network error querying journal_batches API: {e}",
            journal_batches_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception(
            "journal_batches API returned HTTP %s",
            status,
        )
        raise QueryDataError(
            f"journal_batches API returned HTTP {status}",
            journal_batches_url=url,
        ) from e
    except Exception as e:
        logger.exception(
            "Unexpected error calling journal_batches API",
        )
        raise QueryDataError(
            "Unexpected error querying journal_batches API: "
            f"{e}",
            journal_batches_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error(
            "Unexpected journal_batches payload type: %r",
            type(data),
        )
        raise QueryDataError(
            "Unexpected journal_batches payload type: "
            f"{type(data)!r}",
            journal_batches_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in "
                "journal_batches payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d journal_batches records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_journal_batches_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "batch_code",
        "description",
        "status",
        "period",
        "posting_date",
        "total_entries",
        "total_debits",
        "total_credits",
        "created_by",
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


def _build_journal_batches_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No journal_batches records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]
    fieldnames = _select_journal_batches_fields(display)
    if not fieldnames:
        return "No journal_batches records were found in the system."

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
            f"{total} journal batch records. "
            "You can request CSV to see the full dataset._"
        )

    return table


def _build_journal_batches_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]
    fieldnames = _select_journal_batches_fields(display)
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
            f"{total} journal batch rows\n"
        )
    return csv_text


class JournalBatchesHandler(QueryHandler):
    mode = "journal_batches"
    keywords = [
        "journal_batches",
        "journal batches",
        "gl batches",
        "ledger batches",
    ]
    source_label = "your DCG OSSS data service (journal_batches)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "JournalBatchesHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )

        rows = await _fetch_journal_batches(skip=skip, limit=limit)
        return {
            "rows": rows,
            "journal_batches": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_journal_batches_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_journal_batches_csv(rows)


register_handler(JournalBatchesHandler())
