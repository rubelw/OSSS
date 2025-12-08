# src/OSSS/ai/langchain/agents/student_info_table.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from collections import Counter
from datetime import date
import logging

import httpx
from pydantic import BaseModel, Field

from OSSS.ai.agents.query_data.handlers.students_handler import (
    _fetch_students_and_persons,
    API_BASE,
)

logger = logging.getLogger("OSSS.ai.langchain.student_info_table")


# ---------------------------------------------------------------------------
# Filters schema (used by StructuredTool and by our code)
# ---------------------------------------------------------------------------

class StudentInfoFilters(BaseModel):
    """
    Filters that can be applied to the OSSS student list.
    All fields are optional; when omitted, that filter is not applied.

    These fields are exposed to the LLM via the tool schema, so it can
    directly populate them from natural language like:

      - "show male students"
      - "students with last name beginning with 'S'"
      - "THIRD grade female students"
    """
    first_name_prefix: Optional[str] = Field(
        default=None,
        description=(
            "If provided, only include students whose FIRST name starts with this "
            "prefix (case-insensitive). Example: 'Sa' for 'Sarah', 'Sam'."
        ),
    )
    last_name_prefix: Optional[str] = Field(
        default=None,
        description=(
            "If provided, only include students whose LAST name starts with this "
            "prefix (case-insensitive). Example: 'S' for 'Smith', 'Saunders'."
        ),
    )
    genders: Optional[List[str]] = Field(
        default=None,
        description=(
            "If provided, only include students whose gender is in this list. "
            "Typical values: ['MALE'], ['FEMALE'], or ['OTHER']."
        ),
    )
    grade_levels: Optional[List[str]] = Field(
        default=None,
        description=(
            "If provided, only include students whose grade-level label is in this "
            "list (e.g. ['THIRD'], ['PREK'], ['FIRST']). "
            "Use UPPERCASE labels when possible."
        ),
    )

