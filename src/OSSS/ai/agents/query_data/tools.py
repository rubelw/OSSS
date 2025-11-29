from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List, Optional
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# Adjust these to your actual model paths
from OSSS.db.session import get_async_session
from OSSS.models.students import Student  # example name
from OSSS.models.enrollments import Enrollment  # if you need joins

logger = logging.getLogger("OSSS.ai.agents.students.tools")


# ---------------------------------------------------------------------------
# Simple DTOs / filter objects
# ---------------------------------------------------------------------------

@dataclass
class StudentFilters:
    student_id: Optional[UUID] = None
    external_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    grade_level: Optional[str] = None
    school_year: Optional[str] = None
    active_only: bool = True
    limit: int = 50


@dataclass
class StudentRecord:
    id: UUID
    first_name: str
    last_name: str
    grade_level: Optional[str]
    external_id: Optional[str]
    is_active: bool

    @classmethod
    def from_orm(cls, student: Student) -> "StudentRecord":
        return cls(
            id=student.id,
            first_name=student.first_name,
            last_name=student.last_name,
            grade_level=getattr(student, "grade_level", None),
            external_id=getattr(student, "external_id", None),
            is_active=getattr(student, "is_active", True),
        )


# ---------------------------------------------------------------------------
# Core query builders (pure table functions)
# ---------------------------------------------------------------------------

def build_student_query(filters: StudentFilters) -> Select:
    """Build a SQLAlchemy Select for students based purely on filters."""
    stmt = select(Student)
    conditions = []

    if filters.student_id:
        conditions.append(Student.id == filters.student_id)

    if filters.external_id:
        conditions.append(Student.external_id == filters.external_id)

    if filters.first_name:
        # case-insensitive prefix match
        conditions.append(Student.first_name.ilike(filters.first_name + "%"))

    if filters.last_name:
        conditions.append(Student.last_name.ilike(filters.last_name + "%"))

    if filters.grade_level:
        conditions.append(Student.grade_level == filters.grade_level)

    if filters.active_only and hasattr(Student, "is_active"):
        conditions.append(Student.is_active.is_(True))

    if conditions:
        stmt = stmt.where(and_(*conditions))

    stmt = stmt.limit(filters.limit)
    return stmt


async def get_student_by_id(
    session: AsyncSession,
    student_id: UUID,
) -> Optional[StudentRecord]:
    """Return a single student by ID, or None."""
    filters = StudentFilters(student_id=student_id, limit=1, active_only=False)
    stmt = build_student_query(filters)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if not row:
        return None
    return StudentRecord.from_orm(row)


async def search_students(
    session: AsyncSession,
    filters: StudentFilters,
) -> List[StudentRecord]:
    """Return a list of matching students."""
    stmt = build_student_query(filters)
    result = await session.execute(stmt)
    rows: Iterable[Student] = result.scalars().all()
    return [StudentRecord.from_orm(r) for r in rows]


async def list_students_for_grade(
    session: AsyncSession,
    grade_level: str,
    active_only: bool = True,
    limit: int = 100,
) -> List[StudentRecord]:
    """Convenience wrapper around search_students for grade-level listings."""
    filters = StudentFilters(
        grade_level=grade_level,
        active_only=active_only,
        limit=limit,
    )
    return await search_students(session, filters)


# ---------------------------------------------------------------------------
# Convenience entry point so agents don't need to manage sessions
# ---------------------------------------------------------------------------

async def query_students_tool(filters: StudentFilters) -> List[StudentRecord]:
    """
    High-level tool: open a session and run a student search.

    This is what your AI agent will call. The agent never touches ORM models or
    raw tables directly — only this function.
    """
    async with get_async_session() as session:
        return await search_students(session, filters)


async def get_student_tool(student_id: UUID) -> Optional[StudentRecord]:
    """High-level tool for fetching a single student."""
    async with get_async_session() as session:
        return await get_student_by_id(session, student_id)
