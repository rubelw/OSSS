# src/OSSS/ai/langchain/agents/student_info_table.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from collections import Counter
from datetime import date
import logging
import re

import httpx

from OSSS.ai.agents.query_data.handlers.students_handler import (
    _fetch_students_and_persons,
    API_BASE,
)

logger = logging.getLogger("OSSS.ai.langchain.student_info_table")


# ---------------------------------------------------------------------------
# Filter extraction helpers
# ---------------------------------------------------------------------------

def _extract_last_name_prefix(message: str) -> Optional[str]:
    """
    Look for phrases like:
      - last name beginning with 'S'
      - last names starting with "Sm"
      - last name starts with S
    and return the prefix (uppercased).
    """
    patterns = [
        r"last\s+name[s]?\s+(?:starting|beginning|begins|starts)\s+with\s+['\"]?([A-Za-z]{1,20})['\"]?",
        r"last\s+name[s]?\s+['\"]?([A-Za-z]{1,20})['\"]?\s+only",
    ]
    msg = message or ""
    for pat in patterns:
        m = re.search(pat, msg, flags=re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None


def _extract_first_name_prefix(message: str) -> Optional[str]:
    """
    Look for phrases like:
      - first name beginning with 'M'
      - first names starting with "Mi"
      - first name starts with J
    and return the prefix (uppercased).
    """
    patterns = [
        r"first\s+name[s]?\s+(?:starting|beginning|begins|starts)\s+with\s+['\"]?([A-Za-z]{1,20})['\"]?",
        r"first\s+name[s]?\s+['\"]?([A-Za-z]{1,20})['\"]?\s+only",
    ]
    msg = message or ""
    for pat in patterns:
        m = re.search(pat, msg, flags=re.IGNORECASE)
        if m:
            return m.group(1).upper()
    return None


def _extract_gender_filter(message: str) -> Optional[List[str]]:
    """
    Detect simple gender filters in the message.

    Examples:
      - "show student info for FEMALE"
      - "girls only"
      - "boys in THIRD grade"
    Returns a list like ["FEMALE"] or ["FEMALE", "OTHER"] (uppercased),
    or None if no obvious gender terms are found.
    """
    msg = (message or "").lower()
    genders: set[str] = set()

    if "female" in msg or "girl" in msg or "girls" in msg:
        genders.add("FEMALE")
    if "male" in msg or "boy" in msg or "boys" in msg:
        genders.add("MALE")
    if "other" in msg or "nonbinary" in msg or "non-binary" in msg:
        genders.add("OTHER")

    # Also allow explicit phrases like "gender FEMALE", "gender: male"
    m = re.search(r"gender\s*[:=]?\s*([A-Za-z]+)", msg)
    if m:
        val = m.group(1).upper()
        if val in {"FEMALE", "MALE", "OTHER"}:
            genders.add(val)

    return list(genders) if genders else None


def _extract_grade_filter(message: str) -> Optional[List[str]]:
    """
    Detect grade-level filters in the message.

    Supports:
      - "PREK", "pre-k", "pre k"
      - "kindergarten", "kinder", "grade K"
      - word grades: "first", "second", "third", "fourth", ...
      - numeric grades: "3rd grade", "grade 3", "grade 10", etc.

    Returns a list of canonical grade labels as used in OSSS:
      PREK, KINDERGARTEN, FIRST, SECOND, THIRD, FORTH, FIFTH, ...
    """
    msg = (message or "").lower()
    labels: set[str] = set()

    # Explicit tokens for PREK / Kindergarten
    token_map = {
        "prek": "PREK",
        "pre-k": "PREK",
        "pre k": "PREK",
        "kindergarten": "KINDERGARTEN",
        "kinder": "KINDERGARTEN",
        "grade k": "KINDERGARTEN",
    }
    for token, label in token_map.items():
        if token in msg:
            labels.add(label)

    # Word-based grades
    word_map = {
        "first": "FIRST",
        "second": "SECOND",
        "third": "THIRD",
        # OSSS enum uses FORTH/NINETH – normalize both spellings
        "fourth": "FORTH",
        "forth": "FORTH",
        "fifth": "FIFTH",
        "sixth": "SIXTH",
        "seventh": "SEVENTH",
        "eighth": "EIGHTH",
        "ninth": "NINETH",
        "nineth": "NINETH",
        "tenth": "TENTH",
        "eleventh": "ELEVENTH",
        "twelfth": "TWELFTH",
    }
    for word, label in word_map.items():
        if re.search(rf"\b{word}\b", msg):
            labels.add(label)

    # Numeric grades: "3rd grade", "grade 3"
    num_map = {
        1: "FIRST",
        2: "SECOND",
        3: "THIRD",
        4: "FORTH",
        5: "FIFTH",
        6: "SIXTH",
        7: "SEVENTH",
        8: "EIGHTH",
        9: "NINETH",
        10: "TENTH",
        11: "ELEVENTH",
        12: "TWELFTH",
    }

    for m in re.finditer(r"\b([1-9]|1[0-2])(?:st|nd|rd|th)?\s+grade\b", msg):
        n = int(m.group(1))
        label = num_map.get(n)
        if label:
            labels.add(label)

    for m in re.finditer(r"grade\s+([1-9]|1[0-2])\b", msg):
        n = int(m.group(1))
        label = num_map.get(n)
        if label:
            labels.add(label)

    # Also allow "grade level THIRD" / "grade level PREK"
    m = re.search(
        r"(?:grade\s+level|grade)\s+([A-Za-z]+)",
        msg,
    )
    if m:
        word = m.group(1).lower()
        # reuse word_map / token_map
        if word in word_map:
            labels.add(word_map[word])
        elif word in token_map:
            labels.add(token_map[word])
        elif word.upper() in {
            "PREK",
            "KINDERGARTEN",
            "FIRST",
            "SECOND",
            "THIRD",
            "FORTH",
            "FIFTH",
            "SIXTH",
            "SEVENTH",
            "EIGHTH",
            "NINETH",
            "TENTH",
            "ELEVENTH",
            "TWELFTH",
        }:
            labels.add(word.upper())

    return sorted(labels) if labels else None


def _name_matches(
    first_name: str,
    last_name: str,
    first_prefix: Optional[str],
    last_prefix: Optional[str],
) -> bool:
    """
    Apply simple startswith filters for first/last name.
    If a prefix is None, that dimension is not filtered.
    """
    fn = (first_name or "").upper()
    ln = (last_name or "").upper()

    if first_prefix and not fn.startswith(first_prefix):
        return False
    if last_prefix and not ln.startswith(last_prefix):
        return False
    return True


# ---------------------------------------------------------------------------
# Grade index builder
# ---------------------------------------------------------------------------

async def _build_student_grade_index(
    *, skip: int = 0, limit: int = 100
) -> Dict[str, str]:
    """
    Build a mapping of student_id -> grade level label using:
      - student_school_enrollments.grade_level_id
      - grade_levels (code/name)
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


# ---------------------------------------------------------------------------
# Main agent
# ---------------------------------------------------------------------------

async def run_student_info_table(*, message: str, session_id: str) -> Dict[str, Any]:
    """
    LangChain-style agent function for summarizing students.

    Supports simple natural-language filters like:
      - "show student info with last name beginning with 'S'"
      - "show student info with first name starting with 'M'"
      - "show student info for FEMALE in THIRD grade"
      - "show student info for girls in 3rd grade whose last name starts with 'S'"
    """

    # 1) Pull students + persons from OSSS backend
    data = await _fetch_students_and_persons(skip=0, limit=100)
    students: List[Dict[str, Any]] = data.get("students", [])
    persons: List[Dict[str, Any]] = data.get("persons", [])

    persons_by_id = {p["id"]: p for p in persons}
    all_students = list(students)  # unfiltered copy

    # 1b) Parse filters from the message
    first_prefix = _extract_first_name_prefix(message)
    last_prefix = _extract_last_name_prefix(message)
    gender_filter = _extract_gender_filter(message)
    grade_filter = _extract_grade_filter(message)

    if first_prefix or last_prefix or gender_filter or grade_filter:
        logger.info(
            "Applying student filters: first_prefix=%r last_prefix=%r gender_filter=%r grade_filter=%r",
            first_prefix,
            last_prefix,
            gender_filter,
            grade_filter,
        )

    # 2) Build student_id -> grade_level_label index from enrollments
    student_grade_index = await _build_student_grade_index(skip=0, limit=100)

    by_grade = Counter()
    by_gender = Counter()
    rows: List[Dict[str, Any]] = []
    filtered_students: List[Dict[str, Any]] = []

    for s in students:
        person = persons_by_id.get(s.get("person_id") or "")

        first_name = (person or {}).get("first_name") or ""
        last_name = (person or {}).get("last_name") or ""

        # Name filters first (cheap)
        if not _name_matches(first_name, last_name, first_prefix, last_prefix):
            continue

        # Gender from person; fallback to student or Unknown
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

        # Gender filter
        if gender_filter and gender.upper() not in gender_filter:
            continue

        # Grade filter (compare on uppercase to tolerate case differences)
        if grade_filter and grade.upper() not in grade_filter:
            continue

        filtered_students.append(s)

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

    students = filtered_students

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

    # Header text that reflects filters (if any)
    if first_prefix or last_prefix or gender_filter or grade_filter:
        desc_parts: List[str] = []
        if first_prefix:
            desc_parts.append(f"first name beginning with '{first_prefix}'")
        if last_prefix:
            desc_parts.append(f"last name beginning with '{last_prefix}'")
        if gender_filter:
            genders_h = ", ".join(g.title() for g in gender_filter)
            desc_parts.append(f"gender in [{genders_h}]")
        if grade_filter:
            grades_h = ", ".join(grade_filter)
            desc_parts.append(f"grade level in [{grades_h}]")

        desc = " and ".join(desc_parts)
        found_line = (
            f"I found {len(students)} students in the live OSSS backend "
            f"matching {desc}."
        )
    else:
        found_line = f"I found {len(students)} students in the live OSSS backend."

    reply = "\n".join(
        [
            found_line,
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

    return {
        "reply": reply,
        "raw_students": all_students,        # unfiltered
        "filtered_students": students,       # after all filters
        "raw_persons": persons,
        "student_grade_index": student_grade_index,
        "first_name_prefix": first_prefix,
        "last_name_prefix": last_prefix,
        "gender_filter": gender_filter,
        "grade_filter": grade_filter,
    }
