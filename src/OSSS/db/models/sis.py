# src/OSSS/db/models/sis.py
from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB  # TSVectorType if/when needed


# ---------- District / School / Calendar ----------



class School(UUIDMixin, Base):
    __tablename__ = "schools"

    organization_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    school_code: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    nces_school_id: Mapped[Optional[str]] = mapped_column(sa.Text)
    building_code: Mapped[Optional[str]] = mapped_column(sa.Text)
    type: Mapped[Optional[str]] = mapped_column(sa.Text)
    timezone: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )


class AcademicTerm(UUIDMixin, Base):
    __tablename__ = "academic_terms"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    type: Mapped[Optional[str]] = mapped_column(sa.Text)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class GradingPeriod(UUIDMixin, Base):
    __tablename__ = "grading_periods"

    term_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Calendar(UUIDMixin, Base):
    __tablename__ = "calendars"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class CalendarDay(UUIDMixin, Base):
    __tablename__ = "calendar_days"

    calendar_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    day_type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=text("'instructional'"))
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("calendar_id", "date", name="uq_calendar_day"),)


class BellSchedule(UUIDMixin, Base):
    __tablename__ = "bell_schedules"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Period(UUIDMixin, Base):
    __tablename__ = "periods"

    bell_schedule_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("bell_schedules.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    start_time: Mapped[time] = mapped_column(sa.Time, nullable=False)
    end_time: Mapped[time] = mapped_column(sa.Time, nullable=False)
    sequence: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class GradeLevel(UUIDMixin, Base):
    __tablename__ = "grade_levels"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    ordinal: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Department(UUIDMixin, Base):
    __tablename__ = "departments"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_department_name"),)


class Subject(UUIDMixin, Base):
    __tablename__ = "subjects"

    department_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("departments.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Course(UUIDMixin, Base):
    __tablename__ = "courses"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("subjects.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(sa.Text)
    credit_hours: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(4, 2))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class CourseSection(UUIDMixin, Base):
    __tablename__ = "course_sections"

    course_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    term_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    section_number: Mapped[str] = mapped_column(sa.Text, nullable=False)
    capacity: Mapped[Optional[int]] = mapped_column(sa.Integer)
    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("course_id", "term_id", "section_number", name="uq_course_term_section"),)


class Room(UUIDMixin, Base):
    __tablename__ = "rooms"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    capacity: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- People / Accounts ----------

class Person(UUIDMixin, Base):
    __tablename__ = "persons"

    first_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    last_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    middle_name: Mapped[Optional[str]] = mapped_column(sa.Text)
    dob: Mapped[Optional[date]] = mapped_column(sa.Date)
    email: Mapped[Optional[str]] = mapped_column(sa.Text)
    phone: Mapped[Optional[str]] = mapped_column(sa.Text)
    gender: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Student(UUIDMixin, Base):
    __tablename__ = "students"

    student_number: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    graduation_year: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Staff(UUIDMixin, Base):
    __tablename__ = "staff"

    employee_number: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    title: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Guardian(UUIDMixin, Base):
    __tablename__ = "guardians"

    relationship: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class UserAccount(UUIDMixin, Base):
    __tablename__ = "user_accounts"

    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    username: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Role(UUIDMixin, Base):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Permission(UUIDMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(sa.Text, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- Addresses / Contacts ----------

class Address(UUIDMixin, Base):
    __tablename__ = "addresses"

    line1: Mapped[str] = mapped_column(sa.Text, nullable=False)
    line2: Mapped[Optional[str]] = mapped_column(sa.Text)
    city: Mapped[str] = mapped_column(sa.Text, nullable=False)
    state: Mapped[Optional[str]] = mapped_column(sa.Text)
    postal_code: Mapped[Optional[str]] = mapped_column(sa.Text)
    country: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Contact(UUIDMixin, Base):
    __tablename__ = "contacts"

    type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    value: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class PersonAddress(Base):
    __tablename__ = "person_addresses"

    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    address_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("addresses.id", ondelete="CASCADE"), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class PersonContact(Base):
    __tablename__ = "person_contacts"

    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    contact_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)
    label: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_primary: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))
    is_emergency: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class StudentGuardian(Base):
    __tablename__ = "student_guardians"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    guardian_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True)
    custody: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_primary: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))
    contact_order: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class ExternalId(UUIDMixin, Base):
    __tablename__ = "external_ids"

    entity_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_id: Mapped[Any] = mapped_column(GUID(), nullable=False)
    system: Mapped[str] = mapped_column(sa.Text, nullable=False)
    external_id: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "system", name="uq_external_ids"),)


