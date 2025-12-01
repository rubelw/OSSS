from __future__ import annotations

from typing import Any, Dict, List
import httpx
import csv
import io
import logging

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError  # optional

logger = logging.getLogger("OSSS.ai.agents.query_data.webhooks")

API_BASE = "http://host.containers.internal:8081"


# ---------------------------------------------------------------------------
# Low-level fetch
# ---------------------------------------------------------------------------
async def _fetch_webhooks(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Call the FastAPI /api/webhooks endpoint and return a list of dict rows.
    """
    url = f"{API_BASE}/api/webhooks"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.exception("Error calling webhooks API")
        # NOTE: QueryDataError only takes a message, so do NOT pass extra kwargs.
        raise QueryDataError(f"Error querying webhooks API: {e}") from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected webhooks payload type: {type(data)!r}"
        )

    return data


# ---------------------------------------------------------------------------
# Helpers for table formatting
# ---------------------------------------------------------------------------
def _preferred_field_order(all_fields: List[str]) -> List[str]:
    """
    Reorder columns so the most useful webhook fields appear first.
    Unknown fields are appended at the end in original order.
    """
    preferred = [
        "id",
        "name",
        "event",
        "topic",
        "url",
        "target_url",
        "is_active",
        "enabled",
        "created_at",
        "updated_at",
        "last_success_at",
        "last_error_at",
    ]

    ordered: List[str] = []
    for f in preferred:
        if f in all_fields and f not in ordered:
            ordered.append(f)

    for f in all_fields:
        if f not in ordered:
            ordered.append(f)

    return ordered


def _sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Sort webhooks by most recently updated if updated_at exists,
    otherwise by created_at, otherwise unsorted.
    """
    if not rows:
        return rows

    key_field = None
    sample = rows[0]
    if "updated_at" in sample:
        key_field = "updated_at"
    elif "created_at" in sample:
        key_field = "created_at"

    if key_field is None:
        return rows

    try:
        return sorted(
            rows,
            key=lambda r: (r.get(key_field) or ""),
            reverse=True,
        )
    except Exception:
        logger.debug("Could not sort webhooks by %s; returning unsorted.", key_field)
        return rows


# ---------------------------------------------------------------------------
# Markdown & CSV builders
# ---------------------------------------------------------------------------
def _build_webhooks_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No webhooks records were found in the system."

    rows = _sort_rows(rows)
    raw_fieldnames = list(rows[0].keys())
    if not raw_fieldnames:
        return "No webhooks records were found in the system."

    fieldnames = _preferred_field_order(raw_fieldnames)

    header_cells = ["#"] + fieldnames
    header = "| " + " | ".join(header_cells) + " |\n"
    separator = "| " + " | ".join(["---"] * len(header_cells)) + " |\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_cells = [str(idx)] + [str(r.get(f, "")) for f in fieldnames]
        lines.append("| " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


def _build_webhooks_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    rows = _sort_rows(rows)
    raw_fieldnames = list(rows[0].keys())
    if not raw_fieldnames:
        return ""

    fieldnames = _preferred_field_order(raw_fieldnames)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
class WebhooksHandler(QueryHandler):
    mode = "webhooks"
    keywords = [
        "webhooks",
        "webhook",
        "outbound webhooks",
        "event webhooks",
        "callback webhooks",
    ]
    source_label = "your DCG OSSS data service (webhooks)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        """
        Fetch raw webhook rows. If you later enrich with delivery logs, etc.,
        you can expand this dict.
        """
        rows = await _fetch_webhooks(skip=skip, limit=limit)
        rows = _sort_rows(rows)

        return {
            "rows": rows,
            "webhooks": rows,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_webhooks_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_webhooks_csv(rows)


# register on import
register_handler(WebhooksHandler())
