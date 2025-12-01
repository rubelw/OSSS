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

logger = logging.getLogger("OSSS.ai.agents.query_data.ticket_scans")

API_BASE = "http://host.containers.internal:8081"


# ------------------------------------------------------------------------------
# Shared HTTP helper
# ------------------------------------------------------------------------------

async def _fetch_json(url: str, params: Dict[str, Any] | None = None) -> Any:
    """
    Thin wrapper around httpx GET that normalizes errors into QueryDataError.

    NOTE: We only pass a message into QueryDataError (no extra kwargs) so we
    don't hit the 'unexpected keyword argument' issues you've seen before.
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

async def _fetch_ticket_scans(
    skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/ticket_scans"
    data = await _fetch_json(url, {"skip": skip, "limit": limit})

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected ticket_scans payload type: {type(data)!r}"
        )
    return data


async def _fetch_tickets() -> List[Dict[str, Any]]:
    """
    Optional enrichment: load tickets so we can attach a human-friendly
    ticket display to each scan (e.g., ticket code, event, seat).
    """
    url = f"{API_BASE}/api/tickets"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected tickets payload type: {type(data)!r}"
        )
    return data


async def _fetch_user_accounts() -> List[Dict[str, Any]]:
    """
    Optional enrichment: load user accounts so we can show who scanned
    the ticket (scanner / gate staff).
    """
    url = f"{API_BASE}/api/user_accounts"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected user_accounts payload type: {type(data)!r}"
        )
    return data


# ------------------------------------------------------------------------------
# Enrichment helpers
# ------------------------------------------------------------------------------

def _build_ticket_lookup(
    tickets: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    Build index: ticket_id -> ticket row
    """
    lookup: Dict[str, Dict[str, Any]] = {}
    for t in tickets:
        tid = t.get("id")
        if not tid:
            continue
        lookup[tid] = t
    return lookup


def _build_user_lookup(
    users: List[Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    Build index: user_id -> user row
    """
    lookup: Dict[str, Dict[str, Any]] = {}
    for u in users:
        uid = u.get("id")
        if not uid:
            continue
        lookup[uid] = u
    return lookup


def _ticket_display(ticket: Dict[str, Any] | None) -> str | None:
    if not ticket:
        return None

    # Best-effort: depend only on common-ish fields
    code = ticket.get("code") or ticket.get("ticket_code")
    event = ticket.get("event_name") or ticket.get("name")
    seat = ticket.get("seat") or ticket.get("seat_label")

    pieces = []
    if code:
        pieces.append(str(code))
    if event:
        pieces.append(str(event))
    if seat:
        pieces.append(f"Seat {seat}")

    return " - ".join(pieces) if pieces else None


def _user_display(user: Dict[str, Any] | None) -> str | None:
    if not user:
        return None

    full_name = user.get("full_name")
    display_name = user.get("display_name")
    username = user.get("username")
    email = user.get("email")

    if full_name:
        return str(full_name)
    if display_name:
        return str(display_name)
    if username and email:
        return f"{username} ({email})"
    return username or email


# ------------------------------------------------------------------------------
# Markdown / CSV builders
# ------------------------------------------------------------------------------

def _build_ticket_scans_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No ticket_scans records were found in the system."

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No ticket_scans records were found in the system."

    header = "| # | " + " | ".join(fieldnames) + " |\n"
    separator = "|---|" + "|".join(["---"] * len(fieldnames)) + "|\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_vals = [str(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {idx} | " + " | ".join(row_vals) + " |")

    return header + separator + "\n".join(lines)


def _build_ticket_scans_csv(rows: List[Dict[str, Any]]) -> str:
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

class TicketScansHandler(QueryHandler):
    mode = "ticket_scans"
    keywords = [
        "ticket_scans",
        "ticket scans",
        "scan logs",
        "ticket scan logs",
        "ticket check-ins",
        "ticket checkins",
        "gate scans",
        "entry scans",
    ]
    source_label = (
        "your DCG OSSS ticket scanning service "
        "(ticket_scans, optionally enriched with tickets and user accounts)"
    )

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        # Base scans
        scan_rows = await _fetch_ticket_scans(skip=skip, limit=limit)

        ticket_lookup: Dict[str, Dict[str, Any]] = {}
        user_lookup: Dict[str, Dict[str, Any]] = {}
        enrichment_info: Dict[str, Any] = {}

        # Try to enrich with tickets + user_accounts; never fail the whole call.
        try:
            tickets = await _fetch_tickets()
            ticket_lookup = _build_ticket_lookup(tickets)
            enrichment_info["tickets_count"] = len(tickets)
        except Exception:
            logger.warning(
                "TicketScansHandler: enrichment via /api/tickets failed; "
                "continuing with base scan data.",
                exc_info=True,
            )

        try:
            users = await _fetch_user_accounts()
            user_lookup = _build_user_lookup(users)
            enrichment_info["user_accounts_count"] = len(users)
        except Exception:
            logger.warning(
                "TicketScansHandler: enrichment via /api/user_accounts failed; "
                "continuing without scanner user details.",
                exc_info=True,
            )

        enriched: List[Dict[str, Any]] = []
        for row in scan_rows:
            ticket_id = row.get("ticket_id")
            scanner_user_id = (
                row.get("scanner_user_id")
                or row.get("user_id")
                or row.get("scanned_by_user_id")
            )

            ticket = ticket_lookup.get(ticket_id) if ticket_lookup else None
            user = user_lookup.get(scanner_user_id) if user_lookup else None

            enriched.append(
                {
                    **row,
                    "ticket_display": _ticket_display(ticket),
                    "scanner_user_display": _user_display(user),
                }
            )

        return {
            "rows": enriched,
            "ticket_scans": enriched,
            "enrichment": enrichment_info,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_ticket_scans_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_ticket_scans_csv(rows)


# register on import
register_handler(TicketScansHandler())
