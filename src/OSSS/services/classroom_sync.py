# src/OSSS/services/classroom_sync.py
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from OSSS.services.google_client import classroom_service_impersonate, classroom_service_user

from googleapiclient.errors import HttpError

from OSSS.db.session import get_async_session
from OSSS.db.models.course_sections import CourseSection
from OSSS.db.models.courses import Course
from OSSS.db.models.students import Student
from OSSS.db.models.teacher_section_assignments import TeacherSectionAssignment
from OSSS.db.models.external_ids import ExternalId
from OSSS.db.models.persons import Person
from OSSS.db.models.student_section_enrollments import StudentSectionEnrollment

from .client import classroom_service_impersonate, classroom_service_user  # noqa: F401  (user flow optional)
from .mappers import map_course_payload

log = logging.getLogger(__name__)

GC_SYSTEM = "google_classroom"


# ------------------------
# Google API – thread shim
# ------------------------
async def _gc_to_thread(fn, *args, **kwargs):
    """Run a blocking googleapiclient call on a worker thread."""
    return await asyncio.to_thread(fn, *args, **kwargs)


# ------------------------
# Core upsert helpers
# ------------------------
async def _get_or_create_course(
    service,
    db: AsyncSession,
    section: CourseSection,
    teacher_email: str,
) -> str:
    """
    Ensure a Classroom Course exists for this section.
    Uses ExternalId(system='google_classroom', entity_type='section', entity_id=section.id)
    as the stable mapping.
    """
    # Look up mapping
    ext = await db.scalar(
        sa.select(ExternalId).where(
            ExternalId.system == GC_SYSTEM,
            ExternalId.entity_type == "section",
            ExternalId.entity_id == section.id,
        )
    )

    # Build payload
    section_label = getattr(section, "section_name", None) or getattr(section, "code", None) or ""
    room = getattr(section, "room", None)
    payload = map_course_payload(
        course_name=section.course.name,  # requires joinedload(CourseSection.course)
        section=section_label,
        room=room,
        owner_email=teacher_email,
    )

    courses = service.courses()

    # Try update (PATCH) if we have an external id
    if ext and ext.external_id:
        try:
            # get → patch
            course = await _gc_to_thread(courses.get(id=ext.external_id).execute)
            await _gc_to_thread(courses.patch(id=course["id"], body=payload).execute)
            return course["id"]
        except HttpError as e:
            if getattr(e, "resp", None) and e.resp.status == 404:
                log.info("GC course id %s not found. Will recreate.", ext.external_id)
            else:
                raise

    # Create new course
    course = await _gc_to_thread(courses.create(body=payload).execute)
    course_id = course["id"]

    # Persist/Update mapping
    if ext:
        ext.external_id = course_id
        if isinstance(ext.extra, dict):
            ext.extra["owner_email"] = teacher_email
        else:
            ext.extra = {"owner_email": teacher_email}
    else:
        db.add(
            ExternalId(
                system=GC_SYSTEM,
                entity_type="section",
                entity_id=section.id,
                external_id=course_id,
                extra={"owner_email": teacher_email},
            )
        )

    await db.commit()
    return course_id


async def _ensure_teacher(service, course_id: str, teacher_email: str) -> None:
    """Add a teacher to the course (idempotent)."""
    teachers = service.courses().teachers()
    try:
        await _gc_to_thread(
            teachers.create(courseId=course_id, body={"userId": teacher_email}).execute
        )
    except HttpError as e:
        if getattr(e, "resp", None) and e.resp.status == 409:
            # already a teacher
            return
        raise


async def _ensure_student(service, course_id: str, student_email: str) -> None:
    """Enroll a student (idempotent)."""
    students = service.courses().students()
    try:
        await _gc_to_thread(
            students.create(courseId=course_id, body={"userId": student_email}).execute
        )
    except HttpError as e:
        if getattr(e, "resp", None) and e.resp.status == 409:
            # already enrolled
            return
        # Often 400/404: account doesn’t exist or isn’t Classroom-enabled; leave to caller to log
        raise


