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
            "Controls filtering by current enrollment status based on the latest "
            "student_school_enrollments.status value.\n\n"
            "- If True, only include students who are currently enrolled "
            "  (latest status in ['ENROLLED', 'ACTIVE']).\n"
            "- If False, only include students who are NOT currently enrolled "
            "  (e.g., WITHDRAWN).\n"
            "- If omitted or null, we DEFAULT TO True (currently enrolled only)."
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
    return result["reply"]


# ---------------------------------------------------------------------------
# Helpers to get enrollments via QueryData handler
# ---------------------------------------------------------------------------

def _index_grade_levels(grade_levels) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for gl in grade_levels or []:
        if isinstance(gl, dict):
            gl_id = gl.get("id")
        else:
            gl_id = getattr(gl, "id", None)
        if gl_id is None:
            continue
        idx[str(gl_id)] = gl
    logger.info(
        "[student_info_table] _index_grade_levels: built index for %d grade_levels",
        len(idx),
    )
    return idx


async def _fetch_all_persons(
    *,
    page_size: int = 500,
    max_pages: int = 20,
    timeout_s: float = 10.0,
) -> List[Dict[str, Any]]:
    persons: List[Dict[str, Any]] = []
    skip = 0

    url = f"{API_BASE}/api/persons"

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            for page_idx in range(max_pages):
                params = {"skip": skip, "limit": page_size}
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                payload = resp.json()

                page = _coerce_list(payload, label=f"persons(page {page_idx})")
                if not page:
                    break

                page_dicts = [p for p in page if isinstance(p, dict)]
                persons.extend(page_dicts)

                logger.info(
                    "[student_info_table] _fetch_all_persons: page=%d skip=%d limit=%d got=%d total=%d",
                    page_idx,
                    skip,
                    page_size,
                    len(page_dicts),
                    len(persons),
                )

                if len(page) < page_size:
                    break

                skip += page_size

    except httpx.HTTPError as e:
        logger.error(
            "[student_info_table] _fetch_all_persons: error fetching persons pages: %s",
            e,
            exc_info=True,
        )

    return persons


async def _fetch_student_school_enrollments(
    *,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
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


def _coerce_list(payload, *, label: str) -> list:
    if payload is None:
        return []

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for k in ("items", "data", "results", "rows", "persons", "students"):
            v = payload.get(k)
            if isinstance(v, list):
                logger.debug("[student_info_table] %s payload is dict; using key=%r len=%d", label, k, len(v))
                return v
        logger.warning("[student_info_table] %s payload is dict but no list key found. keys=%s", label, list(payload.keys())[:30])
        return []

    logger.warning("[student_info_table] %s payload unexpected type=%s repr=%r", label, type(payload).__name__, payload)
    return []


async def _fetch_grade_levels(
    *, skip: int = 0, limit: int = 100
) -> List[Dict[str, Any]]:
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
) -> Tuple[Dict[str, str], Dict[str, bool], Dict[str, str]]:
    enrollments = await _fetch_student_school_enrollments(skip=skip, limit=limit)
    grade_levels = await _fetch_grade_levels(skip=0, limit=100)

    logger.info(
        "[student_info_table] _build_student_grade_index: fetched %d enrollments, %d grade_levels",
        len(enrollments),
        len(grade_levels),
    )

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

    grade_label_by_id: Dict[str, str] = {}
    for gl in grade_levels:
        if isinstance(gl, dict):
            gid = gl.get("id")
            code = gl.get("code")
            name = gl.get("name") or gl.get("grade_name")
        else:
            gid = getattr(gl, "id", None)
            code = getattr(gl, "code", None)
            name = getattr(gl, "name", None) or getattr(gl, "grade_name", None)
        if not gid:
            continue
        label = code or name or "UNKNOWN"
        grade_label_by_id[str(gid)] = label

    by_student: Dict[str, List[Dict[str, Any]]] = {}
    for enr in enrollments:
        sid = enr.get("student_id")
        if not sid:
            continue
        by_student.setdefault(sid, []).append(enr)

    student_grade: Dict[str, str] = {}
    student_enrolled: Dict[str, bool] = {}
    student_status: Dict[str, str] = {}

    def _key(e: Dict[str, Any]) -> date:
        d = _parse_date(e.get("entry_date"))
        return d or date.min

    for sid, enr_list in by_student.items():
        if not enr_list:
            continue

        for e in enr_list:
            status = e.get("status")
            if isinstance(status, str):
                e["_status_norm"] = status.strip().upper()
            else:
                e["_status_norm"] = ""

        try:
            latest = max(enr_list, key=_key)
        except ValueError:
            continue

        # ✅ normalize empty -> UNKNOWN
        latest_status = latest.get("_status_norm", "") or "UNKNOWN"
        is_enrolled = latest_status in {"ENROLLED", "ACTIVE"}

        gid_raw = latest.get("grade_level_id")
        gid = str(gid_raw) if gid_raw is not None else None
        label = grade_label_by_id.get(gid, "UNKNOWN")

        student_enrolled[sid] = is_enrolled
        student_grade[sid] = label
        student_status[sid] = latest_status

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

    sample_idx = list(student_enrolled.items())[:10]
    logger.debug(
        "[student_info_table] student_enrolled index sample (first 10): %s",
        sample_idx,
    )

    return student_grade, student_enrolled, student_status