# in student_info_table.py (helper)
async def run_student_info_table_markdown_only(
    *,
    filters: Optional[StudentInfoFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> str:
    result = await run_student_info_table_structured(
        filters=filters,
        session_id=session_id,
        skip=skip,
        limit=limit,
    )
    # result["reply"] is your full markdown summary/table text
    return result["reply"]


# ---------------------------------------------------------------------------
# Grade-level index from enrollments + grade_levels
# ---------------------------------------------------------------------------

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
        label = gl.get("code") or gl.get("name") or gl.get("grade_name") or "UNKNOWN"
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
            e for e in enr_list
            if (e.get("status") or "").lower() == "active"
        ]
        candidates = active or enr_list

        def _key(e: Dict[str, Any]) -> date:
            d = _parse_date(e.get("entry_date"))
            return d or date.min

        try:
            chosen = max(candidates, key=_key)
        except ValueError:
            continue

        gid = chosen.get("grade_level_id")
        label = grade_label_by_id.get(gid, "UNKNOWN")
        student_grade[sid] = label

    logger.info(
        "Built student_grade_index for %d students using %d enrollments and %d grade_levels",
        len(student_grade),
        len(enrollments),
        len(grade_levels),
    )
    return student_grade


# ---------------------------------------------------------------------------
# Internal helper: build full table rows (no filtering)
# ---------------------------------------------------------------------------

async def _build_student_rows(skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    """
    Fetch students + persons + grade-level index and build a unified row list.

    Each row includes:

        person_id, first_name, middle_name, last_name, dob,
        email, phone, gender,
        person_created_at, person_updated_at,
        student_id, student_number, graduation_year,
        student_created_at, student_updated_at,
        grade_level
    """
    data = await _fetch_students_and_persons(skip=skip, limit=limit)
    students: List[Dict[str, Any]] = data.get("students", [])
    persons: List[Dict[str, Any]] = data.get("persons", [])

    persons_by_id = {p["id"]: p for p in persons}
    student_grade_index = await _build_student_grade_index(skip=skip, limit=limit)

    rows: List[Dict[str, Any]] = []

    for s in students:
        person = persons_by_id.get(s.get("person_id") or {})

        first_name = (person or {}).get("first_name") or ""
        middle_name = (person or {}).get("middle_name") or ""
        last_name = (person or {}).get("last_name") or ""

        gender = (person or {}).get("gender") or s.get("gender") or "UNKNOWN"

        grade = (
            student_grade_index.get(s.get("id") or "")
            or s.get("grade_level")
            or s.get("grade_level_name")
            or s.get("grade")
            or "UNKNOWN"
        )

        rows.append(
            {
                "person_id": (person or {}).get("id"),
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
                "dob": (person or {}).get("dob"),
                "email": (person or {}).get("email"),
                "phone": (person or {}).get("phone"),
                "gender": gender,
                "person_created_at": (person or {}).get("created_at"),
                "person_updated_at": (person or {}).get("updated_at"),
                "student_id": s.get("id"),
                "student_number": s.get("student_number"),
                "graduation_year": s.get("graduation_year"),
                "student_created_at": s.get("created_at"),
                "student_updated_at": s.get("updated_at"),
                "grade_level": grade,
            }
        )

    return {
        "rows": rows,
        "students": students,
        "persons": persons,
        "student_grade_index": student_grade_index,
    }


# ---------------------------------------------------------------------------
# Filtering helper
# ---------------------------------------------------------------------------

def _apply_filters(
    rows: List[Dict[str, Any]],
    filters: Optional[StudentInfoFilters],
) -> List[Dict[str, Any]]:
    """Return only rows that pass all active filters."""
    if not filters:
        return rows

    logger.info("[student_info_table] Applying filters: %s", filters.model_dump())

    fn_pref = (filters.first_name_prefix or "").lower()
    ln_pref = (filters.last_name_prefix or "").lower()
    allowed_genders = {g.upper() for g in (filters.genders or [])}
    allowed_grades = {g.upper() for g in (filters.grade_levels or [])}

    def _keep(r: Dict[str, Any]) -> bool:
        fn = (r.get("first_name") or "").lower()
        ln = (r.get("last_name") or "").lower()
        gend = (r.get("gender") or "").upper()
        grade = (r.get("grade_level") or "").upper()

        if fn_pref and not fn.startswith(fn_pref):
            return False
        if ln_pref and not ln.startswith(ln_pref):
            return False
        if allowed_genders and gend not in allowed_genders:
            return False
        if allowed_grades and grade not in allowed_grades:
            return False
        return True

    filtered = [r for r in rows if _keep(r)]
    return filtered


# ---------------------------------------------------------------------------
# Public API 1: legacy unstructured function (no filters)
# ---------------------------------------------------------------------------

async def run_student_info_table(*, message: str, session_id: str) -> Dict[str, Any]:
    """
    Legacy / unstructured version (kept for backward compatibility).
    Ignores `message` content; returns ALL students.
    """
    built = await _build_student_rows(skip=0, limit=100)
    rows = built["rows"]
    students = built["students"]
    persons = built["persons"]
    student_grade_index = built["student_grade_index"]

    filtered_rows = rows  # no filters here

    by_grade = Counter()
    by_gender = Counter()

    for r in filtered_rows:
        by_grade[r["grade_level"]] += 1
        by_gender[r["gender"] or "UNKNOWN"] += 1

    # Markdown table (same format as structured version)
    header = (
        "| # | First | Middle | Last | DOB | Email | Phone | Gender | "
        "Person ID | Created At | Updated At | Student ID | Student Number | Graduation Year | Grade Level |"
    )
    sep = (
        "|---|-------|--------|------|-----|-------|-------|--------|"
        "-----------|-------------|-------------|------------|----------------|------------------|------------|"
    )
    table_lines = [header, sep]

    for idx, r in enumerate(filtered_rows[:50], start=1):
        table_lines.append(
            "| {i} | {fn} | {mn} | {ln} | {dob} | {email} | {phone} | {gender} | "
            "{pid} | {pcrt} | {pupd} | {sid} | {snum} | {gyear} | {grade} |".format(
                i=idx,
                fn=r.get("first_name") or "",
                mn=r.get("middle_name") or "",
                ln=r.get("last_name") or "",
                dob=r.get("dob") or "",
                email=r.get("email") or "",
                phone=r.get("phone") or "",
                gender=r.get("gender") or "",
                pid=r.get("person_id") or "",
                pcrt=r.get("person_created_at") or "",
                pupd=r.get("person_updated_at") or "",
                sid=r.get("student_id") or "",
                snum=r.get("student_number") or "",
                gyear=r.get("graduation_year") or "",
                grade=r.get("grade_level") or "",
            )
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
            f"I found {len(filtered_rows)} students in the live OSSS backend.",
            "",
            *grade_lines,
            "",
            *gender_lines,
            "",
            "Sample (first 50 students):",
            "",
            *table_lines,
        ]
    )

    return {
        "reply": reply,
        "raw_students": students,
        "raw_persons": persons,
        "student_grade_index": student_grade_index,
        "filtered_rows": filtered_rows,
    }


# ---------------------------------------------------------------------------
# Public API 2: structured version used by the LangChain tool
# ---------------------------------------------------------------------------

async def run_student_info_table_structured(
    *,
    filters: Optional[StudentInfoFilters],
    session_id: str,
    skip: int = 0,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Structured version for the LangChain tool.
    Applies the given filters, then computes summary + sample table.

    This is what `student_info_table_tool` should call.
    """
    logger.info(
        "[student_info_table] run_student_info_table_structured called with filters=%s",
        filters.model_dump() if filters else None,
    )

    built = await _build_student_rows(skip=skip, limit=limit)
    rows = built["rows"]
    students = built["students"]
    persons = built["persons"]
    student_grade_index = built["student_grade_index"]

    filtered_rows = _apply_filters(rows, filters)

    by_grade = Counter()
    by_gender = Counter()

    for r in filtered_rows:
        by_grade[r["grade_level"]] += 1
        by_gender[r["gender"] or "UNKNOWN"] += 1

    header = (
        "| # | First | Middle | Last | DOB | Email | Phone | Gender | "
        "Person ID | Created At | Updated At | Student ID | Student Number | Graduation Year | Grade Level |"
    )
    sep = (
        "|---|-------|--------|------|-----|-------|-------|--------|"
        "-----------|-------------|-------------|------------|----------------|------------------|------------|"
    )
    table_lines = [header, sep]

    for idx, r in enumerate(filtered_rows[:50], start=1):
        table_lines.append(
            "| {i} | {fn} | {mn} | {ln} | {dob} | {email} | {phone} | {gender} | "
            "{pid} | {pcrt} | {pupd} | {sid} | {snum} | {gyear} | {grade} |".format(
                i=idx,
                fn=r.get("first_name") or "",
                mn=r.get("middle_name") or "",
                ln=r.get("last_name") or "",
                dob=r.get("dob") or "",
                email=r.get("email") or "",
                phone=r.get("phone") or "",
                gender=r.get("gender") or "",
                pid=r.get("person_id") or "",
                pcrt=r.get("person_created_at") or "",
                pupd=r.get("person_updated_at") or "",
                sid=r.get("student_id") or "",
                snum=r.get("student_number") or "",
                gyear=r.get("graduation_year") or "",
                grade=r.get("grade_level") or "",
            )
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
            f"I found {len(filtered_rows)} students in the live OSSS backend after applying filters.",
            "",
            *grade_lines,
            "",
            *gender_lines,
            "",
            "Sample (first 50 matching students):",
            "",
            *table_lines,
        ]
    )

    return {
        "reply": reply,
        "raw_students": students,
        "raw_persons": persons,
        "student_grade_index": student_grade_index,
        "filtered_rows": filtered_rows,
        "filters": filters.model_dump() if filters else None,
    }
