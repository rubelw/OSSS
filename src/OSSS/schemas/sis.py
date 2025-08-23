from __future__ import annotations

from datetime import date, time, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


# Base -----------------------------------------------------------------

class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- District / School / Calendar ----------

class DistrictOut(ORMBase):
    id: str
    name: str
    code: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SchoolOut(ORMBase):
    id: str
    district_id: str
    name: str
    school_code: Optional[str] = None
    nces_school_id: Optional[str] = None
    building_code: Optional[str] = None
    type: Optional[str] = None
    timezone: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AcademicTermOut(ORMBase):
    id: str
    school_id: str
    name: str
    type: Optional[str] = None
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime


class GradingPeriodOut(ORMBase):
    id: str
    term_id: str
    name: str
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime


class CalendarOut(ORMBase):
    id: str
    school_id: str
    name: str
    created_at: datetime
    updated_at: datetime


class CalendarDayOut(ORMBase):
    id: str
    calendar_id: str
    date: date
    day_type: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BellScheduleOut(ORMBase):
    id: str
    school_id: str
    name: str
    created_at: datetime
    updated_at: datetime


class PeriodOut(ORMBase):
    id: str
    bell_schedule_id: str
    name: str
    start_time: time
    end_time: time
    sequence: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class GradeLevelOut(ORMBase):
    id: str
    school_id: str
    name: str
    ordinal: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class DepartmentOut(ORMBase):
    id: str
    school_id: str
    name: str
    created_at: datetime
    updated_at: datetime


class SubjectOut(ORMBase):
    id: str
    department_id: Optional[str] = None
    name: str
    code: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CourseOut(ORMBase):
    id: str
    school_id: str
    subject_id: Optional[str] = None
    name: str
    code: Optional[str] = None
    credit_hours: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class CourseSectionOut(ORMBase):
    id: str
    course_id: str
    term_id: str
    section_number: str
    capacity: Optional[int] = None
    school_id: str
    created_at: datetime
    updated_at: datetime


class RoomOut(ORMBase):
    id: str
    school_id: str
    name: str
    capacity: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# ---------- People / Accounts ----------

class PersonOut(ORMBase):
    id: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    dob: Optional[date] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StudentOut(ORMBase):
    id: str
    student_number: Optional[str] = None
    graduation_year: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class StaffOut(ORMBase):
    id: str
    employee_number: Optional[str] = None
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GuardianOut(ORMBase):
    id: str
    relationship: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class UserAccountOut(ORMBase):
    id: str
    person_id: str
    username: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RoleOut(ORMBase):
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PermissionOut(ORMBase):
    id: str
    code: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class RolePermissionOut(ORMBase):
    role_id: str
    permission_id: str
    created_at: datetime
    updated_at: datetime


# ---------- Addresses / Contacts ----------

class AddressOut(ORMBase):
    id: str
    line1: str
    line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ContactOut(ORMBase):
    id: str
    type: str
    value: str
    created_at: datetime
    updated_at: datetime


class PersonAddressOut(ORMBase):
    person_id: str
    address_id: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class PersonContactOut(ORMBase):
    person_id: str
    contact_id: str
    label: Optional[str] = None
    is_primary: bool
    is_emergency: bool
    created_at: datetime
    updated_at: datetime


class StudentGuardianOut(ORMBase):
    student_id: str
    guardian_id: str
    custody: Optional[str] = None
    is_primary: bool
    contact_order: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ExternalIdOut(ORMBase):
    id: str
    entity_type: str
    entity_id: str
    system: str
    external_id: str
    created_at: datetime
    updated_at: datetime


# ---------- Enrollments / Programs ----------

class StudentSchoolEnrollmentOut(ORMBase):
    id: str
    student_id: str
    school_id: str
    entry_date: date
    exit_date: Optional[date] = None
    status: str
    exit_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StudentProgramEnrollmentOut(ORMBase):
    id: str
    student_id: str
    program_name: str
    start_date: date
    end_date: Optional[date] = None
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------- Special Education / Support Plans ----------

class SpecialEducationCaseOut(ORMBase):
    id: str
    student_id: str
    eligibility: Optional[str] = None
    case_opened: Optional[date] = None
    case_closed: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class IepPlanOut(ORMBase):
    id: str
    special_ed_case_id: str
    effective_start: date
    effective_end: Optional[date] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AccommodationOut(ORMBase):
    id: str
    iep_plan_id: Optional[str] = None
    applies_to: Optional[str] = None
    description: str
    created_at: datetime
    updated_at: datetime