# ---------- Enrollments / Programs ----------

class StudentSchoolEnrollment(UUIDMixin, Base):
    __tablename__ = "student_school_enrollments"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    entry_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    exit_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=text("'active'"))
    exit_reason: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class StudentProgramEnrollment(UUIDMixin, Base):
    __tablename__ = "student_program_enrollments"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    program_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    status: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- Special Education / Support Plans ----------

class SpecialEducationCase(UUIDMixin, Base):
    __tablename__ = "special_education_cases"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    eligibility: Mapped[Optional[str]] = mapped_column(sa.Text)
    case_opened: Mapped[Optional[date]] = mapped_column(sa.Date)
    case_closed: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class IepPlan(UUIDMixin, Base):
    __tablename__ = "iep_plans"

    special_ed_case_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("special_education_cases.id", ondelete="CASCADE"), nullable=False)
    effective_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    effective_end: Mapped[Optional[date]] = mapped_column(sa.Date)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Accommodation(UUIDMixin, Base):
    __tablename__ = "accommodations"

    iep_plan_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("iep_plans.id", ondelete="CASCADE"))
    applies_to: Mapped[Optional[str]] = mapped_column(sa.Text)
    description: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class EllPlan(UUIDMixin, Base):
    __tablename__ = "ell_plans"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    level: Mapped[Optional[str]] = mapped_column(sa.Text)
    effective_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    effective_end: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Section504Plan(UUIDMixin, Base):
    __tablename__ = "section504_plans"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    effective_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    effective_end: Mapped[Optional[date]] = mapped_column(sa.Date)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- Scheduling ----------

class SectionMeeting(UUIDMixin, Base):
    __tablename__ = "section_meetings"

    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    period_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("periods.id", ondelete="SET NULL"))
    room_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("rooms.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("section_id", "day_of_week", "period_id", name="uq_section_meeting"),)


class TeacherSectionAssignment(UUIDMixin, Base):
    __tablename__ = "teacher_section_assignments"

    staff_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("staff_id", "section_id", name="uq_teacher_section"),)


class StudentSectionEnrollment(UUIDMixin, Base):
    __tablename__ = "student_section_enrollments"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    added_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    dropped_on: Mapped[Optional[date]] = mapped_column(sa.Date)
    seat_time_minutes: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "section_id", name="uq_student_section"),)


class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"

    course_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    prereq_course_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class SectionRoomAssignment(UUIDMixin, Base):
    __tablename__ = "section_room_assignments"

    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    room_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    end_date: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("section_id", "room_id", "start_date", name="uq_section_room_range"),)


# ---------- Attendance ----------

class AttendanceCode(Base):
    __tablename__ = "attendance_codes"

    code: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_present: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))
    is_excused: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class AttendanceEvent(UUIDMixin, Base):
    __tablename__ = "attendance_events"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_meeting_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("section_meetings.id", ondelete="SET NULL"))
    date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    code: Mapped[str] = mapped_column(sa.Text, ForeignKey("attendance_codes.code", ondelete="RESTRICT"), nullable=False)
    minutes: Mapped[Optional[int]] = mapped_column(sa.Integer)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "date", "section_meeting_id", name="uq_attendance_event"),)


class AttendanceDailySummary(UUIDMixin, Base):
    __tablename__ = "attendance_daily_summary"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    present_minutes: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    absent_minutes: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    tardy_minutes: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "date", name="uq_attendance_daily"),)


# ---------- Grading ----------

class GradeScale(UUIDMixin, Base):
    __tablename__ = "grade_scales"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    type: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class GradeScaleBand(UUIDMixin, Base):
    __tablename__ = "grade_scale_bands"

    grade_scale_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("grade_scales.id", ondelete="CASCADE"), nullable=False)
    label: Mapped[str] = mapped_column(sa.Text, nullable=False)
    min_value: Mapped[Decimal] = mapped_column(sa.Numeric(6, 3), nullable=False)
    max_value: Mapped[Decimal] = mapped_column(sa.Numeric(6, 3), nullable=False)
    gpa_points: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(4, 2))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class AssignmentCategory(UUIDMixin, Base):
    __tablename__ = "assignment_categories"

    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    weight: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Assignment(UUIDMixin, Base):
    __tablename__ = "assignments"

    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("assignment_categories.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    points_possible: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 2))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class GradebookEntry(UUIDMixin, Base):
    __tablename__ = "gradebook_entries"

    assignment_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 3))
    submitted_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    late: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_gradebook_student_assignment"),)


