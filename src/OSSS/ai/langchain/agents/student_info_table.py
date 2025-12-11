# src/OSSS/ai/langchain/agents/student_info_table.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from collections import Counter
from datetime import date
import logging

import httpx
from pydantic import BaseModel, Field

from OSSS.ai.agents.query_data.handlers.students_handler import (
    _fetch_students_and_persons,
    API_BASE,
)
from OSSS.ai.agents.query_data.query_data_registry import get_handler

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
      - "show inactive students"
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
    enrolled_only: bool | None = Field(
        default=None,
        description=(
            "If True, only include students whose most recent enrollment row has "
            "status of ENROLLED/ACTIVE. "
            "If False, only include students whose most recent enrollment row is "
            "NOT ENROLLED/ACTIVE (inactive/withdrawn/etc.). "
            "If None, do not filter on enrollment status."
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
# Helpers to get enrollments via QueryData handler
# ---------------------------------------------------------------------------


async def _fetch_student_school_enrollments(
    *,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch student_school_enrollments rows, preferring the QueryData handler.
    Falls back to direct HTTP if the handler is not registered.

    We expect each row to have at least:
      - student_id
      - grade_level_id (optional but recommended)
      - entry_date
      - status  (e.g. ENROLLED, ACTIVE, WITHDRAWN, INACTIVE, etc.)
    """
    handler = get_handler("student_school_enrollments")

    if handler is not None:
        logger.info(
            "[student_info_table] Using QueryData handler for student_school_enrollments "
            "(skip=%s, limit=%s)",
            skip,
            limit,
        )
        result = await handler.fetch(ctx=None, skip=skip, limit=limit)
        rows = result.get("rows") or result.get("student_school_enrollments") or []
        if not isinstance(rows, list):
            logger.error(
                "[student_info_table] student_school_enrollments handler returned "
                "non-list rows: %r",
                type(rows),
            )
            return []
        return rows

    # Fallback: direct HTTP to the OSSS API
    logger.warning(
        "[student_info_table] student_school_enrollments handler not found; "
        "falling back to direct HTTP call."
    )
    url = f"{API_BASE}/api/student_school_enrollments"
    params = {"skip": skip, "limit": limit}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.error(
            "Error fetching student_school_enrollments from OSSS API: %s",
            e,
            exc_info=True,
        )
        return []

    if not isinstance(data, list):
        logger.error(
            "Unexpected student_school_enrollments payload type via HTTP: %r",
            type(data),
        )
        return []

    return data


async def _fetch_grade_levels(
    *, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Fetch grade_levels directly from the OSSS API.
    (We don't currently have a dedicated QueryData handler for this.)
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            gl_resp = await client.get(
                f"{API_BASE}/api/grade_levels",
                params={"skip": skip, "limit": limit},
            )
            gl_resp.raise_for_status()
            grade_levels = gl_resp.json()
            if not isinstance(grade_levels, list):
                logger.error(
                    "Unexpected grade_levels payload type: %r", type(grade_levels)
                )
                return []
            return grade_levels
    except httpx.HTTPError as e:
        logger.error(
            "Error fetching grade_levels from OSSS API: %s", e, exc_info=True
        )
        return []


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


# ---------------------------------------------------------------------------
# Grade-level + enrollment index from enrollments + grade_levels
# ---------------------------------------------------------------------------


async def _build_student_grade_index(
    *, skip: int = 0, limit: int = 100
) -> Tuple[Dict[str, str], Dict[str, bool]]:
    """
    Build:
      - student_grade:  mapping of student_id -> grade level label using
          student_school_enrollments.grade_level_id + grade_levels (code/name)
      - student_enrolled: mapping of student_id -> is_enrolled (bool), where:

          latest := enrollment row with the greatest entry_date
          status_norm := latest.status uppercased (or "" if missing)
          is_enrolled := status_norm in {'ENROLLED', 'ACTIVE'}
    """
    enrollments = await _fetch_student_school_enrollments(skip=skip, limit=limit)
    grade_levels = await _fetch_grade_levels(skip=0, limit=100)

    logger.info(
        "[student_info_table] _build_student_grade_index: fetched %d enrollments, %d grade_levels",
        len(enrollments),
        len(grade_levels),
    )

    # Debug a small sample of enrollment statuses
    sample_enr = [
        {
            "student_id": e.get("student_id"),
            "status": e.get("status"),
            "entry_date": e.get("entry_date"),
            "grade_level_id": e.get("grade_level_id"),
        }
        for e in enrollments[:5]
    ]
    logger.debug(
        "[student_info_table] enrollment sample (first 5): %s",
        sample_enr,
    )

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

    student_grade: Dict[str, str] = {}
    student_enrolled: Dict[str, bool] = {}

    def _key(e: Dict[str, Any]) -> date:
        d = _parse_date(e.get("entry_date"))
        return d or date.min

    for sid, enr_list in by_student.items():
        if not enr_list:
            continue

        # Normalize status once
        for e in enr_list:
            status = e.get("status")
            if isinstance(status, str):
                e["_status_norm"] = status.strip().upper()
            else:
                e["_status_norm"] = ""

        # Latest enrollment by entry_date
        try:
            latest = max(enr_list, key=_key)
        except ValueError:
            # all invalid dates; skip this student
            continue

        latest_status = latest.get("_status_norm", "")
        is_enrolled = latest_status in {"ENROLLED", "ACTIVE"}

        gid = latest.get("grade_level_id")
        label = grade_label_by_id.get(gid, "UNKNOWN")

        student_enrolled[sid] = is_enrolled
        student_grade[sid] = label

    num_enrolled = sum(1 for v in student_enrolled.values() if v)
    num_not_enrolled = sum(1 for v in student_enrolled.values() if not v)

    logger.info(
        "Built student_grade_index for %d students using %d enrollments and %d grade_levels "
        "(currently enrolled=%d, inactive=%d)",
        len(student_grade),
        len(enrollments),
        len(grade_levels),
        num_enrolled,
        num_not_enrolled,
    )

    # Debug a small sample of the final index
    sample_idx = list(student_enrolled.items())[:10]
    logger.debug(
        "[student_info_table] student_enrolled index sample (first 10): %s",
        sample_idx,
    )

    return student_grade, student_enrolled


# ---------------------------------------------------------------------------
# Internal helper: build full table rows (no filtering)
# ---------------------------------------------------------------------------


async def _build_student_rows(skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    """
    Fetch students + persons + grade/enrollment index and build a unified row list.
    ...
    """
    data = await _fetch_students_and_persons(skip=skip, limit=limit)
    students: List[Dict[str, Any]] = data.get("students", [])
    persons: List[Dict[str, Any]] = data.get("persons", [])

    logger.info(
        "[student_info_table] _build_student_rows: fetched %d students and %d persons "
        "(skip=%d, limit=%d)",
        len(students),
        len(persons),
        skip,
        limit,
    )

    persons_by_id = {p["id"]: p for p in persons}
    student_grade_index, student_enrolled_index = await _build_student_grade_index(
        skip=skip, limit=limit
    )

    rows: List[Dict[str, Any]] = []

    for s in students:
        person = persons_by_id.get(s.get("person_id") or {})

        first_name = (person or {}).get("first_name") or ""
        middle_name = (person or {}).get("middle_name") or ""
        last_name = (person or {}).get("last_name") or ""

        gender = (person or {}).get("gender") or s.get("gender") or "UNKNOWN"

        student_id = s.get("id") or ""

        grade = (
            student_grade_index.get(student_id)
            or s.get("grade_level")
            or s.get("grade_level_name")
            or s.get("grade")
            or "UNKNOWN"
        )

        # is_enrolled is specifically based on the latest enrollment status
        is_enrolled = bool(student_enrolled_index.get(student_id, False))

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
                "student_id": student_id,
                "student_number": s.get("student_number"),
                "graduation_year": s.get("graduation_year"),
                "student_created_at": s.get("created_at"),
                "student_updated_at": s.get("updated_at"),
                "grade_level": grade,
                "is_enrolled": is_enrolled,
            }
        )

    total_rows = len(rows)
    enrolled_rows = sum(1 for r in rows if r.get("is_enrolled"))
    inactive_rows = total_rows - enrolled_rows

    logger.info(
        "[student_info_table] _build_student_rows: built %d unified rows "
        "(is_enrolled=True: %d, is_enrolled=False: %d)",
        total_rows,
        enrolled_rows,
        inactive_rows,
    )

    # small debug sample
    logger.debug(
        "[student_info_table] unified row sample (first 5): %s",
        [
            {
                "student_id": r.get("student_id"),
                "first_name": r.get("first_name"),
                "last_name": r.get("last_name"),
                "grade_level": r.get("grade_level"),
                "is_enrolled": r.get("is_enrolled"),
            }
            for r in rows[:5]
        ],
    )

    return {
        "rows": rows,
        "students": students,
        "persons": persons,
        "student_grade_index": student_grade_index,
        "student_enrolled_index": student_enrolled_index,
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
        logger.info(
            "[student_info_table] _apply_filters: no filters provided; returning %d rows",
            len(rows),
        )
        return rows

    logger.info("[student_info_table] Applying filters: %s", filters.model_dump())

    fn_pref = (filters.first_name_prefix or "").lower()
    ln_pref = (filters.last_name_prefix or "").lower()
    allowed_genders = {g.upper() for g in (filters.genders or [])}
    allowed_grades = {g.upper() for g in (filters.grade_levels or [])}
    enrolled_only = filters.enrolled_only

    total_rows = len(rows)
    total_enrolled = sum(1 for r in rows if r.get("is_enrolled"))
    total_inactive = total_rows - total_enrolled

    logger.info(
        "[student_info_table] _apply_filters: starting with %d rows "
        "(is_enrolled=True: %d, is_enrolled=False: %d, enrolled_only=%r)",
        total_rows,
        total_enrolled,
        total_inactive,
        enrolled_only,
    )

    def _keep(r: Dict[str, Any]) -> bool:
        fn = (r.get("first_name") or "").lower()
        ln = (r.get("last_name") or "").lower()
        gend = (r.get("gender") or "").upper()
        grade = (r.get("grade_level") or "").upper()
        is_enrolled = bool(r.get("is_enrolled"))

        if fn_pref and not fn.startswith(fn_pref):
            return False
        if ln_pref and not ln.startswith(ln_pref):
            return False
        if allowed_genders and gend not in allowed_genders:
            return False
        if allowed_grades and grade not in allowed_grades:
            return False

        # Enrollment filter, based on status from student_school_enrollments
        if enrolled_only is True and not is_enrolled:
            return False
        if enrolled_only is False and is_enrolled:
            return False

        return True

    filtered = [r for r in rows if _keep(r)]

    f_total = len(filtered)
    f_enrolled = sum(1 for r in filtered if r.get("is_enrolled"))
    f_inactive = f_total - f_enrolled

    logger.info(
        "[student_info_table] _apply_filters: after filters -> %d rows "
        "(is_enrolled=True: %d, is_enrolled=False: %d)",
        f_total,
        f_enrolled,
        f_inactive,
    )

    # small debug sample of filtered rows
    logger.debug(
        "[student_info_table] filtered row sample (first 5): %s",
        [
            {
                "student_id": r.get("student_id"),
                "first_name": r.get("first_name"),
                "last_name": r.get("last_name"),
                "grade_level": r.get("grade_level"),
                "is_enrolled": r.get("is_enrolled"),
            }
            for r in filtered[:5]
        ],
    )

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
