from sqlalchemy import Column, Text, Integer, Boolean, Date, DateTime, Time, Numeric, ForeignKey, UniqueConstraint, Index, text, func
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, GUID, JSONB, TSVectorType



class District(UUIDMixin, Base):
    __tablename__ = "districts"
    name = Column("name", Text, nullable=False, unique=True)
    code = Column("code", Text, unique=True)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)


class School(UUIDMixin, Base):
    __tablename__ = "schools"

    district_id   = Column(GUID(), ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    name          = Column(Text, nullable=False)
    school_code   = Column(Text, unique=True)      # keep if you still use this
    nces_school_id= Column(Text)                   # NEW: map the column added in migrations
    building_code = Column(Text)                   # NEW: map the column added in migrations
    type          = Column(Text)
    timezone      = Column(Text)

    # fix these: use timestamps, not uuid strings
    created_at    = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class AcademicTerm(UUIDMixin, Base):
    __tablename__ = "academic_terms"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    type = Column("type", Text)
    start_date = Column("start_date", Date, nullable=False)
    end_date = Column("end_date", Date, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)


class GradingPeriod(UUIDMixin, Base):
    __tablename__ = "grading_periods"
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    start_date = Column("start_date", Date, nullable=False)
    end_date = Column("end_date", Date, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Calendar(UUIDMixin, Base):
    __tablename__ = "calendars"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class CalendarDay(UUIDMixin, Base):
    __tablename__ = "calendar_days"
    calendar_id = Column("calendar_id", GUID(), ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False)
    date = Column("date", Date, nullable=False)
    day_type = Column("day_type", Text, nullable=False, server_default=text("'instructional'"))
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("calendar_id", "date", name="uq_calendar_day"), )

class BellSchedule(UUIDMixin, Base):
    __tablename__ = "bell_schedules"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Period(UUIDMixin, Base):
    __tablename__ = "periods"
    bell_schedule_id = Column("bell_schedule_id", GUID(), ForeignKey("bell_schedules.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    start_time = Column("start_time", Time, nullable=False)
    end_time = Column("end_time", Time, nullable=False)
    sequence = Column("sequence", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class GradeLevel(UUIDMixin, Base):
    __tablename__ = "grade_levels"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    ordinal = Column("ordinal", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Department(UUIDMixin, Base):
    __tablename__ = "departments"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_department_name"), )

class Subject(UUIDMixin, Base):
    __tablename__ = "subjects"
    department_id = Column("department_id", GUID(), ForeignKey("departments.id", ondelete="SET NULL"))
    name = Column("name", Text, nullable=False)
    code = Column("code", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Course(UUIDMixin, Base):
    __tablename__ = "courses"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column("subject_id", GUID(), ForeignKey("subjects.id", ondelete="SET NULL"))
    name = Column("name", Text, nullable=False)
    code = Column("code", Text)
    credit_hours = Column("credit_hours", Numeric(4,2))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class CourseSection(UUIDMixin, Base):
    __tablename__ = "course_sections"
    course_id = Column("course_id", GUID(), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    section_number = Column("section_number", Text, nullable=False)
    capacity = Column("capacity", Integer)
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("course_id", "term_id", "section_number", name="uq_course_term_section"), )

class Room(UUIDMixin, Base):
    __tablename__ = "rooms"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    capacity = Column("capacity", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Person(UUIDMixin, Base):
    __tablename__ = "persons"
    first_name = Column("first_name", Text, nullable=False)
    last_name = Column("last_name", Text, nullable=False)
    middle_name = Column("middle_name", Text)
    dob = Column("dob", Date)
    email = Column("email", Text)
    phone = Column("phone", Text)
    gender = Column("gender", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Student(UUIDMixin, Base):
    __tablename__ = "students"
    student_number = Column("student_number", Text, unique=True)
    graduation_year = Column("graduation_year", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Staff(UUIDMixin, Base):
    __tablename__ = "staff"
    employee_number = Column("employee_number", Text, unique=True)
    title = Column("title", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Guardian(UUIDMixin, Base):
    __tablename__ = "guardians"
    relationship = Column("relationship", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class UserAccount(UUIDMixin, Base):
    __tablename__ = "user_accounts"
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    username = Column("username", Text, nullable=False, unique=True)
    password_hash = Column("password_hash", Text)
    is_active = Column("is_active", Boolean, nullable=False, server_default=text("true"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Role(UUIDMixin, Base):
    __tablename__ = "roles"
    name = Column("name", Text, nullable=False, unique=True)
    description = Column("description", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Permission(UUIDMixin, Base):
    __tablename__ = "permissions"
    code = Column("code", Text, nullable=False, unique=True)
    description = Column("description", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id = Column("role_id", GUID(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column("permission_id", GUID(), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Address(UUIDMixin, Base):
    __tablename__ = "addresses"
    line1 = Column("line1", Text, nullable=False)
    line2 = Column("line2", Text)
    city = Column("city", Text, nullable=False)
    state = Column("state", Text)
    postal_code = Column("postal_code", Text)
    country = Column("country", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Contact(UUIDMixin, Base):
    __tablename__ = "contacts"
    type = Column("type", Text, nullable=False)
    value = Column("value", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class PersonAddress(Base):
    __tablename__ = "person_addresses"
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    address_id = Column("address_id", GUID(), ForeignKey("addresses.id", ondelete="CASCADE"), primary_key=True)
    is_primary = Column("is_primary", Boolean, nullable=False, server_default=text("false"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class PersonContact(Base):
    __tablename__ = "person_contacts"
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    contact_id = Column("contact_id", GUID(), ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)
    label = Column("label", Text)
    is_primary = Column("is_primary", Boolean, nullable=False, server_default=text("false"))
    is_emergency = Column("is_emergency", Boolean, nullable=False, server_default=text("false"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class StudentGuardian(Base):
    __tablename__ = "student_guardians"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    guardian_id = Column("guardian_id", GUID(), ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True)
    custody = Column("custody", Text)
    is_primary = Column("is_primary", Boolean, nullable=False, server_default=text("false"))
    contact_order = Column("contact_order", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class ExternalId(UUIDMixin, Base):
    __tablename__ = "external_ids"
    entity_type = Column("entity_type", Text, nullable=False)
    entity_id = Column("entity_id", GUID(), nullable=False)
    system = Column("system", Text, nullable=False)
    external_id = Column("external_id", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", "system", name="uq_external_ids"), )

class StudentSchoolEnrollment(UUIDMixin, Base):
    __tablename__ = "student_school_enrollments"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    entry_date = Column("entry_date", Date, nullable=False)
    exit_date = Column("exit_date", Date)
    status = Column("status", Text, nullable=False, server_default=text("'active'"))
    exit_reason = Column("exit_reason", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class StudentProgramEnrollment(UUIDMixin, Base):
    __tablename__ = "student_program_enrollments"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    program_name = Column("program_name", Text, nullable=False)
    start_date = Column("start_date", Date, nullable=False)
    end_date = Column("end_date", Date)
    status = Column("status", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class SpecialEducationCase(UUIDMixin, Base):
    __tablename__ = "special_education_cases"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    eligibility = Column("eligibility", Text)
    case_opened = Column("case_opened", Date)
    case_closed = Column("case_closed", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class IepPlan(UUIDMixin, Base):
    __tablename__ = "iep_plans"
    special_ed_case_id = Column("special_ed_case_id", GUID(), ForeignKey("special_education_cases.id", ondelete="CASCADE"), nullable=False)
    effective_start = Column("effective_start", Date, nullable=False)
    effective_end = Column("effective_end", Date)
    summary = Column("summary", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Accommodation(UUIDMixin, Base):
    __tablename__ = "accommodations"
    iep_plan_id = Column("iep_plan_id", GUID(), ForeignKey("iep_plans.id", ondelete="CASCADE"))
    applies_to = Column("applies_to", Text)
    description = Column("description", Text, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class EllPlan(UUIDMixin, Base):
    __tablename__ = "ell_plans"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    level = Column("level", Text)
    effective_start = Column("effective_start", Date, nullable=False)
    effective_end = Column("effective_end", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Section504Plan(UUIDMixin, Base):
    __tablename__ = "section504_plans"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    effective_start = Column("effective_start", Date, nullable=False)
    effective_end = Column("effective_end", Date)
    summary = Column("summary", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class SectionMeeting(UUIDMixin, Base):
    __tablename__ = "section_meetings"
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column("day_of_week", Integer, nullable=False)
    period_id = Column("period_id", GUID(), ForeignKey("periods.id", ondelete="SET NULL"))
    room_id = Column("room_id", GUID(), ForeignKey("rooms.id", ondelete="SET NULL"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("section_id", "day_of_week", "period_id", name="uq_section_meeting"), )

class TeacherSectionAssignment(UUIDMixin, Base):
    __tablename__ = "teacher_section_assignments"
    staff_id = Column("staff_id", GUID(), ForeignKey("staff.id", ondelete="CASCADE"), nullable=False)
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    role = Column("role", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("staff_id", "section_id", name="uq_teacher_section"), )

class StudentSectionEnrollment(UUIDMixin, Base):
    __tablename__ = "student_section_enrollments"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    added_on = Column("added_on", Date, nullable=False)
    dropped_on = Column("dropped_on", Date)
    seat_time_minutes = Column("seat_time_minutes", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "section_id", name="uq_student_section"), )

class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"
    course_id = Column("course_id", GUID(), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    prereq_course_id = Column("prereq_course_id", GUID(), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class SectionRoomAssignment(UUIDMixin, Base):
    __tablename__ = "section_room_assignments"
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    room_id = Column("room_id", GUID(), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    start_date = Column("start_date", Date)
    end_date = Column("end_date", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("section_id", "room_id", "start_date", name="uq_section_room_range"), )

class AttendanceCode(Base):
    __tablename__ = "attendance_codes"
    code = Column("code", Text, primary_key=True)
    description = Column("description", Text)
    is_present = Column("is_present", Boolean, nullable=False, server_default=text("false"))
    is_excused = Column("is_excused", Boolean, nullable=False, server_default=text("false"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class AttendanceEvent(UUIDMixin, Base):
    __tablename__ = "attendance_events"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_meeting_id = Column("section_meeting_id", GUID(), ForeignKey("section_meetings.id", ondelete="SET NULL"))
    date = Column("date", Date, nullable=False)
    code = Column("code", Text, ForeignKey("attendance_codes.code", ondelete="RESTRICT"), nullable=False)
    minutes = Column("minutes", Integer)
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "date", "section_meeting_id", name="uq_attendance_event"), )

class AttendanceDailySummary(UUIDMixin, Base):
    __tablename__ = "attendance_daily_summary"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    date = Column("date", Date, nullable=False)
    present_minutes = Column("present_minutes", Integer, nullable=False, server_default=text("0"))
    absent_minutes = Column("absent_minutes", Integer, nullable=False, server_default=text("0"))
    tardy_minutes = Column("tardy_minutes", Integer, nullable=False, server_default=text("0"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "date", name="uq_attendance_daily"), )

class GradeScale(UUIDMixin, Base):
    __tablename__ = "grade_scales"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    type = Column("type", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class GradeScaleBand(UUIDMixin, Base):
    __tablename__ = "grade_scale_bands"
    grade_scale_id = Column("grade_scale_id", GUID(), ForeignKey("grade_scales.id", ondelete="CASCADE"), nullable=False)
    label = Column("label", Text, nullable=False)
    min_value = Column("min_value", Numeric(6,3), nullable=False)
    max_value = Column("max_value", Numeric(6,3), nullable=False)
    gpa_points = Column("gpa_points", Numeric(4,2))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class AssignmentCategory(UUIDMixin, Base):
    __tablename__ = "assignment_categories"
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    weight = Column("weight", Numeric(5,2))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Assignment(UUIDMixin, Base):
    __tablename__ = "assignments"
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    category_id = Column("category_id", GUID(), ForeignKey("assignment_categories.id", ondelete="SET NULL"))
    name = Column("name", Text, nullable=False)
    due_date = Column("due_date", Date)
    points_possible = Column("points_possible", Numeric(8,2))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class GradebookEntry(UUIDMixin, Base):
    __tablename__ = "gradebook_entries"
    assignment_id = Column("assignment_id", GUID(), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    score = Column("score", Numeric(8,3))
    submitted_at = Column("submitted_at", DateTime(timezone=True))
    late = Column("late", Boolean, nullable=False, server_default=text("false"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("assignment_id", "student_id", name="uq_gradebook_student_assignment"), )

class FinalGrade(UUIDMixin, Base):
    __tablename__ = "final_grades"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id = Column("section_id", GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    grading_period_id = Column("grading_period_id", GUID(), ForeignKey("grading_periods.id", ondelete="CASCADE"), nullable=False)
    numeric_grade = Column("numeric_grade", Numeric(6,3))
    letter_grade = Column("letter_grade", Text)
    credits_earned = Column("credits_earned", Numeric(5,2))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "section_id", "grading_period_id", name="uq_final_grade_period"), )

class GpaCalculation(UUIDMixin, Base):
    __tablename__ = "gpa_calculations"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    gpa = Column("gpa", Numeric(4,3), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "term_id", name="uq_gpa_term"), )

class ClassRank(UUIDMixin, Base):
    __tablename__ = "class_ranks"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    rank = Column("rank", Integer, nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("school_id", "term_id", "student_id", name="uq_class_rank"), )

class ReportCard(UUIDMixin, Base):
    __tablename__ = "report_cards"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    published_at = Column("published_at", DateTime(timezone=True))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "term_id", name="uq_report_card"), )

class TranscriptLine(UUIDMixin, Base):
    __tablename__ = "transcript_lines"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id = Column("course_id", GUID(), ForeignKey("courses.id", ondelete="SET NULL"))
    term_id = Column("term_id", GUID(), ForeignKey("academic_terms.id", ondelete="SET NULL"))
    credits_attempted = Column("credits_attempted", Numeric(5,2))
    credits_earned = Column("credits_earned", Numeric(5,2))
    final_letter = Column("final_letter", Text)
    final_numeric = Column("final_numeric", Numeric(6,3))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class StandardizedTest(UUIDMixin, Base):
    __tablename__ = "standardized_tests"
    name = Column("name", Text, nullable=False)
    subject = Column("subject", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class TestAdministration(UUIDMixin, Base):
    __tablename__ = "test_administrations"
    test_id = Column("test_id", GUID(), ForeignKey("standardized_tests.id", ondelete="CASCADE"), nullable=False)
    administration_date = Column("administration_date", Date, nullable=False)
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class TestResult(UUIDMixin, Base):
    __tablename__ = "test_results"
    administration_id = Column("administration_id", GUID(), ForeignKey("test_administrations.id", ondelete="CASCADE"), nullable=False)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    scale_score = Column("scale_score", Numeric(8,2))
    percentile = Column("percentile", Numeric(5,2))
    performance_level = Column("performance_level", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("administration_id", "student_id", name="uq_test_result_student"), )

class Message(UUIDMixin, Base):
    __tablename__ = "messages"
    sender_id = Column("sender_id", GUID(), ForeignKey("user_accounts.id", ondelete="SET NULL"))
    channel = Column("channel", Text, nullable=False)
    subject = Column("subject", Text)
    body = Column("body", Text)
    sent_at = Column("sent_at", DateTime(timezone=True))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class MessageRecipient(Base):
    __tablename__ = "message_recipients"
    message_id = Column("message_id", GUID(), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    delivery_status = Column("delivery_status", Text)
    delivered_at = Column("delivered_at", DateTime(timezone=True))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class FamilyPortalAccess(Base):
    __tablename__ = "family_portal_access"
    guardian_id = Column("guardian_id", GUID(), ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True)
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    permissions = Column("permissions", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class StateReportingSnapshot(UUIDMixin, Base):
    __tablename__ = "state_reporting_snapshots"
    as_of_date = Column("as_of_date", Date, nullable=False)
    scope = Column("scope", Text)
    payload = Column("payload", JSONB())
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class ExportRun(UUIDMixin, Base):
    __tablename__ = "export_runs"
    export_name = Column("export_name", Text, nullable=False)
    ran_at = Column("ran_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    status = Column("status", Text, nullable=False, server_default=text("'success'"))
    file_uri = Column("file_uri", Text)
    error = Column("error", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class DataSharingAgreement(UUIDMixin, Base):
    __tablename__ = "data_sharing_agreements"
    vendor = Column("vendor", Text, nullable=False)
    scope = Column("scope", Text)
    start_date = Column("start_date", Date)
    end_date = Column("end_date", Date)
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class SisImportJob(UUIDMixin, Base):
    __tablename__ = "sis_import_jobs"
    source = Column("source", Text, nullable=False)
    status = Column("status", Text, nullable=False, server_default=text("'running'"))
    started_at = Column("started_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    finished_at = Column("finished_at", DateTime(timezone=True))
    counts = Column("counts", JSONB())
    error_log = Column("error_log", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class DataQualityIssue(UUIDMixin, Base):
    __tablename__ = "data_quality_issues"
    entity_type = Column("entity_type", Text, nullable=False)
    entity_id = Column("entity_id", GUID(), nullable=False)
    rule = Column("rule", Text, nullable=False)
    severity = Column("severity", Text, nullable=False)
    details = Column("details", Text)
    detected_at = Column("detected_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)


class Fee(UUIDMixin, Base):
    __tablename__ = "fees"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    amount = Column("amount", Numeric(10,2), nullable=False)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Payment(UUIDMixin, Base):
    __tablename__ = "payments"
    invoice_id = Column("invoice_id", GUID(), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    paid_on = Column("paid_on", Date, nullable=False)
    amount = Column("amount", Numeric(10,2), nullable=False)
    method = Column("method", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Waiver(UUIDMixin, Base):
    __tablename__ = "waivers"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    reason = Column("reason", Text)
    amount = Column("amount", Numeric(10,2))
    granted_on = Column("granted_on", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class MealAccount(UUIDMixin, Base):
    __tablename__ = "meal_accounts"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    balance = Column("balance", Numeric(10,2), nullable=False, server_default=text("0"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", name="uq_meal_account_student"), )

class MealTransaction(UUIDMixin, Base):
    __tablename__ = "meal_transactions"
    account_id = Column("account_id", GUID(), ForeignKey("meal_accounts.id", ondelete="CASCADE"), nullable=False)
    transacted_at = Column("transacted_at", DateTime(timezone=True), nullable=False)
    amount = Column("amount", Numeric(10,2), nullable=False)
    description = Column("description", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class MealEligibilityStatus(UUIDMixin, Base):
    __tablename__ = "meal_eligibility_statuses"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    status = Column("status", Text, nullable=False)
    effective_start = Column("effective_start", Date, nullable=False)
    effective_end = Column("effective_end", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)


class BusRoute(UUIDMixin, Base):
    __tablename__ = "bus_routes"
    name = Column("name", Text, nullable=False)
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="SET NULL"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class BusStop(UUIDMixin, Base):
    __tablename__ = "bus_stops"
    route_id = Column("route_id", GUID(), ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False)
    name = Column("name", Text, nullable=False)
    latitude = Column("latitude", Numeric(10,7))
    longitude = Column("longitude", Numeric(10,7))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class BusStopTime(UUIDMixin, Base):
    __tablename__ = "bus_stop_times"
    route_id = Column("route_id", GUID(), ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False)
    stop_id = Column("stop_id", GUID(), ForeignKey("bus_stops.id", ondelete="CASCADE"), nullable=False)
    arrival_time = Column("arrival_time", Time, nullable=False)
    departure_time = Column("departure_time", Time)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("route_id", "stop_id", "arrival_time", name="uq_bus_stop_time"), )

class StudentTransportationAssignment(UUIDMixin, Base):
    __tablename__ = "student_transportation_assignments"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    route_id = Column("route_id", GUID(), ForeignKey("bus_routes.id", ondelete="SET NULL"))
    stop_id = Column("stop_id", GUID(), ForeignKey("bus_stops.id", ondelete="SET NULL"))
    direction = Column("direction", Text)
    effective_start = Column("effective_start", Date, nullable=False)
    effective_end = Column("effective_end", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class LibraryItem(UUIDMixin, Base):
    __tablename__ = "library_items"
    school_id = Column("school_id", GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    title = Column("title", Text, nullable=False)
    author = Column("author", Text)
    isbn = Column("isbn", Text)
    barcode = Column("barcode", Text, unique=True)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class LibraryCheckout(UUIDMixin, Base):
    __tablename__ = "library_checkouts"
    item_id = Column("item_id", GUID(), ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False)
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    checked_out_on = Column("checked_out_on", Date, nullable=False)
    due_on = Column("due_on", Date, nullable=False)
    returned_on = Column("returned_on", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class LibraryHold(UUIDMixin, Base):
    __tablename__ = "library_holds"
    item_id = Column("item_id", GUID(), ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False)
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    placed_on = Column("placed_on", Date, nullable=False)
    expires_on = Column("expires_on", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("item_id", "person_id", name="uq_library_hold"), )

class LibraryFine(UUIDMixin, Base):
    __tablename__ = "library_fines"
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    amount = Column("amount", Numeric(10,2), nullable=False)
    reason = Column("reason", Text)
    assessed_on = Column("assessed_on", Date, nullable=False)
    paid_on = Column("paid_on", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class HealthProfile(UUIDMixin, Base):
    __tablename__ = "health_profiles"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    allergies = Column("allergies", Text)
    conditions = Column("conditions", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", name="uq_health_profile_student"), )

class Immunization(UUIDMixin, Base):
    __tablename__ = "immunizations"
    name = Column("name", Text, nullable=False)
    code = Column("code", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class ImmunizationRecord(UUIDMixin, Base):
    __tablename__ = "immunization_records"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    immunization_id = Column("immunization_id", GUID(), ForeignKey("immunizations.id", ondelete="CASCADE"), nullable=False)
    date_administered = Column("date_administered", Date, nullable=False)
    dose_number = Column("dose_number", Integer)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("student_id", "immunization_id", "date_administered", name="uq_immunization_record"), )

class Medication(UUIDMixin, Base):
    __tablename__ = "medications"
    name = Column("name", Text, nullable=False)
    instructions = Column("instructions", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class MedicationAdministration(UUIDMixin, Base):
    __tablename__ = "medication_administrations"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    medication_id = Column("medication_id", GUID(), ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    administered_at = Column("administered_at", DateTime(timezone=True), nullable=False)
    dose = Column("dose", Text)
    notes = Column("notes", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class NurseVisit(UUIDMixin, Base):
    __tablename__ = "nurse_visits"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    visited_at = Column("visited_at", DateTime(timezone=True), nullable=False)
    reason = Column("reason", Text)
    disposition = Column("disposition", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class EmergencyContact(UUIDMixin, Base):
    __tablename__ = "emergency_contacts"
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    contact_name = Column("contact_name", Text, nullable=False)
    relationship = Column("relationship", Text)
    phone = Column("phone", Text)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

class Consent(UUIDMixin, Base):
    __tablename__ = "consents"
    person_id = Column("person_id", GUID(), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    consent_type = Column("consent_type", Text, nullable=False)
    granted = Column("granted", Boolean, nullable=False, server_default=text("true"))
    effective_date = Column("effective_date", Date, nullable=False)
    expires_on = Column("expires_on", Date)
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    __table_args__ = (UniqueConstraint("person_id", "consent_type", name="uq_consent_type"), )


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"
    actor_id = Column(GUID(), ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True)
    action = Column(Text, nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(GUID(), nullable=False)

    # NOTE: 'metadata' is reserved by SQLAlchemy's Declarative API.
    # Use a different *attribute* name and map it to the 'metadata' column name.
    metadata_ = Column("metadata", JSONB(), nullable=True)

    occurred_at = Column(DateTime(timezone=True), nullable=False, default=lambda: str(uuid.uuid4()))

class Invoice(UUIDMixin, Base):
    __tablename__ = "invoices"
    student_id = Column("student_id", GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    issued_on = Column("issued_on", Date, nullable=False)
    due_on = Column("due_on", Date)
    status = Column("status", Text, nullable=False, server_default=text("'open'"))
    created_at = Column("created_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)
    updated_at = Column("updated_at", DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False)