class FinalGrade(UUIDMixin, Base):
    __tablename__ = "final_grades"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    grading_period_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("grading_periods.id", ondelete="CASCADE"), nullable=False)
    numeric_grade: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(6, 3))
    letter_grade: Mapped[Optional[str]] = mapped_column(sa.Text)
    credits_earned: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "section_id", "grading_period_id", name="uq_final_grade_period"),)


class GpaCalculation(UUIDMixin, Base):
    __tablename__ = "gpa_calculations"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    term_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    gpa: Mapped[Decimal] = mapped_column(sa.Numeric(4, 3), nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "term_id", name="uq_gpa_term"),)


class ClassRank(UUIDMixin, Base):
    __tablename__ = "class_ranks"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    term_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    rank: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("school_id", "term_id", "student_id", name="uq_class_rank"),)


class ReportCard(UUIDMixin, Base):
    __tablename__ = "report_cards"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    term_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "term_id", name="uq_report_card"),)


class TranscriptLine(UUIDMixin, Base):
    __tablename__ = "transcript_lines"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("courses.id", ondelete="SET NULL"))
    term_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("academic_terms.id", ondelete="SET NULL"))
    credits_attempted: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))
    credits_earned: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))
    final_letter: Mapped[Optional[str]] = mapped_column(sa.Text)
    final_numeric: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(6, 3))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- Testing ----------

class StandardizedTest(UUIDMixin, Base):
    __tablename__ = "standardized_tests"

    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class TestAdministration(UUIDMixin, Base):
    __tablename__ = "test_administrations"

    test_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("standardized_tests.id", ondelete="CASCADE"), nullable=False)
    administration_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    school_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class TestResult(UUIDMixin, Base):
    __tablename__ = "test_results"

    administration_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("test_administrations.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    scale_score: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(8, 2))
    percentile: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))
    performance_level: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("administration_id", "student_id", name="uq_test_result_student"),)


# ---------- Messaging ----------

class Message(UUIDMixin, Base):
    __tablename__ = "messages"

    sender_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("user_accounts.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(sa.Text, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(sa.Text)
    body: Mapped[Optional[str]] = mapped_column(sa.Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class MessageRecipient(Base):
    __tablename__ = "message_recipients"

    message_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    delivery_status: Mapped[Optional[str]] = mapped_column(sa.Text)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- Family Portal ----------

class FamilyPortalAccess(Base):
    __tablename__ = "family_portal_access"

    guardian_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True)
    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    permissions: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- State Reporting / Exports ----------

class StateReportingSnapshot(UUIDMixin, Base):
    __tablename__ = "state_reporting_snapshots"

    as_of_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    scope: Mapped[Optional[str]] = mapped_column(sa.Text)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB())

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class ExportRun(UUIDMixin, Base):
    __tablename__ = "export_runs"

    export_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    ran_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=text("'success'"))
    file_uri: Mapped[Optional[str]] = mapped_column(sa.Text)
    error: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class DataSharingAgreement(UUIDMixin, Base):
    __tablename__ = "data_sharing_agreements"

    vendor: Mapped[str] = mapped_column(sa.Text, nullable=False)
    scope: Mapped[Optional[str]] = mapped_column(sa.Text)
    start_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    end_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- SIS Import / DQ ----------

class SisImportJob(UUIDMixin, Base):
    __tablename__ = "sis_import_jobs"

    source: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=text("'running'"))
    started_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    counts: Mapped[Optional[dict]] = mapped_column(JSONB())
    error_log: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class DataQualityIssue(UUIDMixin, Base):
    __tablename__ = "data_quality_issues"

    entity_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_id: Mapped[Any] = mapped_column(GUID(), nullable=False)
    rule: Mapped[str] = mapped_column(sa.Text, nullable=False)
    severity: Mapped[str] = mapped_column(sa.Text, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(sa.Text)
    detected_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- Fees / Payments ----------

class Fee(UUIDMixin, Base):
    __tablename__ = "fees"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Payment(UUIDMixin, Base):
    __tablename__ = "payments"

    invoice_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    paid_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
    method: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Waiver(UUIDMixin, Base):
    __tablename__ = "waivers"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(sa.Text)
    amount: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(10, 2))
    granted_on: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- Meals ----------

