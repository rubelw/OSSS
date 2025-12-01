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

logger = logging.getLogger("OSSS.ai.agents.query_data.incident_participants")

API_BASE = "http://host.containers.internal:8081"


# ----------------------------------------------------------------------
# FETCH INCIDENT PARTICIPANTS
# ----------------------------------------------------------------------
async def _fetch_incident_participants(skip: int = 0, limit: int = 300) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/incident_participants"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise QueryDataError(
            f"Error querying incident_participants API: {e}",
            incident_participants_url=url
        ) from e


# ----------------------------------------------------------------------
# FETCH INCIDENTS
# ----------------------------------------------------------------------
async def _fetch_incidents(skip: int = 0, limit: int = 300) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/incidents"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise QueryDataError(
            f"Error querying incidents API: {e}",
            incidents_url=url
        ) from e


# ----------------------------------------------------------------------
# FETCH STUDENTS
# ----------------------------------------------------------------------
async def _fetch_students(skip: int = 0, limit: int = 1000) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/students"
    params = {"skip": skip, "limit": min(limit, 1000)}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise QueryDataError(
            f"Error querying students API: {e}",
            students_url=url
        ) from e


# ----------------------------------------------------------------------
# FETCH PERSONS
# ----------------------------------------------------------------------
async def _fetch_persons(skip: int = 0, limit: int = 1000) -> List[Dict[str, Any]]:
    url = f"{API_BASE}/api/persons"
    params = {"skip": skip, "limit": min(limit, 1000)}

    try:
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise QueryDataError(
            f"Error querying persons API: {e}",
            persons_url=url
        ) from e


# ----------------------------------------------------------------------
# MARKDOWN WITH GROUPING BY INCIDENT
# ----------------------------------------------------------------------
def _build_markdown(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No incident participant records were found."

    grouped: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)

    for r in rows:
        grouped[r["incident_id"]].append(r)

    out = []

    for incident_id, items in grouped.items():
        inc = items[0]

        # incident details
        title = inc.get("incident_title", "Unknown Incident")
        date = inc.get("incident_date", "")
        location = inc.get("incident_location", "")

        out.append(f"## 🚨 Incident: {title}")
        out.append(f"**Incident ID:** {incident_id}")
        if date:
            out.append(f"**Date:** {date}")
        if location:
            out.append(f"**Location:** {location}")
        out.append("")

        # participants
        out.append("### Participants:\n")

        for p in items:
            name = f"{p.get('first_name','')} {p.get('last_name','')}".strip()
            role = p.get("role", "")
            injury = p.get("injury", "")
            notes = p.get("notes", "")

            out.append(f"#### 🧑‍🎓 {name}")
            out.append(f"- **Role:** {role}")
            if injury:
                out.append(f"- **Injury:** {injury}")
            if notes:
                out.append(f"- **Notes:** {notes}")
            out.append("")

        out.append("\n---\n")

    return "\n".join(out)


# ----------------------------------------------------------------------
# CSV EXPORT
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
# MAIN HANDLER CLASS
# ----------------------------------------------------------------------
class IncidentParticipantsHandler(QueryHandler):
    mode = "incident_participants"
    keywords = [
        "incident participants",
        "incident_participants",
        "discipline participants",
        "behavior participants",
    ]
    source_label = "DCG OSSS incident & discipline records"

    async def fetch(self, ctx: AgentContext, skip: int, limit: int) -> FetchResult:

        # 1. Fetch all required tables
        participants = await _fetch_incident_participants(skip, limit)
        incidents = await _fetch_incidents()
        students = await _fetch_students()
        persons = await _fetch_persons()

        # 2. Build lookups
        incident_lookup = {i["id"]: i for i in incidents}
        student_lookup = {s["id"]: s for s in students}
        person_lookup = {p["id"]: p for p in persons}

        # 3. Merge all data
        combined = []

        for p in participants:
            sid = p.get("student_id")
            incident_id = p.get("incident_id")

            student = student_lookup.get(sid, {})
            person = person_lookup.get(student.get("person_id"))
            incident = incident_lookup.get(incident_id, {})

            combined.append({
                **p,

                # student
                "student_number": student.get("student_number"),
                "graduation_year": student.get("graduation_year"),

                # person
                "first_name": person.get("first_name") if person else None,
                "last_name": person.get("last_name") if person else None,
                "dob": person.get("dob") if person else None,

                # incident info
                "incident_title": incident.get("title"),
                "incident_date": incident.get("date"),
                "incident_location": incident.get("location"),
            })

        return {
            "rows": combined,
            "participants": participants,
            "incidents": incidents,
            "students_count": len(students),
            "persons_count": len(persons),
            "combined_rows": combined,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_markdown(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_csv(rows)


register_handler(IncidentParticipantsHandler())