class EllPlanOut(ORMBase):
    id: str
    student_id: str
    level: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class Section504PlanOut(ORMBase):
    id: str
    student_id: str
    effective_start: date
    effective_end: Optional[date] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------- Scheduling ----------

class SectionMeetingOut(ORMBase):
    id: str
    section_id: str
    day_of_week: int
    period_id: Optional[str] = None
    room_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TeacherSectionAssignmentOut(ORMBase):
    id: str
    staff_id: str
    section_id: str
    role: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StudentSectionEnrollmentOut(ORMBase):
    id: str
    student_id: str
    section_id: str
    added_on: date
    dropped_on: Optional[date] = None
    seat_time_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class CoursePrerequisiteOut(ORMBase):
    course_id: str
    prereq_course_id: str
    created_at: datetime
    updated_at: datetime


class SectionRoomAssignmentOut(ORMBase):
    id: str
    section_id: str
    room_id: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


# ---------- Attendance ----------

class AttendanceCodeOut(ORMBase):
    code: str
    description: Optional[str] = None
    is_present: bool
    is_excused: bool
    created_at: datetime
    updated_at: datetime


class AttendanceEventOut(ORMBase):
    id: str
    student_id: str
    section_meeting_id: Optional[str] = None
    date: date
    code: str
    minutes: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AttendanceDailySummaryOut(ORMBase):
    id: str
    student_id: str
    date: date
    present_minutes: int
    absent_minutes: int
    tardy_minutes: int
    created_at: datetime
    updated_at: datetime


# ---------- Grading ----------

class GradeScaleOut(ORMBase):
    id: str
    school_id: str
    name: str
    type: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class GradeScaleBandOut(ORMBase):
    id: str
    grade_scale_id: str
    label: str
    min_value: Decimal
    max_value: Decimal
    gpa_points: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class AssignmentCategoryOut(ORMBase):
    id: str
    section_id: str
    name: str
    weight: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class AssignmentOut(ORMBase):
    id: str
    section_id: str
    category_id: Optional[str] = None
    name: str
    due_date: Optional[date] = None
    points_possible: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class GradebookEntryOut(ORMBase):
    id: str
    assignment_id: str
    student_id: str
    score: Optional[Decimal] = None
    submitted_at: Optional[datetime] = None
    late: bool
    created_at: datetime
    updated_at: datetime


class FinalGradeOut(ORMBase):
    id: str
    student_id: str
    section_id: str
    grading_period_id: str
    numeric_grade: Optional[Decimal] = None
    letter_grade: Optional[str] = None
    credits_earned: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class GpaCalculationOut(ORMBase):
    id: str
    student_id: str
    term_id: str
    gpa: Decimal
    created_at: datetime
    updated_at: datetime


class ClassRankOut(ORMBase):
    id: str
    school_id: str
    term_id: str
    student_id: str
    rank: int
    created_at: datetime
    updated_at: datetime


class ReportCardOut(ORMBase):
    id: str
    student_id: str
    term_id: str
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TranscriptLineOut(ORMBase):
    id: str
    student_id: str
    course_id: Optional[str] = None
    term_id: Optional[str] = None
    credits_attempted: Optional[Decimal] = None
    credits_earned: Optional[Decimal] = None
    final_letter: Optional[str] = None
    final_numeric: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


# ---------- Testing ----------

class StandardizedTestOut(ORMBase):
    id: str
    name: str
    subject: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TestAdministrationOut(ORMBase):
    id: str
    test_id: str
    administration_date: date
    school_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TestResultOut(ORMBase):
    id: str
    administration_id: str
    student_id: str
    scale_score: Optional[Decimal] = None
    percentile: Optional[Decimal] = None
    performance_level: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------- Messaging ----------

class MessageOut(ORMBase):
    id: str
    sender_id: Optional[str] = None
    channel: str
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class MessageRecipientOut(ORMBase):
    message_id: str
    person_id: str
    delivery_status: Optional[str] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ---------- Family Portal ----------

class FamilyPortalAccessOut(ORMBase):
    guardian_id: str
    student_id: str
    permissions: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------- State Reporting / Exports ----------

class StateReportingSnapshotOut(ORMBase):
    id: str
    as_of_date: date
    scope: Optional[str] = None
    payload: Optional[dict] = None
    created_at: datetime
    updated_at: datetime