class MealAccount(UUIDMixin, Base):
    __tablename__ = "meal_accounts"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    balance: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", name="uq_meal_account_student"),)


class MealTransaction(UUIDMixin, Base):
    __tablename__ = "meal_transactions"

    account_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("meal_accounts.id", ondelete="CASCADE"), nullable=False)
    transacted_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class MealEligibilityStatus(UUIDMixin, Base):
    __tablename__ = "meal_eligibility_statuses"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False)
    effective_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    effective_end: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- Transportation ----------

class BusRoute(UUIDMixin, Base):
    __tablename__ = "bus_routes"

    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    school_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class BusStop(UUIDMixin, Base):
    __tablename__ = "bus_stops"

    route_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    latitude: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(10, 7))
    longitude: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(10, 7))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class BusStopTime(UUIDMixin, Base):
    __tablename__ = "bus_stop_times"

    route_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False)
    stop_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("bus_stops.id", ondelete="CASCADE"), nullable=False)
    arrival_time: Mapped[time] = mapped_column(sa.Time, nullable=False)
    departure_time: Mapped[Optional[time]] = mapped_column(sa.Time)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("route_id", "stop_id", "arrival_time", name="uq_bus_stop_time"),)


class StudentTransportationAssignment(UUIDMixin, Base):
    __tablename__ = "student_transportation_assignments"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    route_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("bus_routes.id", ondelete="SET NULL"))
    stop_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("bus_stops.id", ondelete="SET NULL"))
    direction: Mapped[Optional[str]] = mapped_column(sa.Text)
    effective_start: Mapped[date] = mapped_column(sa.Date, nullable=False)
    effective_end: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- Library ----------

class LibraryItem(UUIDMixin, Base):
    __tablename__ = "library_items"

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    author: Mapped[Optional[str]] = mapped_column(sa.Text)
    isbn: Mapped[Optional[str]] = mapped_column(sa.Text)
    barcode: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class LibraryCheckout(UUIDMixin, Base):
    __tablename__ = "library_checkouts"

    item_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    checked_out_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    due_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    returned_on: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class LibraryHold(UUIDMixin, Base):
    __tablename__ = "library_holds"

    item_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    placed_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    expires_on: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("item_id", "person_id", name="uq_library_hold"),)


class LibraryFine(UUIDMixin, Base):
    __tablename__ = "library_fines"

    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(sa.Text)
    assessed_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    paid_on: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


# ---------- Health ----------

class HealthProfile(UUIDMixin, Base):
    __tablename__ = "health_profiles"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    allergies: Mapped[Optional[str]] = mapped_column(sa.Text)
    conditions: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", name="uq_health_profile_student"),)


class Immunization(UUIDMixin, Base):
    __tablename__ = "immunizations"

    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class ImmunizationRecord(UUIDMixin, Base):
    __tablename__ = "immunization_records"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    immunization_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("immunizations.id", ondelete="CASCADE"), nullable=False)
    date_administered: Mapped[date] = mapped_column(sa.Date, nullable=False)
    dose_number: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "immunization_id", "date_administered", name="uq_immunization_record"),)


class Medication(UUIDMixin, Base):
    __tablename__ = "medications"

    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class MedicationAdministration(UUIDMixin, Base):
    __tablename__ = "medication_administrations"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    medication_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    administered_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    dose: Mapped[Optional[str]] = mapped_column(sa.Text)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class NurseVisit(UUIDMixin, Base):
    __tablename__ = "nurse_visits"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    visited_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(sa.Text)
    disposition: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class EmergencyContact(UUIDMixin, Base):
    __tablename__ = "emergency_contacts"

    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    contact_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    relationship: Mapped[Optional[str]] = mapped_column(sa.Text)
    phone: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


class Consent(UUIDMixin, Base):
    __tablename__ = "consents"

    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    consent_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    granted: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=text("true"))
    effective_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    expires_on: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("person_id", "consent_type", name="uq_consent_type"),)


# ---------- Audit ----------

class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"

    actor_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("user_accounts.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_id: Mapped[Any] = mapped_column(GUID(), nullable=False)

    # 'metadata' is reserved by SQLAlchemy; map attribute name to column "metadata"
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB())

    occurred_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


# ---------- Billing ----------

class Invoice(UUIDMixin, Base):
    __tablename__ = "invoices"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    issued_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    due_on: Mapped[Optional[date]] = mapped_column(sa.Date)
    status: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=text("'open'"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