# ---------------------------------------------------------------------------
# Internal helper: build full table rows (no filtering)
# ---------------------------------------------------------------------------

def _person_id_from_dict(p: dict):
    for k in ("id", "person_id", "personId", "uuid"):
        if p.get(k):
            return p.get(k)

    for k in ("person", "data", "attributes"):
        v = p.get(k)
        if isinstance(v, dict):
            for kk in ("id", "person_id", "personId", "uuid"):
                if v.get(kk):
                    return v.get(kk)

    return None


def _index_persons(persons) -> dict[str, dict]:
    persons = _coerce_list(persons, label="persons(index)")
    idx: dict[str, dict] = {}

    logger.debug("[student_info_table] _index_persons: persons len=%d", len(persons))
    if persons[:1] and isinstance(persons[0], dict):
        logger.debug("[student_info_table] _index_persons: first person keys=%s", list(persons[0].keys())[:50])

    for p in persons:
        if not isinstance(p, dict):
            continue
        raw_id = _person_id_from_dict(p)
        if raw_id is None:
            continue
        idx[str(raw_id)] = p

    logger.info("[student_info_table] _index_persons: indexed %d persons", len(idx))
    logger.debug("[student_info_table] _index_persons: id sample=%s", list(idx.keys())[:10])
    return idx


