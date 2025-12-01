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
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.waivers")

API_BASE = "http://host.containers.internal:8081"


# ---------------------------------------------------------------------------
# Low-level fetch
# ---------------------------------------------------------------------------
async def _fetch_waivers(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/waivers"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.exception("Error calling waivers API")
        raise QueryDataError(f"Error querying waivers API: {e}") from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected waivers payload type: {type(data)!r}"
        )

    return data


# ---------------------------------------------------------------------------
# Sorting & Column Ordering
# ---------------------------------------------------------------------------
def _preferred_field_order(fields: List[str]) -> List[str]:
    preferred = [
        "id",
        "student_id",
        "program_id",
        "waiver_type",
        "reason",
        "approved_by",
        "start_date",
        "end_date",
        "is_active",
        "created_at",
        "updated_at",
    ]

    ordered = [f for f in preferred if f in fields]
    for f in fields:
        if f not in ordered:
            ordered.append(f)

    return ordered


def _sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return rows

    sample = rows[0]
    key = None
    if "updated_at" in sample:
        key = "updated_at"
    elif "created_at" in sample:
        key = "created_at"

    if not key:
        return rows

    try:
        return sorted(rows, key=lambda r: (r.get(key) or ""), reverse=True)
    except Exception:
        logger.debug("Unable to sort waivers by %s", key)
        return rows


# ---------------------------------------------------------------------------
# Markdown + CSV
# ---------------------------------------------------------------------------
def _build_waivers_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No waivers records were found in the system."

    rows = _sort_rows(rows)
    raw_fields = list(rows[0].keys())
    fields = _preferred_field_order(raw_fields)

    header = "| # | " + " | ".join(fields) + " |\n"
    separator = "|---|" + "|".join(["---"] * len(fields)) + "|\n"

    lines = []
    for idx, r in enumerate(rows, start=1):
        cells = [str(r.get(f, "")) for f in fields]
        lines.append(f"| {idx} | " + " | ".join(cells) + " |")

    return header + separator + "\n".join(lines)


def _build_waivers_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    rows = _sort_rows(rows)
    raw_fields = list(rows[0].keys())
    fields = _preferred_field_order(raw_fields)

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
class WaiversHandler(QueryHandler):
    mode = "waivers"
    keywords = [
        "waivers",
        "waiver",
        "student waivers",
        "program waivers",
        "fee waivers",
    ]
    source_label = "your DCG OSSS data service (waivers)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:

        rows = await _fetch_waivers(skip=skip, limit=limit)
        rows = _sort_rows(rows)

        return {
            "rows": rows,
            "waivers": rows,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_waivers_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_waivers_csv(rows)


# Register on import
register_handler(WaiversHandler())
