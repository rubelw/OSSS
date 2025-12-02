from __future__ import annotations

from typing import Any, Dict, List, Sequence
import httpx
import csv
import io
import logging
import os

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.move_orders")

API_BASE = os.getenv(
    "OSSS_MOVE_ORDERS_API_BASE",
    "http://host.containers.internal:8081",
)
MOVE_ORDERS_ENDPOINT = "/api/move_orders"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_move_orders(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}{MOVE_ORDERS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching move_orders from %s with params skip=%s, limit=%s",
        url,
        skip,
        limit,
    )

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0), verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError as json_err:
                logger.exception("Failed to decode move_orders API JSON")
                raise QueryDataError(
                    f"Error decoding move_orders API JSON: {json_err}",
                    move_orders_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling move_orders API")
        raise QueryDataError(
            f"Network error querying move_orders API: {e}",
            move_orders_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("move_orders API returned HTTP %s", status)
        raise QueryDataError(
            f"move_orders API returned HTTP {status}",
            move_orders_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling move_orders API")
        raise QueryDataError(
            f"Unexpected error querying move_orders API: {e}",
            move_orders_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected move_orders payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected move_orders payload type: {type(data)!r}",
            move_orders_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in move_orders payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d move_orders records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_move_orders_fields(rows: Sequence[Dict[str, Any]]) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "move_order_code",
        "status",
        "source_location",
        "source_org",
        "destination_location",
        "destination_org",
        "requested_by",
        "requested_date",
        "approved_by",
        "approved_date",
        "completed_date",
        "created_at",
        "updated_at",
    ]

    all_keys: List[str] = []
    for r in rows:
        for k in r:
            if k not in all_keys:
                all_keys.append(k)

    ordered = [c for c in preferred_order if c in all_keys]
    ordered.extend(k for k in all_keys if k not in ordered)
    return ordered


def _build_move_orders_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No move_orders records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]

    fieldnames = _select_move_orders_fields(display)
    if not fieldnames:
        return "No move_orders records were found in the system."

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"
    lines: List[str] = []

    for idx, r in enumerate(display, start=1):
        cells = [_escape_md(idx)] + [_escape_md(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(cells) + " |")

    table = header + separator + "\n".join(lines)
    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} move order records. "
            "You can request CSV to see the full dataset._"
        )
    return table


def _build_move_orders_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]

    fieldnames = _select_move_orders_fields(display)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(display)
    csv_text = output.getvalue()

    if total > MAX_CSV_ROWS:
        csv_text += f"# Truncated to first {MAX_CSV_ROWS} of {total} move order rows\n"
    return csv_text


class MoveOrdersHandler(QueryHandler):
    mode = "move_orders"
    keywords = [
        "move orders",
        "move_orders",
        "inventory move orders",
        "transfer orders",
        "room move orders",
        "dcg move orders",
    ]
    source_label = "DCG OSSS data service (move_orders)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "MoveOrdersHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )
        rows = await _fetch_move_orders(skip=skip, limit=limit)
        return {
            "rows": rows,
            "move_orders": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_move_orders_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_move_orders_csv(rows)


register_handler(MoveOrdersHandler())
