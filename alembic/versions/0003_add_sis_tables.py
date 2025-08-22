"""
Initial SIS schema (core + optional modules)

Generated: 2025-08-12
Target DB: PostgreSQL

Notes
- UUID PKs with server_default=gen_random_uuid() (enable pgcrypto or replace with uuid_generate_v4())
- created_at/updated_at timestamps on most tables
- Soft deletes omitted for simplicity; add deleted_at if needed
- Many optional attributes trimmed for brevity; extend as your needs evolve
- Order of creation respects FK dependencies; downgrade reverses

"""
from alembic import op
import uuid
from sqlalchemy.dialects import postgresql as psql
import sqlalchemy as sa
from sqlalchemy import text

# Pull the shims from your app (preferred)
try:
    from app.models.base import GUID, JSONB, TSVectorType  # GUID/JSONB are TypeDecorator; TSVectorType is PG TSVECTOR or Text
except Exception:
    # Fallbacks, in case direct import isn't available during migration
    import uuid
    from sqlalchemy.types import TypeDecorator, CHAR

    class GUID(TypeDecorator):
        impl = CHAR
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import UUID as PGUUID
                return dialect.type_descriptor(PGUUID(as_uuid=True))
            return dialect.type_descriptor(sa.CHAR(36))
        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(str(value))
            return str(value)
        def process_result_value(self, value, dialect):
            return None if value is None else uuid.UUID(value)

    # JSONB shim: real JSONB on PG, JSON elsewhere
    try:
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
    except Exception:
        PGJSONB = None

    class JSONB(TypeDecorator):
        impl = sa.JSON
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql" and PGJSONB is not None:
                return dialect.type_descriptor(PGJSONB())
            return dialect.type_descriptor(sa.JSON())

    # TSVECTOR shim: real TSVECTOR on PG, TEXT elsewhere
    try:
        from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
        class TSVectorType(PG_TSVECTOR):  # ok to subclass for clarity
            pass
    except Exception:
        class TSVectorType(sa.Text):  # type: ignore
            pass

