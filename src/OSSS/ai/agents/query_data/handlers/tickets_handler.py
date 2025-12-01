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

logger = logging.getLogger("OSSS.ai.agents.query_data.tickets")

API_BASE = "http://host.containers.internal:8081"


# ------------------------------------------------------------------------------
# Shared HTTP helper
# ------------------------------------------------------------------------------

async def _fetch_json(url: str, params: Dict[str, Any] | None = None) -> Any:
    """
    Thin wrapper around httpx GET that normalizes errors into QueryDataError.

    NOTE: Only passes a single message string into QueryDataError so we don't
    hit 'unexpected keyword argument' issues.
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

async def _fetch_tickets(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/tickets"
    data = await _fetch_json(url, {"skip": skip, "limit": limit})

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected tickets payload type: {type(data)!r}"
        )
    return data


async def _fetch_ticket_types() -> List[Dict[str, Any]]:
    """
    Optional enrichment: load ticket types so we can attach the type name/code.
    """
    url = f"{API_BASE}/api/ticket_types"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected ticket_types payload type: {type(data)!r}"
        )
    return data


async def _fetch_ticket_scans() -> List[Dict[str, Any]]:
    """
    Optional enrichment: load ticket scans so we can show scan counts per ticket.
    """
    url = f"{API_BASE}/api/ticket_scans"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected ticket_scans payload type: {type(data)!r}"
        )
    return data


# ------------------------------------------------------------------------------
# Enrichment helpers
# ------------------------------------------------------------------------------

def _build_type_lookup(
    types: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    Build index: ticket_type_id -> ticket_type row
    """
    lookup: Dict[str, Dict[str, Any]] = {}
    for t in types:
        tid = t.get("id")
        if not tid:
            continue
        lookup[tid] = t
    return lookup


def _build_scan_counts(
    scans: List[Dict[str, Any]]
) -> Dict[str, int]:
    """
    Build index: ticket_id -> scan_count
    """
    counts: Dict[str, int] = {}
    for s in scans:
        ticket_id = s.get("ticket_id")
        if not ticket_id:
            continue
        counts[ticket_id] = counts.get(ticket_id, 0) + 1
    return counts


# ------------------------------------------------------------------------------
# Markdown / CSV builders
# ------------------------------------------------------------------------------

def _build_tickets_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No tickets records were found in the system."

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No tickets records were found in the system."

    header = "| # | " + " | ".join(fieldnames) + " |\n"
    separator = "|---|" + "|".join(["---"] * len(fieldnames)) + "|\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_vals = [str(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {idx} | " + " | ".join(row_vals) + " |")

    return header + separator + "\n".join(lines)


def _build_tickets_csv(rows: List[Dict[str, Any]]) -> str:
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

class TicketsHandler(QueryHandler):
    mode = "tickets"
    keywords = [
        "tickets",
        "ticket list",
        "ticket inventory",
        "ticket sales",
        "event tickets",
        "show tickets",
        "tickets report",
    ]
    source_label = (
        "your DCG OSSS ticketing service "
        "(tickets, optionally enriched with ticket types and scans)"
    )

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        # Base tickets
        ticket_rows = await _fetch_tickets(skip=skip, limit=limit)

        type_lookup: Dict[str, Dict[str, Any]] = {}
        scan_counts: Dict[str, int] = {}
        enrichment_info: Dict[str, Any] = {}

        # Try to enrich with ticket types; never fail the whole call.
        try:
            ticket_types = await _fetch_ticket_types()
            type_lookup = _build_type_lookup(ticket_types)
            enrichment_info["ticket_types_count"] = len(ticket_types)
        except Exception:
            logger.warning(
                "TicketsHandler: enrichment via /api/ticket_types failed; "
                "continuing with base ticket data.",
                exc_info=True,
            )

        # Try to enrich with ticket scans; also best-effort.
        try:
            scans = await _fetch_ticket_scans()
            scan_counts = _build_scan_counts(scans)
            enrichment_info["ticket_scans_count"] = len(scans)
        except Exception:
            logger.warning(
                "TicketsHandler: enrichment via /api/ticket_scans failed; "
                "continuing without scan counts.",
                exc_info=True,
            )

        enriched: List[Dict[str, Any]] = []
        for row in ticket_rows:
            type_row = None
            ticket_type_id = row.get("ticket_type_id")
            if type_lookup and ticket_type_id:
                type_row = type_lookup.get(ticket_type_id)

            scan_count = 0
            ticket_id = row.get("id")
            if ticket_id and scan_counts:
                scan_count = scan_counts.get(ticket_id, 0)

            enriched_row: Dict[str, Any] = {
                **row,
                "ticket_type_name": (type_row or {}).get("name"),
                "ticket_type_code": (type_row or {}).get("code"),
                "scan_count": scan_count,
            }
            enriched.append(enriched_row)

        return {
            "rows": enriched,
            "tickets": enriched,
            "enrichment": enrichment_info,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_tickets_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_tickets_csv(rows)


# register on import
register_handler(TicketsHandler())