class ExportRunOut(ORMBase):
    id: str
    export_name: str
    ran_at: datetime
    status: str
    file_uri: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DataSharingAgreementOut(ORMBase):
    id: str
    vendor: str
    scope: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------- SIS Import / DQ ----------

class SisImportJobOut(ORMBase):
    id: str
    source: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    counts: Optional[dict] = None
    error_log: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DataQualityIssueOut(ORMBase):
    id: str
    entity_type: str
    entity_id: str
    rule: str
    severity: str
    details: Optional[str] = None
    detected_at: datetime
    created_at: datetime
    updated_at: datetime


# ---------- Fees / Payments ----------

class FeeOut(ORMBase):
    id: str
    school_id: str
    name: str
    amount: Decimal
    created_at: datetime
    updated_at: datetime


class PaymentOut(ORMBase):
    id: str
    invoice_id: str
    paid_on: date
    amount: Decimal
    method: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WaiverOut(ORMBase):
    id: str
    student_id: str
    reason: Optional[str] = None
    amount: Optional[Decimal] = None
    granted_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime


# ---------- Meals ----------

class MealAccountOut(ORMBase):
    id: str
    student_id: str
    balance: Decimal
    created_at: datetime
    updated_at: datetime


class MealTransactionOut(ORMBase):
    id: str
    account_id: str
    transacted_at: datetime
    amount: Decimal
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MealEligibilityStatusOut(ORMBase):
    id: str
    student_id: str
    status: str
    effective_start: date
    effective_end: Optional[date] = None
    created_at: datetime
    updated_at: datetime


# ---------- Transportation ----------

class BusRouteOut(ORMBase):
    id: str
    name: str
    school_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BusStopOut(ORMBase):
    id: str
    route_id: str
    name: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


class BusStopTimeOut(ORMBase):
    id: str
    route_id: str
    stop_id: str
    arrival_time: time
    departure_time: Optional[time] = None
    created_at: datetime
    updated_at: datetime


class StudentTransportationAssignmentOut(ORMBase):
    id: str
    student_id: str
    route_id: Optional[str] = None
    stop_id: Optional[str] = None
    direction: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None
    created_at: datetime
    updated_at: datetime


# ---------- Library ----------

class LibraryItemOut(ORMBase):
    id: str
    school_id: str
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    barcode: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class LibraryCheckoutOut(ORMBase):
    id: str
    item_id: str
    person_id: str
    checked_out_on: date
    due_on: date
    returned_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class LibraryHoldOut(ORMBase):
    id: str
    item_id: str
    person_id: str
    placed_on: date
    expires_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class LibraryFineOut(ORMBase):
    id: str
    person_id: str
    amount: Decimal
    reason: Optional[str] = None
    assessed_on: date
    paid_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime


# ---------- Health ----------

class HealthProfileOut(ORMBase):
    id: str
    student_id: str
    allergies: Optional[str] = None
    conditions: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ImmunizationOut(ORMBase):
    id: str
    name: str
    code: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ImmunizationRecordOut(ORMBase):
    id: str
    student_id: str
    immunization_id: str
    date_administered: date
    dose_number: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class MedicationOut(ORMBase):
    id: str
    name: str
    instructions: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MedicationAdministrationOut(ORMBase):
    id: str
    student_id: str
    medication_id: str
    administered_at: datetime
    dose: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class NurseVisitOut(ORMBase):
    id: str
    student_id: str
    visited_at: datetime
    reason: Optional[str] = None
    disposition: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class EmergencyContactOut(ORMBase):
    id: str
    person_id: str
    contact_name: str
    relationship: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ConsentOut(ORMBase):
    id: str
    person_id: str
    consent_type: str
    granted: bool
    effective_date: date
    expires_on: Optional[date] = None
    created_at: datetime
    updated_at: datetime


# ---------- Audit ----------

class AuditLogOut(ORMBase):
    id: str
    actor_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    metadata_: Optional[dict] = None
    occurred_at: datetime


# ---------- Billing ----------

class InvoiceOut(ORMBase):
    id: str
    student_id: str
    issued_on: date
    due_on: Optional[date] = None
    status: str
    created_at: datetime
    updated_at: datetime

# ---------- Discipline / Behavior ----------

class BehaviorCodeOut(ORMBase):
    code: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
