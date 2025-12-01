from __future__ import annotations

import httpx
import csv
import io
import logging
from typing import Any, Dict, List

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.person_addresss")

API_BASE = "http://host.containers.internal:8081"


# -----------------------------
# Fetch helpers
# -----------------------------

async def _fetch_person_addresss(skip: int, limit: int) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/person_addresss"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Error calling person_addresss API")
        raise QueryDataError(f"Error querying person_addresss API: {e}") from e


async def _fetch_persons(limit: int = 5000) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/persons"
    params = {"skip": 0, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Error calling persons API")
        raise QueryDataError(f"Error querying persons API: {e}") from e


async def _fetch_addresss(limit: int = 5000) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/addresss"
    params = {"skip": 0, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.exception("Error calling addresss API")
        raise QueryDataError(f"Error querying addresss API: {e}") from e


# -----------------------------
# Join person + address + join
# -----------------------------

def _join_person_addresss(
    pa_rows: List[Dict[str, Any]],
    persons: List[Dict[str, Any]],
    addresses: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    person_map = {p["id"]: p for p in persons}
    address_map = {a["id"]: a for a in addresses}

    joined = []

    for pa in pa_rows:
        person = person_map.get(pa["person_id"])
        addr = address_map.get(pa["address_id"])

        joined.append({
            "person_addresss_id": pa.get("id"),
            "is_primary": pa.get("is_primary"),
            "pa_created_at": pa.get("created_at"),
            "pa_updated_at": pa.get("updated_at"),

            # Person info
            "person_id": pa.get("person_id"),
            "first_name": person.get("first_name") if person else None,
            "last_name": person.get("last_name") if person else None,
            "email": person.get("email") if person else None,

            # Address info
            "address_id": pa.get("address_id"),
            "line1": addr.get("line1") if addr else None,
            "line2": addr.get("line2") if addr else None,
            "city": addr.get("city") if addr else None,
            "state": addr.get("state") if addr else None,
            "postal_code": addr.get("postal_code") if addr else None,
            "country": addr.get("country") if addr else None,
            "address_created_at": addr.get("created_at") if addr else None,
            "address_updated_at": addr.get("updated_at") if addr else None,
        })

    return joined


# -----------------------------
# Markdown rendering
# -----------------------------

def _build_person_addresss_markdown(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No person address records were found in the system."

    fieldnames = list(rows[0].keys())
    header = "| # | " + " | ".join(fieldnames) + " |\n"
    sep = "|---|" + "|".join(["---"] * len(fieldnames)) + "|\n"

    lines = []
    for idx, row in enumerate(rows, start=1):
        values = [str(row.get(fn, "")) for fn in fieldnames]
        lines.append(f"| {idx} | " + " | ".join(values) + " |")

    return header + sep + "\n".join(lines)


# -----------------------------
# CSV export
# -----------------------------

def _build_person_addresss_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""
    fieldnames = list(rows[0].keys())
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# -----------------------------
# Handler
# -----------------------------

class PersonAddresssHandler(QueryHandler):
    mode = "person_addresss"
    keywords = [
        "person addresses",
        "person_addresss",
        "show person addresses",
        "address assignments",
        "student addresses",
    ]
    source_label = "your DCG OSSS data service (person_addresss)"

    async def fetch(self, ctx: AgentContext, skip: int, limit: int) -> FetchResult:

        pa_rows = await _fetch_person_addresss(skip, limit)
        persons = await _fetch_persons()
        addresses = await _fetch_addresss()

        combined = _join_person_addresss(pa_rows, persons, addresses)

        return {
            "rows": combined,
            "person_addresss": pa_rows,
            "persons": persons,
            "addresses": addresses,
            "combined": combined,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_person_addresss_markdown(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_person_addresss_csv(rows)


register_handler(PersonAddresssHandler())
