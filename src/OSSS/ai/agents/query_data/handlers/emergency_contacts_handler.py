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

logger = logging.getLogger("OSSS.ai.agents.query_data.emergency_contacts")

API_BASE = os.getenv(
    "OSSS_EMERGENCY_CONTACTS_API_BASE",
    "http://host.containers.internal:8081",
)
EMERGENCY_CONTACTS_ENDPOINT = "/api/emergency_contacts"

MAX_MARKDOWN_ROWS = 50
MAX_CSV_ROWS = 2_000


async def _fetch_emergency_contacts(
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch emergency_contacts rows from the OSSS data API.
    """
    url = f"{API_BASE}{EMERGENCY_CONTACTS_ENDPOINT}"
    params = {"skip": skip, "limit": limit}

    logger.debug(
        "Fetching emergency_contacts from %s with params skip=%s, limit=%s",
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
                logger.exception("Failed to decode emergency_contacts API JSON")
                raise QueryDataError(
                    f"Error decoding emergency_contacts API JSON: {json_err}",
                    emergency_contacts_url=url,
                ) from json_err
    except httpx.RequestError as e:
        logger.exception("Network error calling emergency_contacts API")
        raise QueryDataError(
            f"Network error querying emergency_contacts API: {e}",
            emergency_contacts_url=url,
        ) from e
    except httpx.HTTPStatusError as e:
        status = getattr(e.response, "status_code", None)
        logger.exception("emergency_contacts API returned HTTP %s", status)
        raise QueryDataError(
            f"emergency_contacts API returned HTTP {status}",
            emergency_contacts_url=url,
        ) from e
    except Exception as e:
        logger.exception("Unexpected error calling emergency_contacts API")
        raise QueryDataError(
            f"Unexpected error querying emergency_contacts API: {e}",
            emergency_contacts_url=url,
        ) from e

    if not isinstance(data, list):
        logger.error("Unexpected emergency_contacts payload type: %r", type(data))
        raise QueryDataError(
            f"Unexpected emergency_contacts payload type: {type(data)!r}",
            emergency_contacts_url=url,
        )

    cleaned: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            logger.warning(
                "Skipping non-dict item at index %s in emergency_contacts payload: %r",
                i,
                type(item),
            )
            continue
        cleaned.append(item)

    logger.debug(
        "Fetched %d emergency_contacts records (skip=%s, limit=%s)",
        len(cleaned),
        skip,
        limit,
    )
    return cleaned


def _escape_md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", r"\|").replace("`", r"\`")


def _select_emergency_contacts_fields(
    rows: Sequence[Dict[str, Any]],
) -> List[str]:
    if not rows:
        return []

    preferred_order = [
        "id",
        "person_type",        # student, staff, etc.
        "person_id",
        "person_name",
        "contact_name",
        "relationship",
        "priority",           # 1, 2, 3...
        "is_primary",
        "phone_1",
        "phone_1_type",
        "phone_2",
        "phone_2_type",
        "email",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "postal_code",
        "country",
        "allowed_to_pick_up",
        "notes",
        "school_id",
        "school_name",
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


def _build_emergency_contacts_markdown_table(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return "No emergency_contacts records were found in the system."

    total = len(rows)
    display = rows[:MAX_MARKDOWN_ROWS]
    fieldnames = _select_emergency_contacts_fields(display)
    if not fieldnames:
        return "No emergency_contacts records were found in the system."

    header_cells = ["#"] + fieldnames
    header = f"| {' | '.join(header_cells)} |\n"
    separator = f"| {' | '.join(['---'] * len(header_cells))} |\n"
    lines: List[str] = []

    for idx, r in enumerate(display, start=1):
        row_cells = [_escape_md(idx)] + [_escape_md(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {' | '.join(row_cells)} |")

    table = header + separator + "\n".join(lines)
    if total > MAX_MARKDOWN_ROWS:
        table += (
            f"\n\n_Showing first {MAX_MARKDOWN_ROWS} of {total} emergency contact records. "
            "You can request CSV to see the full dataset._"
        )
    return table


def _build_emergency_contacts_csv(
    rows: List[Dict[str, Any]],
) -> str:
    if not rows:
        return ""

    total = len(rows)
    display = rows[:MAX_CSV_ROWS]
    fieldnames = _select_emergency_contacts_fields(display)
    if not fieldnames:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(display)
    csv_text = output.getvalue()

    if total > MAX_CSV_ROWS:
        csv_text += (
            f"# Truncated to first {MAX_CSV_ROWS} of {total} emergency_contact rows\n"
        )

    return csv_text


class EmergencyContactsHandler(QueryHandler):
    mode = "emergency_contacts"
    keywords = [
        "emergency contacts",
        "emergency_contacts",
        "student emergency contacts",
        "staff emergency contacts",
        "contact list for emergencies",
    ]
    source_label = "your DCG OSSS data service (emergency_contacts)"

    async def fetch(
        self,
        ctx: AgentContext,
        skip: int,
        limit: int,
    ) -> FetchResult:
        logger.debug(
            "EmergencyContactsHandler.fetch(skip=%s, limit=%s, user=%s)",
            skip,
            limit,
            getattr(ctx, "user_id", None),
        )
        rows = await _fetch_emergency_contacts(skip=skip, limit=limit)
        return {
            "rows": rows,
            "emergency_contacts": rows,
            "meta": {
                "skip": skip,
                "limit": limit,
                "count": len(rows),
                "source": self.source_label,
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_emergency_contacts_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_emergency_contacts_csv(rows)


# register on import
register_handler(EmergencyContactsHandler())
