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

logger = logging.getLogger("OSSS.ai.agents.query_data.warranties")

API_BASE = "http://host.containers.internal:8081"


# ---------------------------------------------------------------------------
# Fetch Low-Level API Call
# ---------------------------------------------------------------------------
async def _fetch_warranties(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/warrantys"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

    except Exception as e:
        logger.exception("Error calling warranties API")
        raise QueryDataError(f"Error querying warrantys API: {e}") from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected warrantys payload type: {type(data)!r}"
        )

    return data


# ---------------------------------------------------------------------------
# Sorting & Field Prioritization Helpers
# ---------------------------------------------------------------------------
def _preferred_field_order(fields: List[str]) -> List[str]:
    preferred = [
        "id",
        "asset_id",
        "vendor_id",
        "provider",
        "coverage_type",
        "start_date",
        "end_date",
        "is_active",
        "created_at",
        "updated_at",
    ]

    ordered = []
    for f in preferred:
        if f in fields:
            ordered.append(f)

    # Append any fields not in preferred order
    for f in fields:
        if f not in ordered:
            ordered.append(f)

    return ordered


def _sort_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return rows

    sample = rows[0]
    if "updated_at" in sample:
        key_field = "updated_at"
    elif "created_at" in sample:
        key_field = "created_at"
    else:
        return rows

    try:
        return sorted(rows, key=lambda r: (r.get(key_field) or ""), reverse=True)
    except Exception:
        logger.debug("Could not sort warranties by %s; returning unsorted.", key_field)
        return rows


# ---------------------------------------------------------------------------
# Markdown & CSV Builders
# ---------------------------------------------------------------------------
def _build_warranties_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No warranties records were found in the system."

    rows = _sort_rows(rows)
    raw_fields = list(rows[0].keys())
    fields = _preferred_field_order(raw_fields)

    header = "| # | " + " | ".join(fields) + " |\n"
    separator = "|---|" + "|".join(["---"] * len(fields)) + "|\n"

    lines = []
    for idx, r in enumerate(rows, start=1):
        row_cells = [str(r.get(f, "")) for f in fields]
        lines.append(f"| {idx} | " + " | ".join(row_cells) + " |")

    return header + separator + "\n".join(lines)


def _build_warranties_csv(rows: List[Dict[str, Any]]) -> str:
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
# QueryData Handler
# ---------------------------------------------------------------------------
class WarrantiesHandler(QueryHandler):
    mode = "warranties"
    keywords = [
        "warranties",
        "warranty",
        "asset warranties",
        "equipment warranty",
    ]
    source_label = "your DCG OSSS data service (warranties)"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        rows = await _fetch_warranties(skip=skip, limit=limit)
        rows = _sort_rows(rows)

        return {
            "rows": rows,
            "warranties": rows,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_warranties_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_warranties_csv(rows)


# Register handler
register_handler(WarrantiesHandler())