async def _build_student_rows(skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    data = await _fetch_students_and_persons(skip=skip, limit=limit)

    students_raw = data.get("students", [])
    persons_raw = data.get("persons", [])

    students = _coerce_list(students_raw, label="students")
    persons = _coerce_list(persons_raw, label="persons")

    logger.info("[student_info_table] fetched students=%d persons=%d (raw students type=%s, raw persons type=%s)",
                len(students), len(persons), type(students_raw).__name__, type(persons_raw).__name__)

    logger.info(
        "[student_info_table] _build_student_rows: fetched %d students and %d persons "
        "(skip=%d, limit=%d)",
        len(students),
        len(persons),
        skip,
        limit,
    )

    persons_by_id = _index_persons(persons)

    student_person_ids = [str(s.get("person_id")) for s in students if s.get("person_id")]
    missing_all = [pid for pid in student_person_ids if pid not in persons_by_id]
    missing_preview = missing_all[:10]

    logger.warning(
        "[student_info_table] sanity: persons_by_id=%d students_with_person_id=%d missing_total=%d example_missing=%s",
        len(persons_by_id),
        len(student_person_ids),
        len(missing_all),
        missing_preview,
    )

    if missing_all:
        logger.warning(
            "[student_info_table] Missing %d/%d referenced person_ids in initial persons payload; "
            "falling back to paginated /api/persons fetch (Option A).",
            len(missing_all),
            len(student_person_ids),
        )

        persons_full = await _fetch_all_persons(page_size=500, max_pages=20, timeout_s=10.0)

        if persons_full:
            persons = persons_full
            persons_by_id = _index_persons(persons_full)

            missing_after = [pid for pid in student_person_ids if pid not in persons_by_id]
            logger.warning(
                "[student_info_table] After paginated persons fetch: persons_by_id=%d missing_total=%d example_missing=%s",
                len(persons_by_id),
                len(missing_after),
                missing_after[:10],
            )
        else:
            logger.warning(
                "[student_info_table] Paginated persons fetch returned 0 rows; "
                "names may remain blank for some/all students."
            )

    student_grade_index, student_enrolled_index, student_status_index = await _build_student_grade_index(
        skip=skip, limit=limit
    )

    rows: List[Dict[str, Any]] = []

    if students:
        logger.debug(
            "[student_info_table] students sample (first 5): %s",
            [
                {
                    "id": s.get("id"),
                    "person_id": s.get("person_id"),
                    "grad_year": s.get("graduation_year"),
                }
                for s in students[:5]
            ],
        )

    for s in students:
        raw_pid = s.get("person_id")
        person = persons_by_id.get(str(raw_pid)) if raw_pid is not None else None

        first_name = (person or {}).get("first_name") or ""
        middle_name = (person or {}).get("middle_name") or ""
        last_name = (person or {}).get("last_name") or ""

        logger.debug(
            "[student_info_table] person lookup debug: student_id=%s person_id=%s person_found=%s",
            s.get("id"),
            raw_pid,
            (person is not None),
        )

        gender = (person or {}).get("gender") or s.get("gender") or "UNKNOWN"
        student_id = s.get("id") or ""

        grade = (
            student_grade_index.get(student_id)
            or s.get("grade_level")
            or s.get("grade_level_name")
            or s.get("grade")
            or "UNKNOWN"
        )

        is_enrolled = bool(student_enrolled_index.get(student_id, False))

        # ✅ define status per student (fixes "status not found")
        status = student_status_index.get(student_id) or "UNKNOWN"

        dob = (person or {}).get("dob") or (person or {}).get("date_of_birth")
        pid = str(raw_pid) if raw_pid else ""

        rows.append(
            {
                "person_id": (person or {}).get("id"),
                "personId": pid,
                "person_uuid": pid,
                "first_name": first_name,
                "middle_name": middle_name,
                "last_name": last_name,
                "dob": dob,
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
                "status": status,
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

    logger.debug(
        "[student_info_table] unified row sample (first 5): %s",
        [
            {
                "student_id": r.get("student_id"),
                "first_name": r.get("first_name"),
                "last_name": r.get("last_name"),
                "grade_level": r.get("grade_level"),
                "is_enrolled": r.get("is_enrolled"),
                "status": r.get("status"),
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
        "student_status_index": student_status_index,
    }


# ---------------------------------------------------------------------------
# Filtering helper
# ---------------------------------------------------------------------------

def _apply_filters(
    rows: List[Dict[str, Any]],
    filters: Optional[StudentInfoFilters],
) -> List[Dict[str, Any]]:
    if not filters:
        total_rows = len(rows)
        total_enrolled = sum(1 for r in rows if r.get("is_enrolled"))
        total_inactive = total_rows - total_enrolled

        logger.info(
            "[student_info_table] _apply_filters: filters=None, "
            "defaulting to enrolled_only=True; starting with %d rows "
            "(is_enrolled=True: %d, is_enrolled=False: %d)",
            total_rows,
            total_enrolled,
            total_inactive,
        )

        filtered_default = [r for r in rows if bool(r.get("is_enrolled"))]

        f_total = len(filtered_default)
        f_enrolled = sum(1 for r in filtered_default if r.get("is_enrolled"))
        f_inactive = f_total - f_enrolled

        logger.info(
            "[student_info_table] _apply_filters: filters=None -> after default "
            "enrolled_only=True filter: %d rows "
            "(is_enrolled=True: %d, is_enrolled=False: %d)",
            f_total,
            f_enrolled,
            f_inactive,
        )

        return filtered_default

    logger.info("[student_info_table] Applying filters: %s", filters.model_dump())

    fn_pref = (filters.first_name_prefix or "").lower()
    ln_pref = (filters.last_name_prefix or "").lower()
    allowed_genders = {g.upper() for g in (filters.genders or [])}
    allowed_grades = {g.upper() for g in (filters.grade_levels or [])}

    raw_enrolled_only = filters.enrolled_only
    effective_enrolled_only = True if raw_enrolled_only is None else raw_enrolled_only

    total_rows = len(rows)
    total_enrolled = sum(1 for r in rows if r.get("is_enrolled"))
    total_inactive = total_rows - total_enrolled

    logger.info(
        "[student_info_table] _apply_filters: starting with %d rows "
        "(is_enrolled=True: %d, is_enrolled=False: %d, "
        "raw_enrolled_only=%r, effective_enrolled_only=%r)",
        total_rows,
        total_enrolled,
        total_inactive,
        raw_enrolled_only,
        effective_enrolled_only,
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

        if effective_enrolled_only is True and not is_enrolled:
            return False
        if effective_enrolled_only is False and is_enrolled:
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

    return filtered


# ---------------------------------------------------------------------------
# Public API 1: legacy unstructured function (no filters)
# ---------------------------------------------------------------------------

async def run_student_info_table(*, message: str, session_id: str) -> Dict[str, Any]:
    built = await _build_student_rows(skip=0, limit=100)
    rows = built["rows"]
    students = built["students"]
    persons = built["persons"]
    student_grade_index = built["student_grade_index"]

    filtered_rows = rows

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
    by_status = Counter()

    for r in filtered_rows:
        by_status[r.get("status") or "UNKNOWN"] += 1
        by_grade[r["grade_level"]] += 1
        by_gender[r["gender"] or "UNKNOWN"] += 1

    header = (
        "| # | First | Middle | Last | DOB | Email | Phone | Gender | "
        "Status | Created At | Updated At | Student Number | Graduation Year | Grade Level |"
    )
    sep = (
        "|---|-------|--------|------|-----|-------|-------|--------|"
        "--------|------------|------------|----------------|------------------|------------|"
    )
    table_lines = [header, sep]

    for idx, r in enumerate(filtered_rows[:50], start=1):
        table_lines.append(
            "| {i} | {fn} | {mn} | {ln} | {dob} | {email} | {phone} | {gender} | "
            "{status} | {pcrt} | {pupd} | {snum} | {gyear} | {grade} |".format(
                i=idx,
                fn=r.get("first_name") or "",
                mn=r.get("middle_name") or "",
                ln=r.get("last_name") or "",
                dob=r.get("dob") or "",
                email=r.get("email") or "",
                phone=r.get("phone") or "",
                gender=r.get("gender") or "",
                status=r.get("status") or "UNKNOWN",
                pcrt=r.get("person_created_at") or "",
                pupd=r.get("person_updated_at") or "",
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
    status_lines = ["By status:", *[f"- {s}: {c} students" for s, c in by_status.most_common()]]

    reply = "\n".join(
        [
            f"I found {len(filtered_rows)} students in the live OSSS backend after applying filters.",
            "",
            *grade_lines,
            "",
            *gender_lines,
            "",
            *status_lines,
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
