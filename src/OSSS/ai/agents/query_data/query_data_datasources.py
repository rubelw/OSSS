from __future__ import annotations

import logging
from typing import Any, Dict, List

import httpx

logger = logging.getLogger("OSSS.ai.agents.query_data.datasources")

API_BASE = "http://host.containers.internal:8081"


class QueryDataError(Exception):
    """Raised when querying one of the external APIs fails."""

    def __init__(
        self,
        message: str,
        *,
        students_url: str | None = None,
        persons_url: str | None = None,
        scorecards_url: str | None = None,
        live_scorings_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.students_url = students_url
        self.persons_url = persons_url
        self.scorecards_url = scorecards_url
        self.live_scorings_url = live_scorings_url


# ---------------------------------------------------------------------------
# Students + Persons
# ---------------------------------------------------------------------------


async def _fetch_students_and_persons(
    *, skip: int = 0, limit: int = 100
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Low-level tool: call the external students and persons APIs
    and return the raw JSON payloads.
    """
    students_url = f"{API_BASE}/api/students"
    persons_url = f"{API_BASE}/api/persons"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Fetch students
            students_resp = await client.get(students_url, params=params)
            students_resp.raise_for_status()
            students: List[Dict[str, Any]] = students_resp.json()

            # Fetch persons
            persons_resp = await client.get(persons_url, params=params)
            persons_resp.raise_for_status()
            persons: List[Dict[str, Any]] = persons_resp.json()

    except Exception as e:
        logger.exception("Error calling students/persons API")
        raise QueryDataError(
            f"Error querying students/persons API: {e}",
            students_url=students_url,
            persons_url=persons_url,
        ) from e

    return {"students": students, "persons": persons}


def _combine_students_and_persons(
    students: List[Dict[str, Any]],
    persons: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Pure function: combine students + persons into a unified row list.
    """
    persons_by_id = {p["id"]: p for p in persons if "id" in p}

    combined_rows: List[Dict[str, Any]] = []
    for s in students:
        pid = s.get("person_id")
        if not pid:
            continue

        person = persons_by_id.get(pid)
        if not person:
            continue

        combined_rows.append(
            {
                # person fields
                "person_id": person.get("id"),
                "first_name": person.get("first_name"),
                "middle_name": person.get("middle_name"),
                "last_name": person.get("last_name"),
                "dob": person.get("dob"),
                "email": person.get("email"),
                "phone": person.get("phone"),
                "gender": person.get("gender"),
                "person_created_at": person.get("created_at"),
                "person_updated_at": person.get("updated_at"),
                # student fields
                "student_id": s.get("id"),
                "student_number": s.get("student_number"),
                "graduation_year": s.get("graduation_year"),
                "student_created_at": s.get("created_at"),
                "student_updated_at": s.get("updated_at"),
            }
        )

    return combined_rows


async def query_students_tool(
    *, skip: int = 0, limit: int = 100
) -> Dict[str, Any]:
    """
    High-level data/tool function for students/persons.

    Returns raw students, persons, and combined rows.
    """
    payload = await _fetch_students_and_persons(skip=skip, limit=limit)
    students = payload["students"]
    persons = payload["persons"]
    combined_rows = _combine_students_and_persons(students, persons)

    return {
        "students": students,
        "persons": persons,
        "combined_rows": combined_rows,
    }


# ---------------------------------------------------------------------------
# Scorecards
# ---------------------------------------------------------------------------


async def _fetch_scorecards(
    *, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Low-level tool: call the external scorecards API and return JSON payload.
    """
    scorecards_url = f"{API_BASE}/api/scorecards"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(scorecards_url, params=params)
            resp.raise_for_status()
            scorecards: List[Dict[str, Any]] = resp.json()
    except Exception as e:
        logger.exception("Error calling scorecards API")
        raise QueryDataError(
            f"Error querying scorecards API: {e}",
            scorecards_url=scorecards_url,
        ) from e

    return scorecards


async def query_scorecards_tool(
    *, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """
    High-level data/tool function for scorecards.

    Returns raw scorecards list.
    """
    return await _fetch_scorecards(skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# Live scoring
# ---------------------------------------------------------------------------


async def _fetch_live_scorings(
    *, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """Call the OSSS live_scorings endpoint."""
    url = f"{API_BASE}/api/live_scorings"
    params = {"skip": skip, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                raise QueryDataError(
                    f"Live scoring query failed with status={resp.status_code}",
                    live_scorings_url=url,
                )
            data = resp.json()
    except QueryDataError:
        raise
    except Exception as e:
        logger.exception("Error calling live_scorings API")
        raise QueryDataError(
            f"Error querying live_scorings API: {e}",
            live_scorings_url=url,
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected live_scorings payload type: {type(data)!r}",
            live_scorings_url=url,
        )
    return data


async def query_live_scorings_tool(
    *, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """Tool-like wrapper for fetching live scoring rows."""
    return await _fetch_live_scorings(skip=skip, limit=limit)