# ------------------------
# Public sync entry points
# ------------------------
async def sync_section_by_id(section_id: str) -> int:
    """
    Creates/updates the Google Classroom Course for the section, ensures the primary teacher,
    and syncs all enrolled students. Returns count of students attempted.
    """
    async with get_async_session() as db:
        # Load section with the bits we need
        section: Optional[CourseSection] = await db.scalar(
            sa.select(CourseSection)
            .where(CourseSection.id == section_id)
            .options(
                joinedload(CourseSection.course),  # section.course.name
            )
        )
        if not section:
            log.warning("Section %s not found.", section_id)
            return 0

        # Find a primary teacher (or first teacher assignment) with an email
        tsa_result = await db.scalars(
            sa.select(TeacherSectionAssignment)
            .where(TeacherSectionAssignment.section_id == section.id)
            .options(joinedload(TeacherSectionAssignment.person))
        )
        teacher_assignment = next((t for t in tsa_result if t.person and t.person.email), None)
        if not teacher_assignment:
            log.warning("No teacher with email found for section %s", section_id)
            return 0

        teacher_email = teacher_assignment.person.email

        # Build a Classroom client via domain-wide delegation, impersonating the teacher
        service = classroom_service_impersonate(teacher_email)

        # Upsert the GC course and map it in ExternalId
        course_id = await _get_or_create_course(service, db, section, teacher_email)

        # Ensure the (primary) teacher is present
        await _ensure_teacher(service, course_id, teacher_email)

        # Optionally: add other co-teachers here (iterate other TSA rows with email)
        # for t in tsa_result:
        #     if t is teacher_assignment:
        #         continue
        #     if t.person and t.person.email:
        #         await _ensure_teacher(service, course_id, t.person.email)

        # ---------------------------
        # Sync student enrollments
        # ---------------------------
        # Join your enrollment table → students → person to fetch emails
        students_q = await db.scalars(
            sa.select(Student)
            .join(Student.person)  # Student -> Person relationship
            .join(
                StudentSectionEnrollment,
                StudentSectionEnrollment.student_id == Student.id,
            )
            .where(StudentSectionEnrollment.section_id == section.id)
            .options(joinedload(Student.person))
        )

        count = 0
        async def _enroll_one(stu: Student):
            email = getattr(stu.person, "email", None)
            if not email:
                return False
            try:
                await _ensure_student(service, course_id, email)
                return True
            except HttpError as e:
                # Common causes: user not provisioned, Classroom disabled, external domain
                code = getattr(e, "resp", None).status if getattr(e, "resp", None) else "?"
                log.warning("Enroll failed for %s (code=%s): %s", email, code, e)
                return False
            except Exception as e:
                log.exception("Enroll failed for %s: %s", email, e)
                return False

        # Concurrency cap to avoid API rate spikes
        sem = asyncio.Semaphore(8)

        async def _guarded_enroll(stu: Student):
            async with sem:
                return await _enroll_one(stu)

        tasks = [asyncio.create_task(_guarded_enroll(stu)) for stu in students_q]
        if tasks:
            results = await asyncio.gather(*tasks)
            count = sum(1 for ok in results if ok)

        log.info("Synced section %s → GC course %s; students added: %s", section_id, course_id, count)
        return count


async def sync_sections_for_teacher(teacher_person_id: str) -> int:
    """
    Convenience helper: sync all sections for a given teacher (by person.id).
    Returns total students attempted across sections.
    """
    total = 0
    async with get_async_session() as db:
        # Find all sections where this person is assigned as teacher
        tsa_rows = await db.scalars(
            sa.select(TeacherSectionAssignment.section_id)
            .join(TeacherSectionAssignment.person)  # ensures Person relationship is valid
            .where(Person.id == teacher_person_id)
        )
        section_ids = list({sid for sid in tsa_rows if sid})

    for sid in section_ids:
        try:
            total += await sync_section_by_id(sid)
        except Exception:
            log.exception("Section sync failed for %s", sid)
    return total


# Optional CLI entry point
def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Sync Classroom for a section or a teacher's sections.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--section-id", help="UUID of CourseSection to sync")
    g.add_argument("--teacher-person-id", help="UUID of Person for teacher; sync all sections")
    args = parser.parse_args()

    if args.section_id:
        count = asyncio.run(sync_section_by_id(args.section_id))
        print(f"Added {count} students.")
        return 0

    if args.teacher_person_id:
        count = asyncio.run(sync_sections_for_teacher(args.teacher_person_id))
        print(f"Added {count} students across sections.")
        return 0

    return 2


__all__ = [
    "sync_section_by_id",
    "sync_sections_for_teacher",
    "main",
]
