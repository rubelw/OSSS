from __future__ import annotations

import logging
from typing import Any, Dict, List
import httpx
import csv
import io

from OSSS.ai.agents import register_agent
from OSSS.ai.agents.base import AgentContext, AgentResult

logger = logging.getLogger("OSSS.ai.agents.query_data.agent")

API_BASE = "http://host.containers.internal:8081"


# ---------------------------------------------------------------------------
# Data / tool layer: pure functions over the external "tables" (APIs)
# ---------------------------------------------------------------------------


class QueryDataError(Exception):
    """Raised when querying the students/persons APIs fails."""

    def __init__(self, message: str, *, students_url: str, persons_url: str) -> None:
        super().__init__(message)
        self.students_url = students_url
        self.persons_url = persons_url


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
    # Index persons by id
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
                # person fields (all of them)
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


async def query_data_tool(
    *, skip: int = 0, limit: int = 100
) -> Dict[str, Any]:
    """
    High-level data/tool function that the AI agent calls.

    Responsibilities:
      - Calls the underlying APIs
      - Combines student and person records
      - Returns structured data (no formatting, no LLM)
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
# Formatting helpers (still "dumb" utilities, not agents)
# ---------------------------------------------------------------------------


def _build_markdown_table(rows: List[Dict[str, Any]]) -> str:
    """Return student/person combined rows as a markdown table."""
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

    lines = []
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


def _build_csv(rows: List[Dict[str, Any]]) -> str:
    """Return CSV string containing all combined fields."""
    if not rows:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


# ---------------------------------------------------------------------------
# Thin AI agent layer: delegates all data work to query_data_tool()
# ---------------------------------------------------------------------------


@register_agent("query_data")
class QueryDataAgent:
    async def run(self, ctx: AgentContext) -> AgentResult:
        # In the future we could read skip/limit or filters from ctx,
        # but for now we preserve the old behavior.
        skip = 0
        limit = 100

        try:
            data = await query_data_tool(skip=skip, limit=limit)
        except QueryDataError as e:
            # Agent just translates tool error into router-friendly AgentResult
            logger.exception("query_data_tool failed")
            return AgentResult(
                answer_text=(
                    "I attempted to query the students and persons APIs but "
                    "encountered an error.\n\n"
                    f"Students URL: {e.students_url}\nPersons URL: {e.persons_url}"
                ),
                status="error",
                intent="query_data",
                agent_id="query_data",
                agent_name="QueryDataAgent",
                data={
                    "agent_debug_information": {
                        "phase": "query_data",
                        "error": str(e),
                        "students_url": e.students_url,
                        "persons_url": e.persons_url,
                    }
                },
            )

        students: List[Dict[str, Any]] = data["students"]
        persons: List[Dict[str, Any]] = data["persons"]
        combined_rows: List[Dict[str, Any]] = data["combined_rows"]

        markdown_table = _build_markdown_table(combined_rows)
        csv_data = _build_csv(combined_rows)

        debug_info = {
            "phase": "query_data",
            "student_count": len(students),
            "person_count": len(persons),
            "combined_count": len(combined_rows),
            "students": students,
            "persons": persons,
            "combined": combined_rows,
            # 🔑 CSV is here
            "csv": csv_data,
            "csv_filename": "students_export.csv",
        }

        return AgentResult(
            # What shows up in the chat body
            answer_text=markdown_table,
            status="ok",
            # 🔑 these drive the footer in your UI
            intent="query_data",
            agent_id="query_data",
            agent_name="QueryDataAgent",
            # 🔑 this is what router_agent surfaces as `agent_debug_information`
            data={"agent_debug_information": debug_info},
        )
