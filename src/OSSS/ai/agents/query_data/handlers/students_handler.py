# OSSS/ai/agents/query_data/handlers/students_handler.py
from __future__ import annotations

from typing import Any, Dict, List
import csv
import httpx
import io
import logging

from OSSS.ai.agents.base import AgentContext
from OSSS.ai.agents.query_data.query_data_registry import (
    QueryHandler,
    FetchResult,
    register_handler,
)

logger = logging.getLogger("OSSS.ai.agents.query_data.students")

API_BASE = "http://host.containers.internal:8081"


# ---------------------------------------------------------------------------
# Low-level fetch + combine
# ---------------------------------------------------------------------------


async def _fetch_students_and_persons(
    *, skip: int = 0, limit: int = 100
) -> Dict[str, List[Dict[str, Any]]]:
    students_url = f"{API_BASE}/api/students"
    persons_url = f"{API_BASE}/api/persons"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            students_resp = await client.get(students_url, params=params)
            students_resp.raise_for_status()
            students: List[Dict[str, Any]] = students_resp.json()

            persons_resp = await client.get(persons_url, params=params)
            persons_resp.raise_for_status()
            persons: List[Dict[str, Any]] = persons_resp.json()
    except Exception as e:
        logger.exception("Error calling students/persons API")
        # Keep it simple here; the agent will catch and surface the error
        raise RuntimeError(f"Error querying students/persons API: {e}") from e

    return {"students": students, "persons": persons}


def _combine_students_and_persons(
    students: List[Dict[str, Any]],
    persons: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
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


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _build_student_markdown_table(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return "No students were found in the system."

    header = (
        "| # | First | Middle | Last | DOB | Email | Phone | Gender | "
        "Person ID | Created At | Updated At | "
        "Student ID | Student Number | Graduation Year |\n"
        "|---|-------|--------|------|-----|-------|-------|--------|"
        "-----------|-------------|-------------|"
        "------------|----------------|----------------|\n"
    )

    lines: List[str] = []
    for idx, r in enumerate(rows, start=1):
        lines.append(
            f"| {idx} | "
            f"{r.get('first_name', '')} | "
            f"{r.get('middle_name', '')} | "
            f"{r.get('last_name', '')} | "
            f"{r.get('dob', '')} | "
            f"{r.get('email', '')} | "
            f"{r.get('phone', '')} | "
            f"{r.get('gender', '')} | "
            f"{r.get('person_id', '')} | "
            f"{r.get('person_created_at', '')} | "
            f"{r.get('person_updated_at', '')} | "
            f"{r.get('student_id', '')} | "
            f"{r.get('student_number', '')} | "
            f"{r.get('graduation_year', '')} |"
        )

    return header + "\n".join(lines)


def _build_student_csv(rows: List[Dict[str, Any]]) -> str:
    if not rows:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Handler implementation
# ---------------------------------------------------------------------------


class StudentsHandler(QueryHandler):
    mode = "students"
    keywords = [
        "student",
        "students",
        "roster",
        "enrollment",
        "class list",
    ]
    source_label = "your DCG OSSS demo student/person service"

    async def fetch(
        self, ctx: AgentContext, skip: int, limit: int
    ) -> FetchResult:
        payload = await _fetch_students_and_persons(skip=skip, limit=limit)
        students = payload["students"]
        persons = payload["persons"]
        combined_rows = _combine_students_and_persons(students, persons)

        return {
            "rows": combined_rows,
            "students": students,
            "persons": persons,
            "combined_rows": combined_rows,
        }

    def to_markdown(self, rows: List[Dict[str, Any]]) -> str:
        return _build_student_markdown_table(rows)

    def to_csv(self, rows: List[Dict[str, Any]]) -> str:
        return _build_student_csv(rows)


# register on import
register_handler(StudentsHandler())