# Alembic identifiers
# revision identifiers, used by Alembic.
revision = "0003_add_sis_tables"
down_revision = "0002_add_table"
branch_labels = None
depends_on = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    uuid_col = (
        sa.Column("id", sa.String(36), primary_key=True,
                  server_default=text("gen_random_uuid()"))  # PG only
        if is_pg else
        sa.Column("id", sa.CHAR(36), primary_key=True)  # SQLite: no server_default
    )

    # --- Extensions (optional) ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # for gen_random_uuid()

    # ==================
    # Core & Identity
    # ==================
    op.create_table(
        "districts",
        uuid_col,
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("code", sa.Text(), nullable=True, unique=True),
        *_timestamps(),
    )

    op.create_table(
        "schools",
        uuid_col,
        sa.Column("district_id", sa.String(36), sa.ForeignKey("districts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("school_code", sa.Text(), nullable=True, unique=True),
        sa.Column("type", sa.Text(), nullable=True),  # elementary, middle, high
        sa.Column("timezone", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_schools_district", "schools", ["district_id"])

    op.create_table(
        "academic_terms",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),  # 2025-2026, Semester 1, etc
        sa.Column("type", sa.Text(), nullable=True),  # year, semester, trimester
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_terms_school", "academic_terms", ["school_id"])

    op.create_table(
        "grading_periods",
        uuid_col,
        sa.Column("term_id", sa.String(36), sa.ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "calendars",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),  # e.g., Student Days
        *_timestamps(),
    )

    op.create_table(
        "calendar_days",
        uuid_col,
        sa.Column("calendar_id", sa.String(36), sa.ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("day_type", sa.Text(), nullable=False, server_default=sa.text("'instructional'")),  # instructional, holiday, pd, etc.
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("calendar_id", "date", name="uq_calendar_day")
    )

    op.create_table(
        "bell_schedules",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),  # Regular, Early Release
        *_timestamps(),
    )

    op.create_table(
        "periods",
        uuid_col,
        sa.Column("bell_schedule_id", sa.String(36), sa.ForeignKey("bell_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Time(timezone=False), nullable=False),
        sa.Column("end_time", sa.Time(timezone=False), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "grade_levels",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),  # Grade 1, 2, 3 ...
        sa.Column("ordinal", sa.Integer(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "departments",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("school_id", "name", name="uq_department_name")
    )

    op.create_table(
        "subjects",
        uuid_col,
        sa.Column("department_id", sa.String(36), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "courses",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.String(36), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        sa.Column("credit_hours", sa.Numeric(4,2), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "course_sections",
        uuid_col,
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", sa.String(36), sa.ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_number", sa.Text(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("course_id", "term_id", "section_number", name="uq_course_term_section")
    )

    op.create_table(
        "rooms",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "persons",
        uuid_col,
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("middle_name", sa.Text(), nullable=True),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("gender", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "students",
        uuid_col,
        sa.Column("student_number", sa.Text(), nullable=True, unique=True),
        sa.Column("graduation_year", sa.Integer(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "staff",
        uuid_col,
        sa.Column("employee_number", sa.Text(), nullable=True, unique=True),
        sa.Column("title", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "guardians",
        uuid_col,
        sa.Column("relationship", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "user_accounts",
        uuid_col,
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("username", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_timestamps(),
    )

    op.create_table(
        "roles",
        uuid_col,
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "permissions",
        uuid_col,
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.String(36), sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
        *_timestamps(),
    )

    op.create_table(
        "addresses",
        uuid_col,
        sa.Column("line1", sa.Text(), nullable=False),
        sa.Column("line2", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=True),
        sa.Column("postal_code", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "contacts",
        uuid_col,
        sa.Column("type", sa.Text(), nullable=False),  # phone, email, etc
        sa.Column("value", sa.Text(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "person_addresses",
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("address_id", sa.String(36), sa.ForeignKey("addresses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
    )

    op.create_table(
        "person_contacts",
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("contact_id", sa.String(36), sa.ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_emergency", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
    )

    op.create_table(
        "student_guardians",
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("guardian_id", sa.String(36), sa.ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("custody", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("contact_order", sa.Integer(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "external_ids",
        uuid_col,
        sa.Column("entity_type", sa.Text(), nullable=False),  # e.g., person, student, course
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("system", sa.Text(), nullable=False),  # state, vendor name
        sa.Column("external_id", sa.Text(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("entity_type", "entity_id", "system", name="uq_external_ids"),
    )

    # ==================
    # Enrollment & Programs
    # ==================
    op.create_table(
        "student_school_enrollments",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("exit_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("exit_reason", sa.Text(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_enroll_student_school", "student_school_enrollments", ["student_id", "school_id"])

    op.create_table(
        "student_program_enrollments",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_name", sa.Text(), nullable=False),  # gifted, title I, after-school, etc.
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "special_education_cases",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("eligibility", sa.Text(), nullable=True),
        sa.Column("case_opened", sa.Date(), nullable=True),
        sa.Column("case_closed", sa.Date(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "iep_plans",
        uuid_col,
        sa.Column("special_ed_case_id", sa.String(36), sa.ForeignKey("special_education_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("effective_start", sa.Date(), nullable=False),
        sa.Column("effective_end", sa.Date(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "accommodations",
        uuid_col,
        sa.Column("iep_plan_id", sa.String(36), sa.ForeignKey("iep_plans.id", ondelete="CASCADE"), nullable=True),
        sa.Column("applies_to", sa.Text(), nullable=True),  # testing, classroom, etc.
        sa.Column("description", sa.Text(), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "ell_plans",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.Text(), nullable=True),
        sa.Column("effective_start", sa.Date(), nullable=False),
        sa.Column("effective_end", sa.Date(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "section504_plans",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("effective_start", sa.Date(), nullable=False),
        sa.Column("effective_end", sa.Date(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        *_timestamps(),
    )

    # ==================
    # Scheduling
    # ==================
    op.create_table(
        "section_meetings",
        uuid_col,
        sa.Column("section_id", sa.String(36), sa.ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),  # 0=Mon..6=Sun
        sa.Column("period_id", sa.String(36), sa.ForeignKey("periods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("section_id", "day_of_week", "period_id", name="uq_section_meeting")
    )

    op.create_table(
        "teacher_section_assignments",
        uuid_col,
        sa.Column("staff_id", sa.String(36), sa.ForeignKey("staff.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", sa.String(36), sa.ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),  # primary, co-teacher, para
        *_timestamps(),
        sa.UniqueConstraint("staff_id", "section_id", name="uq_teacher_section")
    )

    op.create_table(
        "student_section_enrollments",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", sa.String(36), sa.ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_on", sa.Date(), nullable=False),
        sa.Column("dropped_on", sa.Date(), nullable=True),
        sa.Column("seat_time_minutes", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "section_id", name="uq_student_section")
    )

    op.create_table(
        "course_prerequisites",
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("prereq_course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True),
        *_timestamps(),
    )

    op.create_table(
        "section_room_assignments",
        uuid_col,
        sa.Column("section_id", sa.String(36), sa.ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", sa.String(36), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("section_id", "room_id", "start_date", name="uq_section_room_range")
    )

    # ==================
    # Attendance
    # ==================
    op.create_table(
        "attendance_codes",
        sa.Column("code", sa.Text(), primary_key=True),  # present, excused, unexcused, tardy
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_present", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_excused", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
    )

    op.create_table(
        "attendance_events",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_meeting_id", sa.String(36), sa.ForeignKey("section_meetings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("code", sa.Text(), sa.ForeignKey("attendance_codes.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "date", "section_meeting_id", name="uq_attendance_event")
    )

    op.create_table(
        "attendance_daily_summary",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("present_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("absent_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tardy_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "date", name="uq_attendance_daily")
    )

    # ==================
    # Assessment, Grades & Transcripts
    # ==================
    op.create_table(
        "grade_scales",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=True),  # AF, standards-based
        *_timestamps(),
    )

    op.create_table(
        "grade_scale_bands",
        uuid_col,
        sa.Column("grade_scale_id", sa.String(36), sa.ForeignKey("grade_scales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),  # A, B, 4, etc.
        sa.Column("min_value", sa.Numeric(6,3), nullable=False),
        sa.Column("max_value", sa.Numeric(6,3), nullable=False),
        sa.Column("gpa_points", sa.Numeric(4,2), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "assignment_categories",
        uuid_col,
        sa.Column("section_id", sa.String(36), sa.ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("weight", sa.Numeric(5,2), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "assignments",
        uuid_col,
        sa.Column("section_id", sa.String(36), sa.ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("assignment_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("points_possible", sa.Numeric(8,2), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "gradebook_entries",
        uuid_col,
        sa.Column("assignment_id", sa.String(36), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Numeric(8,3), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("late", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        *_timestamps(),
        sa.UniqueConstraint("assignment_id", "student_id", name="uq_gradebook_student_assignment")
    )

    op.create_table(
        "final_grades",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", sa.String(36), sa.ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("grading_period_id", sa.String(36), sa.ForeignKey("grading_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numeric_grade", sa.Numeric(6,3), nullable=True),
        sa.Column("letter_grade", sa.Text(), nullable=True),
        sa.Column("credits_earned", sa.Numeric(5,2), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "section_id", "grading_period_id", name="uq_final_grade_period")
    )

    op.create_table(
        "gpa_calculations",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", sa.String(36), sa.ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gpa", sa.Numeric(4,3), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "term_id", name="uq_gpa_term")
    )

    op.create_table(
        "class_ranks",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", sa.String(36), sa.ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("school_id", "term_id", "student_id", name="uq_class_rank")
    )

    op.create_table(
        "report_cards",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("term_id", sa.String(36), sa.ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "term_id", name="uq_report_card")
    )

    op.create_table(
        "transcript_lines",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("term_id", sa.String(36), sa.ForeignKey("academic_terms.id", ondelete="SET NULL"), nullable=True),
        sa.Column("credits_attempted", sa.Numeric(5,2), nullable=True),
        sa.Column("credits_earned", sa.Numeric(5,2), nullable=True),
        sa.Column("final_letter", sa.Text(), nullable=True),
        sa.Column("final_numeric", sa.Numeric(6,3), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "standardized_tests",
        uuid_col,
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "test_administrations",
        uuid_col,
        sa.Column("test_id", sa.String(36), sa.ForeignKey("standardized_tests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("administration_date", sa.Date(), nullable=False),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "test_results",
        uuid_col,
        sa.Column("administration_id", sa.String(36), sa.ForeignKey("test_administrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scale_score", sa.Numeric(8,2), nullable=True),
        sa.Column("percentile", sa.Numeric(5,2), nullable=True),
        sa.Column("performance_level", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("administration_id", "student_id", name="uq_test_result_student")
    )

    # ==================
    # Behavior & Discipline
    # ==================
    op.create_table(
        "behavior_codes",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "consequence_types",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "incidents",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("behavior_code", sa.Text(), sa.ForeignKey("behavior_codes.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "incident_participants",
        uuid_col,
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),  # offender, victim, witness
        *_timestamps(),
        sa.UniqueConstraint("incident_id", "person_id", name="uq_incident_person")
    )

    op.create_table(
        "consequences",
        uuid_col,
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_id", sa.String(36), sa.ForeignKey("incident_participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consequence_code", sa.Text(), sa.ForeignKey("consequence_types.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "behavior_interventions",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intervention", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        *_timestamps(),
    )

    # ==================
    # Health & Safety
    # ==================
    op.create_table(
        "health_profiles",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("allergies", sa.Text(), nullable=True),
        sa.Column("conditions", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("student_id", name="uq_health_profile_student")
    )

    op.create_table(
        "immunizations",
        uuid_col,
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "immunization_records",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("immunization_id", sa.String(36), sa.ForeignKey("immunizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date_administered", sa.Date(), nullable=False),
        sa.Column("dose_number", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("student_id", "immunization_id", "date_administered", name="uq_immunization_record")
    )

    op.create_table(
        "medications",
        uuid_col,
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "medication_administrations",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("medication_id", sa.String(36), sa.ForeignKey("medications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("administered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dose", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "nurse_visits",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("disposition", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "emergency_contacts",
        uuid_col,
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_name", sa.Text(), nullable=False),
        sa.Column("relationship", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "consents",
        uuid_col,
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("consent_type", sa.Text(), nullable=False),  # media_release, field_trip
        sa.Column("granted", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("person_id", "consent_type", name="uq_consent_type")
    )

    # ==================
    # Fees, Meals, Transportation, Library
    # ==================
    op.create_table(
        "fees",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(10,2), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "invoices",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        *_timestamps(),
    )

    op.create_table(
        "payments",
        uuid_col,
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(10,2), nullable=False),
        sa.Column("method", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "waivers",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(10,2), nullable=True),
        sa.Column("granted_on", sa.Date(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "meal_accounts",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance", sa.Numeric(10,2), nullable=False, server_default=sa.text("0")),
        *_timestamps(),
        sa.UniqueConstraint("student_id", name="uq_meal_account_student")
    )

    op.create_table(
        "meal_transactions",
        uuid_col,
        sa.Column("account_id", sa.String(36), sa.ForeignKey("meal_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("transacted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(10,2), nullable=False),  # negative=debit, positive=credit
        sa.Column("description", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "meal_eligibility_statuses",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),  # free, reduced, paid
        sa.Column("effective_start", sa.Date(), nullable=False),
        sa.Column("effective_end", sa.Date(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "bus_routes",
        uuid_col,
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "bus_stops",
        uuid_col,
        sa.Column("route_id", sa.String(36), sa.ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Numeric(10,7), nullable=True),
        sa.Column("longitude", sa.Numeric(10,7), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "bus_stop_times",
        uuid_col,
        sa.Column("route_id", sa.String(36), sa.ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stop_id", sa.String(36), sa.ForeignKey("bus_stops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("arrival_time", sa.Time(), nullable=False),
        sa.Column("departure_time", sa.Time(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("route_id", "stop_id", "arrival_time", name="uq_bus_stop_time")
    )

    op.create_table(
        "student_transportation_assignments",
        uuid_col,
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("route_id", sa.String(36), sa.ForeignKey("bus_routes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stop_id", sa.String(36), sa.ForeignKey("bus_stops.id", ondelete="SET NULL"), nullable=True),
        sa.Column("direction", sa.Text(), nullable=True),  # AM / PM / BOTH
        sa.Column("effective_start", sa.Date(), nullable=False),
        sa.Column("effective_end", sa.Date(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "library_items",
        uuid_col,
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=True),
        sa.Column("isbn", sa.Text(), nullable=True),
        sa.Column("barcode", sa.Text(), nullable=True, unique=True),
        *_timestamps(),
    )

    op.create_table(
        "library_checkouts",
        uuid_col,
        sa.Column("item_id", sa.String(36), sa.ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checked_out_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("returned_on", sa.Date(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "library_holds",
        uuid_col,
        sa.Column("item_id", sa.String(36), sa.ForeignKey("library_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("placed_on", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("item_id", "person_id", name="uq_library_hold")
    )

    op.create_table(
        "library_fines",
        uuid_col,
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(10,2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("assessed_on", sa.Date(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=True),
        *_timestamps(),
    )

    # ==================
    # Communication & Engagement
    # ==================
    op.create_table(
        "messages",
        uuid_col,
        sa.Column("sender_id", sa.String(36), sa.ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),  # email, sms, in_app
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "message_recipients",
        sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("delivery_status", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "family_portal_access",
        sa.Column("guardian_id", sa.String(36), sa.ForeignKey("guardians.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permissions", sa.Text(), nullable=True),
        *_timestamps(),
    )



    # ==================
    # State Reporting & Auditing
    # ==================
    op.create_table(
        "state_reporting_snapshots",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("payload", JSONB(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "export_runs",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("export_name", sa.Text(), nullable=False),
        sa.Column("ran_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'success'")),
        sa.Column("file_uri", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "audit_logs",
        uuid_col,
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("user_accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", GUID(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        *_timestamps(),
    )

    op.create_table(
        "data_sharing_agreements",
        uuid_col,
        sa.Column("vendor", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
    )

    # ==================
    # Analytics & ETL Support
    # ==================
    op.create_table(
        "sis_import_jobs",
        uuid_col,
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("counts", JSONB(), nullable=True),
        sa.Column("error_log", sa.Text(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "data_quality_issues",
        uuid_col,
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),  # info, warning, error
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        *_timestamps(),
    )



def downgrade() -> None:
    # Drop in reverse dependency order
    for table in [
        "data_quality_issues",
        "sis_import_jobs",
        "data_sharing_agreements",
        "audit_logs",
        "export_runs",
        "state_reporting_snapshots",
        "document_links",
        "family_portal_access",
        "message_recipients",
        "messages",
        "library_fines",
        "library_holds",
        "library_checkouts",
        "library_items",
        "student_transportation_assignments",
        "bus_stop_times",
        "bus_stops",
        "bus_routes",
        "meal_eligibility_statuses",
        "meal_transactions",
        "meal_accounts",
        "waivers",
        "payments",
        "invoices",
        "fees",
        "consents",
        "emergency_contacts",
        "nurse_visits",
        "medication_administrations",
        "medications",
        "immunization_records",
        "immunizations",
        "health_profiles",
        "behavior_interventions",
        "consequences",
        "incident_participants",
        "incidents",
        "consequence_types",
        "behavior_codes",
        "test_results",
        "test_administrations",
        "standardized_tests",
        "transcript_lines",
        "report_cards",
        "class_ranks",
        "gpa_calculations",
        "final_grades",
        "gradebook_entries",
        "assignments",
        "assignment_categories",
        "grade_scale_bands",
        "grade_scales",
        "attendance_daily_summary",
        "attendance_events",
        "attendance_codes",
        "section_room_assignments",
        "course_prerequisites",
        "student_section_enrollments",
        "teacher_section_assignments",
        "section_meetings",
        "section504_plans",
        "ell_plans",
        "accommodations",
        "iep_plans",
        "special_education_cases",
        "student_program_enrollments",
        "student_school_enrollments",
        "external_ids",
        "student_guardians",
        "person_contacts",
        "person_addresses",
        "contacts",
        "addresses",
        "role_permissions",
        "permissions",
        "roles",
        "user_accounts",
        "guardians",
        "staff",
        "students",
        "persons",
        "rooms",
        "course_sections",
        "courses",
        "subjects",
        "departments",
        "grade_levels",
        "periods",
        "bell_schedules",
        "calendar_days",
        "calendars",
        "grading_periods",
        "academic_terms",
        "schools",
        "districts",
    ]:
        op.drop_table(table)
    op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
