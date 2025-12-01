from __future__ import annotations

from typing import Any, Dict, List, DefaultDict
import httpx
import csv
import io
import logging
from collections import defaultdict

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)
from OSSS.ai.agents.query_data.query_data_errors import QueryDataError

logger = logging.getLogger("OSSS.ai.agents.query_data.immunization_records")

API_BASE = "http://host.containers.internal:8081"


# ----------------------------------------------------------------------
# FETCH IMMUNIZATION RECORDS
# ----------------------------------------------------------------------
async def _fetch_immunization_records(skip: int = 0, limit: int = 500) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/immunization_records"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise QueryDataError(
            f"Error querying immunization_records API: {e}",
            immunization_records_url=url
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected payload type: {type(data)!r}",
            immunization_records_url=url
        )

    return data


# ----------------------------------------------------------------------
# FETCH STUDENTS
# id, person_id, student_number, graduation_year
# ----------------------------------------------------------------------
async def _fetch_students(skip: int = 0, limit: int = 1000) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/students"
    params = {"skip": skip, "limit": min(limit, 1000)}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise QueryDataError(
            f"Error querying students API: {e}",
            students_url=url
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected students payload type: {type(data)!r}",
            students_url=url
        )

    return data


# ----------------------------------------------------------------------
# FETCH PERSONS
# id, first_name, last_name, dob, email, phone, gender, created_at, ...
# ----------------------------------------------------------------------
async def _fetch_persons(skip: int = 0, limit: int = 1000) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/persons"
    params = {"skip": skip, "limit": min(limit, 1000)}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise QueryDataError(
            f"Error querying persons API: {e}",
            persons_url=url
        ) from e

    if not isinstance(data, list):
        raise QueryDataError(
            f"Unexpected persons payload type: {type(data)!r}",
            persons_url=url
        )

    return data


# ----------------------------------------------------------------------
# BUILD MARKDOWN (grouped by student)
# ----------------------------------------------------------------------
def _build_markdown(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No student immunization records were found."

    grouped: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[r["student_id"]].append(r)

    out = []

    for student_id, items in grouped.items():
        first = items[0].get("first_name", "")
        last = items[0].get("last_name", "")
        student_num = items[0].get("student_number", "")
        dob = items[0].get("dob", "")

        out.append(f"## 🧑‍🎓 {first} {last} ({student_num})")
        out.append(f"**Student ID:** {student_id}  ")
        out.append(f"**DOB:** {dob}\n")

        for r in items:
            out.append(
                f"- **{r.get('immunization_name','')}** — "
                f"*{r.get('status','')}* ({r.get('date','')})"
            )

        out.append("")  # spacing

    return "\n".join(out)


# ----------------------------------------------------------------------
# BUILD CSV
# ----------------------------------------------------------------------
def _build_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


# ----------------------------------------------------------------------
# HANDLER CLASS
# ----------------------------------------------------------------------
class ImmunizationRecordsHandler(QueryHandler):
    mode = "immunization_records"
    keywords = [
        "immunization records",
        "student immunizations",
        "vaccination records",
        "shots",
        "vaccine records",
    ]
    source_label = "DCG OSSS student immunization records"

    async def fetch(self, ctx: AgentContext, skip: int, limit: int) -> FetchResult:

        # Fetch all three datasets
        records = await _fetch_immunization_records(skip, limit)
        students = await _fetch_students()
        persons = await _fetch_persons()

        # Build lookups
        student_lookup = {s["id"]: s for s in students}
        person_lookup = {p["id"]: p for p in persons}

        # Merge → student → person
        combined = []
        for r in records:
            sid = r["student_id"]
            student = student_lookup.get(sid, {})
            person = person_lookup.get(student.get("person_id"))

            combined.append({
                **r,

                # student information
                "student_number": student.get("student_number"),
                "graduation_year": student.get("graduation_year"),

                # person information
                "first_name": person.get("first_name") if person else None,
                "last_name": person.get("last_name") if person else None,
                "dob": person.get("dob") if person else None,
                "email": person.get("email") if person else None,
            })

        return {
            "rows": combined,
            "records": records,
            "students_count": len(students),
            "persons_count": len(persons),
            "combined_rows": combined,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_markdown(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_csv(rows)


# Register handler on import
register_handler(ImmunizationRecordsHandler())
