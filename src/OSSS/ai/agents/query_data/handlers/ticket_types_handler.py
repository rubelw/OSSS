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

logger = logging.getLogger("OSSS.ai.agents.query_data.ticket_types")

API_BASE = "http://host.containers.internal:8081"


# ------------------------------------------------------------------------------
# Shared fetch helper
# ------------------------------------------------------------------------------

async def _fetch_json(url: str, params: Dict[str, Any] | None = None) -> Any:
    """
    Simple wrapper around httpx GET that converts any error into QueryDataError
    without extra keyword args that QueryDataError doesn't expect.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Error calling API: %s", url)
        raise QueryDataError(f"Error calling API {url}: {e}") from e


# ------------------------------------------------------------------------------
# Table-specific fetch helpers
# ------------------------------------------------------------------------------

async def _fetch_ticket_types(
    skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/ticket_types"
    data = await _fetch_json(url, {"skip": skip, "limit": limit})

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected ticket_types payload type: {type(data)!r}"
        )
    return data


async def _fetch_tickets() -> List[Dict[str, Any]]:
    """
    Optional enrichment: load tickets so we can count how many tickets use
    each ticket_type_id. If this endpoint/schema isn't there, we'll catch the
    error and gracefully fall back to no counts.
    """
    url = f"{API_BASE}/api/tickets"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected tickets payload type: {type(data)!r}"
        )
    return data


def _build_ticket_type_usage_counts(
    tickets: List[Dict[str, Any]]
) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for t in tickets:
        ticket_type_id = t.get("ticket_type_id")
        if not ticket_type_id:
            continue
        counts[ticket_type_id] = counts.get(ticket_type_id, 0) + 1
    return counts


# ------------------------------------------------------------------------------
# Markdown / CSV builders
# ------------------------------------------------------------------------------

def _build_ticket_types_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No ticket_types records were found in the system."

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No ticket_types records were found in the system."

    header = "| # | " + " | ".join(fieldnames) + " |\n"
    separator = "|---|" + "|".join(["---"] * len(fieldnames)) + "|\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_vals = [str(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {idx} | " + " | ".join(row_vals) + " |")

    return header + separator + "\n".join(lines)


def _build_ticket_types_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ------------------------------------------------------------------------------
# Handler
# ------------------------------------------------------------------------------

class TicketTypesHandler(QueryHandler):
    mode = "ticket_types"
    keywords = [
        "ticket_types",
        "ticket types",
        "helpdesk ticket types",
        "support ticket types",
        "it ticket types",
        "work order ticket types",
    ]
    source_label = (
        "your DCG OSSS ticket catalog "
        "(ticket_types, optionally enriched with ticket usage)"
    )

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        # Base ticket_types
        ticket_type_rows = await _fetch_ticket_types(skip=skip, limit=limit)

        # Optional enrichment: count how many tickets use each type
        usage_counts: Dict[str, int] = {}
        try:
            tickets = await _fetch_tickets()
            usage_counts = _build_ticket_type_usage_counts(tickets)
        except Exception:
            # Don't fail the whole handler if /api/tickets isn't available.
            logger.warning(
                "TicketTypesHandler: enrichment via /api/tickets failed; "
                "continuing with base ticket_types only.",
                exc_info=True,
            )

        enriched: List[Dict[str, Any]] = []
        for row in ticket_type_rows:
            type_id = row.get("id")

            # Try to build a friendly display string if the schema cooperates
            name = row.get("name") or row.get("title") or ""
            code = row.get("code") or ""
            display = name
            if name and code:
                display = f"{name} ({code})"
            elif code and not name:
                display = code

            enriched.append(
                {
                    **row,
                    "ticket_type_display": display or None,
                    "tickets_count": usage_counts.get(type_id, 0),
                }
            )

        return {
            "rows": enriched,
            "ticket_types": enriched,
            "enrichment": {
                "ticket_types_count": len(ticket_type_rows),
                "tickets_counted": sum(usage_counts.values()) if usage_counts else 0,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_ticket_types_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_ticket_types_csv(rows)


# register on import
register_handler(TicketTypesHandler())
