# src/OSSS/ai/langchain/agents/student_info_table.py
from __future__ import annotations

from typing import Any, Dict, List
from collections import Counter
from datetime import date
import logging

import httpx

from OSSS.ai.agents.query_data.handlers.students_handler import (
    _fetch_students_and_persons,
    API_BASE,
)

logger = logging.getLogger("OSSS.ai.langchain.student_info_table")


async def _build_student_grade_index(
    *, skip: int = 0, limit: int = 100
) -> Dict[str, str]:
    """
    Build a mapping of student_id -> grade level label using:
      - student_school_enrollments.grade_level_id
      - grade_levels (code/name)

    Strategy:
      - Fetch all enrollments and grade_levels from the OSSS API.
      - For each student_id, pick the most recent *active* enrollment if any,
        otherwise the most recent enrollment by entry_date.
      - Map grade_level_id to a human-friendly label (code or name).
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1) Pull enrollments
            enr_resp = await client.get(
                f"{API_BASE}/api/student_school_enrollments",
                params={"skip": skip, "limit": limit},
            )
            enr_resp.raise_for_status()
            enrollments = enr_resp.json()

            # 2) Pull grade levels
            gl_resp = await client.get(
                f"{API_BASE}/api/grade_levels",
                params={"skip": 0, "limit": 100},
            )
            gl_resp.raise_for_status()
            grade_levels = gl_resp.json()

    except httpx.HTTPError as e:
        logger.error(
            "Error fetching enrollments/grade_levels from OSSS API: %s", e, exc_info=True
        )
        return {}

    # Map grade_level_id -> label we want to show (code preferred, fallback to name)
    grade_label_by_id: Dict[str, str] = {}
    for gl in grade_levels:
        gid = gl.get("id")
        if not gid:
            continue
        label = gl.get("code") or gl.get("name") or gl.get("grade_name") or "Unknown"
        grade_label_by_id[gid] = label

    # Group enrollments by student_id
    by_student: Dict[str, List[Dict[str, Any]]] = {}
    for enr in enrollments:
        sid = enr.get("student_id")
        if not sid:
            continue
        by_student.setdefault(sid, []).append(enr)

    def _parse_date(val: Any) -> date | None:
        if not val:
            return None
        if isinstance(val, date):
            return val
        # assume ISO8601 string like "2024-08-23" or "2024-08-23T00:00:00Z"
        text = str(val)
        try:
            return date.fromisoformat(text[:10])
        except Exception:
            return None

    student_grade: Dict[str, str] = {}

    for sid, enr_list in by_student.items():
        if not enr_list:
            continue

        # Prefer active enrollments
        active = [
            e
            for e in enr_list
            if (e.get("status") or "").lower() == "active"
        ]
        candidates = active or enr_list

        # Pick the one with the latest entry_date
        def _key(e: Dict[str, Any]) -> date:
            d = _parse_date(e.get("entry_date"))
            return d or date.min

        try:
            chosen = max(candidates, key=_key)
        except ValueError:
            # no valid candidates
            continue

        gid = chosen.get("grade_level_id")
        label = grade_label_by_id.get(gid)
        if label:
            student_grade[sid] = label

    logger.info(
        "Built student_grade_index for %d students using %d enrollments and %d grade_levels",
        len(student_grade),
        len(enrollments),
        len(grade_levels),
    )
    return student_grade


async def run_student_info_table(*, message: str, session_id: str) -> Dict[str, Any]:
    """
    LangChain-style agent function for summarizing students.

    This reuses the query_data helper `_fetch_students_and_persons` so
    we don't duplicate backend-API logic, and additionally pulls
    grade levels from student_school_enrollments + grade_levels.
    """

    # 1) Pull students + persons from OSSS backend
    data = await _fetch_students_and_persons(skip=0, limit=100)
    students: List[Dict[str, Any]] = data.get("students", [])
    persons: List[Dict[str, Any]] = data.get("persons", [])

    persons_by_id = {p["id"]: p for p in persons}

    # 2) Build student_id -> grade_level_label index from enrollments
    student_grade_index = await _build_student_grade_index(skip=0, limit=100)

    by_grade = Counter()
    by_gender = Counter()
    rows: List[Dict[str, Any]] = []

    for s in students:
        person = persons_by_id.get(s.get("person_id") or "")

        first_name = (person or {}).get("first_name") or ""
        last_name = (person or {}).get("last_name") or ""

        # Gender still primarily from person; fallback to student or Unknown
        gender = (person or {}).get("gender") or s.get("gender") or "Unknown"

        # Grade level priority:
        #   1) From student_school_enrollments/grade_levels
        #   2) From student record fields
        grade = (
            student_grade_index.get(s.get("id") or "")
            or s.get("grade_level")
            or s.get("grade_level_name")
            or s.get("grade")
            or "Unknown"
        )

        by_grade[grade] += 1
        by_gender[gender or "Unknown"] += 1

        rows.append(
            {
                "id": s.get("id"),
                "student_number": s.get("student_number"),
                "first_name": first_name,
                "last_name": last_name,
                "grade_level": grade,
                "gender": gender,
            }
        )

    # 3) Build markdown table and summary
    header = "id | student_number | first_name | last_name | grade_level | gender"
    sep = "--- | --- | --- | --- | --- | ---"
    table_lines = [header, sep]

    for r in rows[:20]:  # truncate for display
        table_lines.append(
            f"{r['id']} | {r['student_number']} | {r['first_name']} | "
            f"{r['last_name']} | {r['grade_level']} | {r['gender']}"
        )

    grade_lines = [
        "By grade level (top 10):",
        *[f"- {g}: {c} students" for g, c in by_grade.most_common(10)],
    ]
    gender_lines = [
        "By gender:",
        *[f"- {g}: {c} students" for g, c in by_gender.most_common()],
    ]

    reply = "\n".join(
        [
            f"I found {len(students)} students in the live OSSS backend.",
            "",
            *grade_lines,
            "",
            *gender_lines,
            "",
            "Sample of first 20 students:",
            "",
            *table_lines,
        ]
    )

    # The router only cares about `reply`, but we return extras for debugging
    return {
        "reply": reply,
        "raw_students": students,
        "raw_persons": persons,
        "student_grade_index": student_grade_index,
    }
