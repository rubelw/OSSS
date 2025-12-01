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

logger = logging.getLogger("OSSS.ai.agents.query_data.user_accounts")

API_BASE = "http://host.containers.internal:8081"


# ------------------------------------------------------------------------------
# Shared fetch helper
# ------------------------------------------------------------------------------

async def _fetch_json(url: str, params: Dict[str, Any] | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Error calling API: %s", url)
        # Keep QueryDataError simple so we don't hit unexpected kwargs issues
        raise QueryDataError(f"Error calling API {url}: {e}") from e


# ------------------------------------------------------------------------------
# Table-specific fetch helpers
# ------------------------------------------------------------------------------

async def _fetch_user_accounts(
    skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/user_accounts"
    data = await _fetch_json(url, {"skip": skip, "limit": limit})

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected user_accounts payload type: {type(data)!r}"
        )
    return data


async def _fetch_users() -> Dict[str, Dict[str, Any]]:
    """
    Load users keyed by id for enrichment.
    """
    url = f"{API_BASE}/api/users"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected users payload type: {type(data)!r}"
        )
    return {row["id"]: row for row in data if isinstance(row, dict) and "id" in row}


async def _fetch_persons() -> Dict[str, Dict[str, Any]]:
    """
    Load persons keyed by id for enrichment.
    """
    url = f"{API_BASE}/api/persons"
    data = await _fetch_json(url, {"skip": 0, "limit": 5000})
    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected persons payload type: {type(data)!r}"
        )
    return {row["id"]: row for row in data if isinstance(row, dict) and "id" in row}


# ------------------------------------------------------------------------------
# Markdown / CSV builders
# ------------------------------------------------------------------------------

def _build_user_accounts_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No user_accounts records were found in the system."

    fieldnames = list(rows[0].keys())
    if not fieldnames:
        return "No user_accounts records were found in the system."

    header = "| # | " + " | ".join(fieldnames) + " |\n"
    separator = "|---|" + "|".join(["---"] * len(fieldnames)) + "|\n"

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        row_vals = [str(r.get(f, "")) for f in fieldnames]
        lines.append(f"| {idx} | " + " | ".join(row_vals) + " |")

    return header + separator + "\n".join(lines)


def _build_user_accounts_csv(rows: List[Dict[str, Any]]) -> str:
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

class UserAccountsHandler(QueryHandler):
    mode = "user_accounts"
    keywords = [
        "user_accounts",
        "user accounts",
        "login accounts",
        "portal accounts",
        "osss accounts",
        "show user accounts",
    ]
    source_label = (
        "your DCG OSSS account services "
        "(user_accounts + users + persons)"
    )

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        # Base table
        account_rows = await _fetch_user_accounts(skip=skip, limit=limit)

        # Enrichment lookups
        try:
            users = await _fetch_users()
        except Exception:
            users = {}

        try:
            persons = await _fetch_persons()
        except Exception:
            persons = {}

        enriched: List[Dict[str, Any]] = []
        for row in account_rows:
            user = users.get(row.get("user_id"))
            person = None
            if isinstance(user, dict):
                person_id = user.get("person_id")
                if person_id:
                    person = persons.get(person_id)

            first_name = (
                person.get("first_name")
                if isinstance(person, dict)
                else None
            )
            last_name = (
                person.get("last_name")
                if isinstance(person, dict)
                else None
            )
            full_name = (
                f"{first_name} {last_name}".strip()
                if first_name or last_name
                else None
            )

            enriched.append(
                {
                    **row,
                    # From users table (if present)
                    "username": (
                        user.get("username")
                        if isinstance(user, dict)
                        else None
                    ),
                    "user_email": (
                        user.get("email")
                        if isinstance(user, dict)
                        else None
                    ),
                    # From persons table (if present)
                    "person_first_name": first_name,
                    "person_last_name": last_name,
                    "person_full_name": full_name,
                }
            )

        return {
            "rows": enriched,
            "user_accounts": enriched,
            "enrichment": {
                "users_loaded": len(users),
                "persons_loaded": len(persons),
            },
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_user_accounts_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_user_accounts_csv(rows)


# register on import
register_handler(UserAccountsHandler())
