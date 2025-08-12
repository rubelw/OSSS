from __future__ import annotations
from typing import Optional, Any, List
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal


from pydantic import BaseModel, ConfigDict, EmailStr

# ---------------------------------------------------------------------------
# Helpers / Base
# ---------------------------------------------------------------------------

class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class WithID(ORMBase):
    id: UUID

class WithTimestamps(ORMBase):
    created_at: datetime

# ---------------------------------------------------------------------------
# Users (local table)
# ---------------------------------------------------------------------------

class UserCreate(ORMBase):
    username: str
    email: EmailStr

class UserRead(WithID):
    username: str
    email: EmailStr
    created_at: datetime

# ---------------------------------------------------------------------------
# Core (shared)
# ---------------------------------------------------------------------------

class OrganizationCreate(ORMBase):
    name: str

class OrganizationRead(WithID, WithTimestamps):
    name: str

class BodyCreate(ORMBase):
    org_id: UUID
    name: str
    type: Optional[str] = None

class BodyRead(WithID, WithTimestamps):
    org_id: UUID
    name: str
    type: Optional[str] = None

class FileCreate(ORMBase):
    storage_key: str
    filename: str
    size: Optional[int] = None
    mime_type: Optional[str] = None

class FileRead(WithID, WithTimestamps):
    storage_key: str
    filename: str
    size: Optional[int] = None
    mime_type: Optional[str] = None
    created_by: Optional[UUID] = None

class TagCreate(ORMBase):
    label: str

class TagRead(WithID):
    label: str

class EntityTagCreate(ORMBase):
    entity_type: str
    entity_id: UUID
    tag_id: UUID

class AuditLogRead(WithID):
    entity_type: str
    entity_id: UUID
    action: str
    actor_id: Optional[UUID] = None
    at: datetime
    delta: Optional[dict[str, Any]] = None

class EmbedCreate(ORMBase):
    provider: str
    url: str
    meta: Optional[dict[str, Any]] = None

class EmbedRead(WithID):
    provider: str
    url: str
    meta: Optional[dict[str, Any]] = None

class WebhookCreate(ORMBase):
    target_url: str
    secret: Optional[str] = None
    events: Optional[list[str]] = None

class WebhookRead(WithID, WithTimestamps):
    target_url: str
    secret: Optional[str] = None
    events: Optional[list[str]] = None

class NotificationRead(WithID, WithTimestamps):
    user_id: UUID
    type: str
    payload: Optional[dict[str, Any]] = None
    read_at: Optional[datetime] = None

class FeatureFlagUpsert(ORMBase):
    org_id: UUID
    key: str
    enabled: bool = False

class FeatureFlagRead(ORMBase):
    org_id: UUID
    key: str
    enabled: bool

class RetentionRuleCreate(ORMBase):
    entity_type: str
    policy: dict[str, Any]

class RetentionRuleRead(WithID):
    entity_type: str
    policy: dict[str, Any]

# ---------------------------------------------------------------------------
# Meetings
# ---------------------------------------------------------------------------

class MeetingCreate(ORMBase):
    org_id: UUID
    title: str
    starts_at: datetime
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None
    is_public: bool = True
    stream_url: Optional[str] = None
    body_id: Optional[UUID] = None

class MeetingUpdate(ORMBase):
    title: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None
    is_public: Optional[bool] = None
    stream_url: Optional[str] = None
    body_id: Optional[UUID] = None

class MeetingRead(WithID, WithTimestamps):
    org_id: UUID
    body_id: Optional[UUID] = None
    title: str
    starts_at: datetime
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None
    is_public: bool
    stream_url: Optional[str] = None

class MeetingPermissionCreate(ORMBase):
    meeting_id: UUID
    principal_type: str  # user|group|role
    principal_id: UUID
    permission: str      # view|edit|publish

class AgendaItemCreate(ORMBase):
    meeting_id: UUID
    title: str
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    position: int = 0
    linked_policy_id: Optional[UUID] = None
    linked_objective_id: Optional[UUID] = None
    time_allocated: Optional[int] = None

class AgendaItemUpdate(ORMBase):
    title: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[UUID] = None
    position: Optional[int] = None
    linked_policy_id: Optional[UUID] = None
    linked_objective_id: Optional[UUID] = None
    time_allocated: Optional[int] = None

class AgendaItemRead(WithID):
    meeting_id: UUID
    parent_id: Optional[UUID] = None
    position: int
    title: str
    description: Optional[str] = None
    linked_policy_id: Optional[UUID] = None
    linked_objective_id: Optional[UUID] = None
    time_allocated: Optional[int] = None

class AgendaWorkflowCreate(ORMBase):
    name: str
    active: bool = True

class AgendaWorkflowRead(WithID):
    name: str
    active: bool

class AgendaWorkflowStepCreate(ORMBase):
    workflow_id: UUID
    step_no: int
    approver_type: str
    approver_id: Optional[UUID] = None
    rule: Optional[str] = None

class AgendaWorkflowStepRead(WithID):
    workflow_id: UUID
    step_no: int
    approver_type: str
    approver_id: Optional[UUID] = None
    rule: Optional[str] = None

class AgendaItemApprovalCreate(ORMBase):
    item_id: UUID
    step_id: UUID
    approver_id: Optional[UUID] = None
    decision: Optional[str] = None
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None

class AgendaItemApprovalRead(WithID):
    item_id: UUID
    step_id: UUID
    approver_id: Optional[UUID] = None
    decision: Optional[str] = None
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None

class MotionCreate(ORMBase):
    agenda_item_id: UUID
    text: str
    moved_by_id: Optional[UUID] = None
    seconded_by_id: Optional[UUID] = None

class MotionRead(WithID):
    agenda_item_id: UUID
    text: str
    moved_by_id: Optional[UUID] = None
    seconded_by_id: Optional[UUID] = None
    passed: Optional[bool] = None
    tally_for: Optional[int] = None
    tally_against: Optional[int] = None
    tally_abstain: Optional[int] = None

class VoteCreate(ORMBase):
    motion_id: UUID
    voter_id: UUID
    value: str  # yea|nay|abstain|absent

class VoteRead(WithID):
    motion_id: UUID
    voter_id: UUID
    value: str

class AttendanceUpsert(ORMBase):
    meeting_id: UUID
    user_id: UUID
    status: Optional[str] = None
    arrived_at: Optional[datetime] = None
    left_at: Optional[datetime] = None

class AttendanceRead(ORMBase):
    meeting_id: UUID
    user_id: UUID
    status: Optional[str] = None
    arrived_at: Optional[datetime] = None
    left_at: Optional[datetime] = None

class MinutesCreate(ORMBase):
    meeting_id: UUID
    content: Optional[str] = None
    published_at: Optional[datetime] = None
    author_id: Optional[UUID] = None

class MinutesRead(WithID, WithTimestamps):
    meeting_id: UUID
    author_id: Optional[UUID] = None
    content: Optional[str] = None
    published_at: Optional[datetime] = None

class MeetingFileLinkCreate(ORMBase):
    meeting_id: UUID
    file_id: UUID
    caption: Optional[str] = None

class AgendaItemFileLinkCreate(ORMBase):
    agenda_item_id: UUID
    file_id: UUID
    caption: Optional[str] = None

class PersonalNoteCreate(ORMBase):
    user_id: UUID
    entity_type: str
    entity_id: UUID
    text: Optional[str] = None

class PersonalNoteRead(WithID, WithTimestamps):
    user_id: UUID
    entity_type: str
    entity_id: UUID
    text: Optional[str] = None

class MeetingPublicationCreate(ORMBase):
    meeting_id: UUID
    public_url: Optional[str] = None
    archive_url: Optional[str] = None

class MeetingPublicationRead(ORMBase):
    meeting_id: UUID
    published_at: datetime
    public_url: Optional[str] = None
    archive_url: Optional[str] = None

# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

class PolicyCreate(ORMBase):
    org_id: UUID
    title: str
    code: Optional[str] = None
    status: str = "active"

class PolicyRead(WithID):
    org_id: UUID
    title: str
    code: Optional[str] = None
    status: str

class PolicyVersionCreate(ORMBase):
    policy_id: UUID
    version_no: int = 1
    content: Optional[str] = None
    effective_date: Optional[date] = None
    supersedes_version_id: Optional[UUID] = None
    created_by: Optional[UUID] = None

class PolicyVersionRead(WithID, WithTimestamps):
    policy_id: UUID
    version_no: int
    content: Optional[str] = None
    effective_date: Optional[date] = None
    supersedes_version_id: Optional[UUID] = None
    created_by: Optional[UUID] = None

class PolicyLegalRefCreate(ORMBase):
    policy_version_id: UUID
    citation: str
    url: Optional[str] = None

class PolicyLegalRefRead(WithID):
    policy_version_id: UUID
    citation: str
    url: Optional[str] = None

class PolicyCommentCreate(ORMBase):
    policy_version_id: UUID
    text: str
    visibility: str = "public"
    user_id: Optional[UUID] = None

class PolicyCommentRead(WithID, WithTimestamps):
    policy_version_id: UUID
    user_id: Optional[UUID] = None
    text: str
    visibility: str

class PolicyWorkflowCreate(ORMBase):
    policy_id: UUID
    name: str
    active: bool = True

class PolicyWorkflowRead(WithID):
    policy_id: UUID
    name: str
    active: bool

class PolicyWorkflowStepCreate(ORMBase):
    workflow_id: UUID
    step_no: int
    approver_type: str
    approver_id: Optional[UUID] = None
    rule: Optional[str] = None

class PolicyWorkflowStepRead(WithID):
    workflow_id: UUID
    step_no: int
    approver_type: str
    approver_id: Optional[UUID] = None
    rule: Optional[str] = None

class PolicyApprovalCreate(ORMBase):
    policy_version_id: UUID
    step_id: UUID
    approver_id: Optional[UUID] = None
    decision: Optional[str] = None
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None

class PolicyApprovalRead(WithID):
    policy_version_id: UUID
    step_id: UUID
    approver_id: Optional[UUID] = None
    decision: Optional[str] = None
    decided_at: Optional[datetime] = None
    comment: Optional[str] = None

class PolicyPublicationRead(ORMBase):
    policy_version_id: UUID
    published_at: datetime
    public_url: Optional[str] = None
    is_current: bool

class PolicyFileLinkCreate(ORMBase):
    policy_version_id: UUID
    file_id: UUID

# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

class PlanCreate(ORMBase):
    org_id: UUID
    name: str
    cycle_start: Optional[date] = None
    cycle_end: Optional[date] = None
    status: Optional[str] = None

class PlanRead(WithID):
    org_id: UUID
    name: str
    cycle_start: Optional[date] = None
    cycle_end: Optional[date] = None
    status: Optional[str] = None

class GoalCreate(ORMBase):
    plan_id: UUID
    name: str
    description: Optional[str] = None

class GoalRead(WithID):
    plan_id: UUID
    name: str
    description: Optional[str] = None

class ObjectiveCreate(ORMBase):
    goal_id: UUID
    name: str
    description: Optional[str] = None

class ObjectiveRead(WithID):
    goal_id: UUID
    name: str
    description: Optional[str] = None

class InitiativeCreate(ORMBase):
    objective_id: UUID
    name: str
    description: Optional[str] = None
    owner_id: Optional[UUID] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    priority: Optional[str] = None

class InitiativeRead(WithID):
    objective_id: UUID
    name: str
    description: Optional[str] = None
    owner_id: Optional[UUID] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    priority: Optional[str] = None

class KPICreate(ORMBase):
    name: str
    goal_id: Optional[UUID] = None
    objective_id: Optional[UUID] = None
    unit: Optional[str] = None
    target: Optional[float] = None
    baseline: Optional[float] = None
    direction: Optional[str] = None  # up|down

class KPIRead(WithID):
    name: str
    goal_id: Optional[UUID] = None
    objective_id: Optional[UUID] = None
    unit: Optional[str] = None
    target: Optional[float] = None
    baseline: Optional[float] = None
    direction: Optional[str] = None

class KPIDatapointCreate(ORMBase):
    kpi_id: UUID
    as_of: date
    value: float
    note: Optional[str] = None

class KPIDatapointRead(WithID):
    kpi_id: UUID
    as_of: date
    value: float
    note: Optional[str] = None

class ScorecardCreate(ORMBase):
    plan_id: UUID
    name: str

class ScorecardRead(WithID):
    plan_id: UUID
    name: str

class ScorecardKPIAttach(ORMBase):
    scorecard_id: UUID
    kpi_id: UUID
    display_order: Optional[int] = None

class PlanAssignmentCreate(ORMBase):
    entity_type: str
    entity_id: UUID
    assignee_type: str  # user|group|role
    assignee_id: UUID

class PlanAlignmentCreate(ORMBase):
    agenda_item_id: Optional[UUID] = None
    policy_id: Optional[UUID] = None
    objective_id: Optional[UUID] = None
    note: Optional[str] = None

class PlanFilterCreate(ORMBase):
    plan_id: UUID
    name: str
    criteria: Optional[dict[str, Any]] = None

class PlanFilterRead(WithID):
    plan_id: UUID
    name: str
    criteria: Optional[dict[str, Any]] = None

# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------

class EvaluationTemplateCreate(ORMBase):
    name: str
    for_role: Optional[str] = None
    version: int = 1
    is_active: bool = True

class EvaluationTemplateRead(WithID):
    name: str
    for_role: Optional[str] = None
    version: int
    is_active: bool

class EvaluationSectionCreate(ORMBase):
    template_id: UUID
    title: str
    order_no: int = 0

class EvaluationSectionRead(WithID):
    template_id: UUID
    title: str
    order_no: int

class EvaluationQuestionCreate(ORMBase):
    section_id: UUID
    text: str
    type: str
    scale_min: Optional[int] = None
    scale_max: Optional[int] = None
    weight: Optional[float] = None

class EvaluationQuestionRead(WithID):
    section_id: UUID
    text: str
    type: str
    scale_min: Optional[int] = None
    scale_max: Optional[int] = None
    weight: Optional[float] = None

class EvaluationCycleCreate(ORMBase):
    org_id: UUID
    name: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

class EvaluationCycleRead(WithID):
    org_id: UUID
    name: str
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

class EvaluationAssignmentCreate(ORMBase):
    cycle_id: UUID
    subject_user_id: UUID
    evaluator_user_id: UUID
    template_id: UUID
    status: Optional[str] = None

class EvaluationAssignmentRead(WithID):
    cycle_id: UUID
    subject_user_id: UUID
    evaluator_user_id: UUID
    template_id: UUID
    status: Optional[str] = None

class EvaluationResponseCreate(ORMBase):
    assignment_id: UUID
    question_id: UUID
    value_num: Optional[float] = None
    value_text: Optional[str] = None
    comment: Optional[str] = None
    answered_at: Optional[datetime] = None

class EvaluationResponseRead(WithID):
    assignment_id: UUID
    question_id: UUID
    value_num: Optional[float] = None
    value_text: Optional[str] = None
    comment: Optional[str] = None
    answered_at: Optional[datetime] = None

class EvaluationSignoffCreate(ORMBase):
    assignment_id: UUID
    signer_id: UUID
    signed_at: Optional[datetime] = None
    note: Optional[str] = None

class EvaluationSignoffRead(WithID):
    assignment_id: UUID
    signer_id: UUID
    signed_at: datetime
    note: Optional[str] = None

class EvaluationFileLinkCreate(ORMBase):
    assignment_id: UUID
    file_id: UUID

class EvaluationReportRead(WithID):
    cycle_id: UUID
    scope: Optional[dict[str, Any]] = None
    generated_at: datetime
    file_id: Optional[UUID] = None

# ---------------------------------------------------------------------------
# Documents (repository)
# ---------------------------------------------------------------------------

class FolderCreate(ORMBase):
    org_id: UUID
    name: str
    parent_id: Optional[UUID] = None
    is_public: bool = False
    sort_order: Optional[int] = None

class FolderRead(WithID):
    org_id: UUID
    parent_id: Optional[UUID] = None
    name: str
    is_public: bool
    sort_order: Optional[int] = None

class DocumentCreate(ORMBase):
    title: str
    folder_id: Optional[UUID] = None
    is_public: bool = False

class DocumentRead(WithID):
    folder_id: Optional[UUID] = None
    title: str
    current_version_id: Optional[UUID] = None
    is_public: bool

class DocumentVersionCreate(ORMBase):
    document_id: UUID
    file_id: UUID
    version_no: int = 1
    checksum: Optional[str] = None
    created_by: Optional[UUID] = None
    published_at: Optional[datetime] = None

class DocumentVersionRead(WithID):
    document_id: UUID
    file_id: UUID
    version_no: int
    checksum: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime
    published_at: Optional[datetime] = None

class DocumentPermissionUpsert(ORMBase):
    resource_type: str  # folder|document
    resource_id: UUID
    principal_type: str  # user|group|role
    principal_id: UUID
    permission: str      # view|edit|manage

class DocumentNotificationUpsert(ORMBase):
    document_id: UUID
    user_id: UUID
    subscribed: bool = True

class DocumentNotificationRead(ORMBase):
    document_id: UUID
    user_id: UUID
    subscribed: bool
    last_sent_at: Optional[datetime] = None

class DocumentActivityRead(WithID):
    document_id: UUID
    actor_id: Optional[UUID] = None
    action: str
    at: datetime
    meta: Optional[dict[str, Any]] = None

# ---------------------------------------------------------------------------
# Communications
# ---------------------------------------------------------------------------

class ChannelCreate(ORMBase):
    org_id: UUID
    name: str
    audience: str = "public"
    description: Optional[str] = None

class ChannelRead(WithID):
    org_id: UUID
    name: str
    audience: str
    description: Optional[str] = None

class PostCreate(ORMBase):
    channel_id: UUID
    title: str
    body: Optional[str] = None
    status: str = "draft"
    publish_at: Optional[datetime] = None
    author_id: Optional[UUID] = None

class PostRead(WithID):
    channel_id: UUID
    title: str
    body: Optional[str] = None
    status: str
    publish_at: Optional[datetime] = None
    author_id: Optional[UUID] = None
    created_at: datetime

class PostAttachmentLinkCreate(ORMBase):
    post_id: UUID
    file_id: UUID

class SubscriptionCreate(ORMBase):
    channel_id: UUID
    principal_type: str
    principal_id: UUID

class SubscriptionRead(ORMBase):
    channel_id: UUID
    principal_type: str
    principal_id: UUID
    created_at: datetime

class DeliveryRead(WithID):
    post_id: UUID
    user_id: UUID
    delivered_at: Optional[datetime] = None
    medium: Optional[str] = None
    status: Optional[str] = None

class PageCreate(ORMBase):
    channel_id: UUID
    slug: str
    title: str
    body: Optional[str] = None
    status: str = "draft"
    published_at: Optional[datetime] = None

class PageRead(WithID):
    channel_id: UUID
    slug: str
    title: str
    body: Optional[str] = None
    status: str
    published_at: Optional[datetime] = None

# ==================
# Core & Identity
# ==================

class DistrictCreate(ORMBase):
    name: str
    code: Optional[str] = None

class DistrictRead(WithID, WithTimestamps):
    name: str
    code: Optional[str] = None

class SchoolCreate(ORMBase):
    district_id: UUID
    name: str
    school_code: Optional[str] = None
    type: Optional[str] = None
    timezone: Optional[str] = None

class SchoolRead(WithID, WithTimestamps):
    district_id: UUID
    name: str
    school_code: Optional[str] = None
    type: Optional[str] = None
    timezone: Optional[str] = None

class AcademicTermCreate(ORMBase):
    school_id: UUID
    name: str
    type: Optional[str] = None
    start_date: date
    end_date: date

class AcademicTermRead(WithID, WithTimestamps):
    school_id: UUID
    name: str
    type: Optional[str] = None
    start_date: date
    end_date: date

class GradingPeriodCreate(ORMBase):
    term_id: UUID
    name: str
    start_date: date
    end_date: date

class GradingPeriodRead(WithID, WithTimestamps):
    term_id: UUID
    name: str
    start_date: date
    end_date: date

class CalendarCreate(ORMBase):
    school_id: UUID
    name: str

class CalendarRead(WithID, WithTimestamps):
    school_id: UUID
    name: str

class CalendarDayCreate(ORMBase):
    calendar_id: UUID
    date: date
    day_type: str = "instructional"
    notes: Optional[str] = None

class CalendarDayRead(WithID, WithTimestamps):
    calendar_id: UUID
    date: date
    day_type: str
    notes: Optional[str] = None

class BellScheduleCreate(ORMBase):
    school_id: UUID
    name: str

class BellScheduleRead(WithID, WithTimestamps):
    school_id: UUID
    name: str

class PeriodCreate(ORMBase):
    bell_schedule_id: UUID
    name: str
    start_time: str
    end_time: str
    sequence: Optional[int] = None

class PeriodRead(WithID, WithTimestamps):
    bell_schedule_id: UUID
    name: str
    start_time: str
    end_time: str
    sequence: Optional[int] = None

class GradeLevelCreate(ORMBase):
    school_id: UUID
    name: str
    ordinal: Optional[int] = None

class GradeLevelRead(WithID, WithTimestamps):
    school_id: UUID
    name: str
    ordinal: Optional[int] = None

class DepartmentCreate(ORMBase):
    school_id: UUID
    name: str

class DepartmentRead(WithID, WithTimestamps):
    school_id: UUID
    name: str

class SubjectCreate(ORMBase):
    department_id: Optional[UUID] = None
    name: str
    code: Optional[str] = None

class SubjectRead(WithID, WithTimestamps):
    department_id: Optional[UUID] = None
    name: str
    code: Optional[str] = None

class CourseCreate(ORMBase):
    school_id: UUID
    subject_id: Optional[UUID] = None
    name: str
    code: Optional[str] = None
    credit_hours: Optional[Decimal] = None

class CourseRead(WithID, WithTimestamps):
    school_id: UUID
    subject_id: Optional[UUID] = None
    name: str
    code: Optional[str] = None
    credit_hours: Optional[Decimal] = None

class CourseSectionCreate(ORMBase):
    course_id: UUID
    term_id: UUID
    section_number: str
    capacity: Optional[int] = None
    school_id: UUID

class CourseSectionRead(WithID, WithTimestamps):
    course_id: UUID
    term_id: UUID
    section_number: str
    capacity: Optional[int] = None
    school_id: UUID

class RoomCreate(ORMBase):
    school_id: UUID
    name: str
    capacity: Optional[int] = None

class RoomRead(WithID, WithTimestamps):
    school_id: UUID
    name: str
    capacity: Optional[int] = None

class PersonCreate(ORMBase):
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    dob: Optional[date] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    gender: Optional[str] = None

class PersonRead(WithID, WithTimestamps):
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    dob: Optional[date] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    gender: Optional[str] = None

class StudentCreate(ORMBase):
    id: UUID
    student_number: Optional[str] = None
    graduation_year: Optional[int] = None

class StudentRead(ORMBase):
    id: UUID
    student_number: Optional[str] = None
    graduation_year: Optional[int] = None

class StaffCreate(ORMBase):
    id: UUID
    employee_number: Optional[str] = None
    title: Optional[str] = None

class StaffRead(ORMBase):
    id: UUID
    employee_number: Optional[str] = None
    title: Optional[str] = None

class GuardianCreate(ORMBase):
    id: UUID
    relationship: Optional[str] = None

class GuardianRead(ORMBase):
    id: UUID
    relationship: Optional[str] = None

class UserAccountCreate(ORMBase):
    person_id: UUID
    username: str
    password_hash: Optional[str] = None
    is_active: bool = True

class UserAccountRead(WithID, WithTimestamps):
    person_id: UUID
    username: str
    password_hash: Optional[str] = None
    is_active: bool

class RoleCreate(ORMBase):
    name: str
    description: Optional[str] = None

class RoleRead(WithID, WithTimestamps):
    name: str
    description: Optional[str] = None

class PermissionCreate(ORMBase):
    code: str
    description: Optional[str] = None

class PermissionRead(WithID, WithTimestamps):
    code: str
    description: Optional[str] = None

class RolePermissionCreate(ORMBase):
    role_id: UUID
    permission_id: UUID

class RolePermissionRead(ORMBase):
    role_id: UUID
    permission_id: UUID

class AddressCreate(ORMBase):
    line1: str
    line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

class AddressRead(WithID, WithTimestamps):
    line1: str
    line2: Optional[str] = None
    city: str
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

class ContactCreate(ORMBase):
    type: str
    value: str

class ContactRead(WithID, WithTimestamps):
    type: str
    value: str

class PersonAddressCreate(ORMBase):
    person_id: UUID
    address_id: UUID
    is_primary: bool = False

class PersonAddressRead(ORMBase):
    person_id: UUID
    address_id: UUID
    is_primary: bool

class PersonContactCreate(ORMBase):
    person_id: UUID
    contact_id: UUID
    label: Optional[str] = None
    is_primary: bool = False
    is_emergency: bool = False

class PersonContactRead(ORMBase):
    person_id: UUID
    contact_id: UUID
    label: Optional[str] = None
    is_primary: bool
    is_emergency: bool

class StudentGuardianCreate(ORMBase):
    student_id: UUID
    guardian_id: UUID
    custody: Optional[str] = None
    is_primary: bool = False
    contact_order: Optional[int] = None

class StudentGuardianRead(ORMBase):
    student_id: UUID
    guardian_id: UUID
    custody: Optional[str] = None
    is_primary: bool
    contact_order: Optional[int] = None

class ExternalIdCreate(ORMBase):
    entity_type: str
    entity_id: UUID
    system: str
    external_id: str

class ExternalIdRead(WithID, WithTimestamps):
    entity_type: str
    entity_id: UUID
    system: str
    external_id: str

# ==================
# Enrollment & Programs
# ==================

class StudentSchoolEnrollmentCreate(ORMBase):
    student_id: UUID
    school_id: UUID
    entry_date: date
    exit_date: Optional[date] = None
    status: str = "active"
    exit_reason: Optional[str] = None

class StudentSchoolEnrollmentRead(WithID, WithTimestamps):
    student_id: UUID
    school_id: UUID
    entry_date: date
    exit_date: Optional[date] = None
    status: str
    exit_reason: Optional[str] = None

class StudentProgramEnrollmentCreate(ORMBase):
    student_id: UUID
    program_name: str
    start_date: date
    end_date: Optional[date] = None
    status: Optional[str] = None

class StudentProgramEnrollmentRead(WithID, WithTimestamps):
    student_id: UUID
    program_name: str
    start_date: date
    end_date: Optional[date] = None
    status: Optional[str] = None

class SpecialEducationCaseCreate(ORMBase):
    student_id: UUID
    eligibility: Optional[str] = None
    case_opened: Optional[date] = None
    case_closed: Optional[date] = None

class SpecialEducationCaseRead(WithID, WithTimestamps):
    student_id: UUID
    eligibility: Optional[str] = None
    case_opened: Optional[date] = None
    case_closed: Optional[date] = None

class IEPPlanCreate(ORMBase):
    special_ed_case_id: UUID
    effective_start: date
    effective_end: Optional[date] = None
    summary: Optional[str] = None

class IEPPlanRead(WithID, WithTimestamps):
    special_ed_case_id: UUID
    effective_start: date
    effective_end: Optional[date] = None
    summary: Optional[str] = None

class AccommodationCreate(ORMBase):
    iep_plan_id: Optional[UUID] = None
    applies_to: Optional[str] = None
    description: str

class AccommodationRead(WithID, WithTimestamps):
    iep_plan_id: Optional[UUID] = None
    applies_to: Optional[str] = None
    description: str

class ELLPlanCreate(ORMBase):
    student_id: UUID
    level: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None

class ELLPlanRead(WithID, WithTimestamps):
    student_id: UUID
    level: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None

class Section504PlanCreate(ORMBase):
    student_id: UUID
    effective_start: date
    effective_end: Optional[date] = None
    summary: Optional[str] = None

class Section504PlanRead(WithID, WithTimestamps):
    student_id: UUID
    effective_start: date
    effective_end: Optional[date] = None
    summary: Optional[str] = None

# ==================
# Scheduling
# ==================

class SectionMeetingCreate(ORMBase):
    section_id: UUID
    day_of_week: int
    period_id: Optional[UUID] = None
    room_id: Optional[UUID] = None

class SectionMeetingRead(WithID, WithTimestamps):
    section_id: UUID
    day_of_week: int
    period_id: Optional[UUID] = None
    room_id: Optional[UUID] = None

class TeacherSectionAssignmentCreate(ORMBase):
    staff_id: UUID
    section_id: UUID
    role: Optional[str] = None

class TeacherSectionAssignmentRead(WithID, WithTimestamps):
    staff_id: UUID
    section_id: UUID
    role: Optional[str] = None

class StudentSectionEnrollmentCreate(ORMBase):
    student_id: UUID
    section_id: UUID
    added_on: date
    dropped_on: Optional[date] = None
    seat_time_minutes: Optional[int] = None

class StudentSectionEnrollmentRead(WithID, WithTimestamps):
    student_id: UUID
    section_id: UUID
    added_on: date
    dropped_on: Optional[date] = None
    seat_time_minutes: Optional[int] = None

class CoursePrerequisiteCreate(ORMBase):
    course_id: UUID
    prereq_course_id: UUID

class CoursePrerequisiteRead(ORMBase):
    course_id: UUID
    prereq_course_id: UUID

class SectionRoomAssignmentCreate(ORMBase):
    section_id: UUID
    room_id: UUID
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class SectionRoomAssignmentRead(WithID, WithTimestamps):
    section_id: UUID
    room_id: UUID
    start_date: Optional[date] = None
    end_date: Optional[date] = None

# ==================
# Attendance
# ==================

class AttendanceCodeCreate(ORMBase):
    code: str
    description: Optional[str] = None
    is_present: bool = False
    is_excused: bool = False

class AttendanceCodeRead(ORMBase):
    code: str
    description: Optional[str] = None
    is_present: bool
    is_excused: bool

class AttendanceEventCreate(ORMBase):
    student_id: UUID
    section_meeting_id: Optional[UUID] = None
    date: date
    code: str
    minutes: Optional[int] = None
    notes: Optional[str] = None

class AttendanceEventRead(WithID, WithTimestamps):
    student_id: UUID
    section_meeting_id: Optional[UUID] = None
    date: date
    code: str
    minutes: Optional[int] = None
    notes: Optional[str] = None

class AttendanceDailySummaryCreate(ORMBase):
    student_id: UUID
    date: date
    present_minutes: int = 0
    absent_minutes: int = 0
    tardy_minutes: int = 0

class AttendanceDailySummaryRead(WithID, WithTimestamps):
    student_id: UUID
    date: date
    present_minutes: int
    absent_minutes: int
    tardy_minutes: int

# ==================
# Assessment, Grades & Transcripts
# ==================

class GradeScaleCreate(ORMBase):
    school_id: UUID
    name: str
    type: Optional[str] = None

class GradeScaleRead(WithID, WithTimestamps):
    school_id: UUID
    name: str
    type: Optional[str] = None

class GradeScaleBandCreate(ORMBase):
    grade_scale_id: UUID
    label: str
    min_value: Decimal
    max_value: Decimal
    gpa_points: Optional[Decimal] = None

class GradeScaleBandRead(WithID, WithTimestamps):
    grade_scale_id: UUID
    label: str
    min_value: Decimal
    max_value: Decimal
    gpa_points: Optional[Decimal] = None

class AssignmentCategoryCreate(ORMBase):
    section_id: UUID
    name: str
    weight: Optional[Decimal] = None

class AssignmentCategoryRead(WithID, WithTimestamps):
    section_id: UUID
    name: str
    weight: Optional[Decimal] = None

class AssignmentCreate(ORMBase):
    section_id: UUID
    category_id: Optional[UUID] = None
    name: str
    due_date: Optional[date] = None
    points_possible: Optional[Decimal] = None

class AssignmentRead(WithID, WithTimestamps):
    section_id: UUID
    category_id: Optional[UUID] = None
    name: str
    due_date: Optional[date] = None
    points_possible: Optional[Decimal] = None

class GradebookEntryCreate(ORMBase):
    assignment_id: UUID
    student_id: UUID
    score: Optional[Decimal] = None
    submitted_at: Optional[datetime] = None
    late: bool = False

class GradebookEntryRead(WithID, WithTimestamps):
    assignment_id: UUID
    student_id: UUID
    score: Optional[Decimal] = None
    submitted_at: Optional[datetime] = None
    late: bool

class FinalGradeCreate(ORMBase):
    student_id: UUID
    section_id: UUID
    grading_period_id: UUID
    numeric_grade: Optional[Decimal] = None
    letter_grade: Optional[str] = None
    credits_earned: Optional[Decimal] = None

class FinalGradeRead(WithID, WithTimestamps):
    student_id: UUID
    section_id: UUID
    grading_period_id: UUID
    numeric_grade: Optional[Decimal] = None
    letter_grade: Optional[str] = None
    credits_earned: Optional[Decimal] = None

class GPACalculationCreate(ORMBase):
    student_id: UUID
    term_id: UUID
    gpa: Decimal

class GPACalculationRead(WithID, WithTimestamps):
    student_id: UUID
    term_id: UUID
    gpa: Decimal

class ClassRankCreate(ORMBase):
    school_id: UUID
    term_id: UUID
    student_id: UUID
    rank: int

class ClassRankRead(WithID, WithTimestamps):
    school_id: UUID
    term_id: UUID
    student_id: UUID
    rank: int

class ReportCardCreate(ORMBase):
    student_id: UUID
    term_id: UUID
    published_at: Optional[datetime] = None

class ReportCardRead(WithID, WithTimestamps):
    student_id: UUID
    term_id: UUID
    published_at: Optional[datetime] = None

class TranscriptLineCreate(ORMBase):
    student_id: UUID
    course_id: Optional[UUID] = None
    term_id: Optional[UUID] = None
    credits_attempted: Optional[Decimal] = None
    credits_earned: Optional[Decimal] = None
    final_letter: Optional[str] = None
    final_numeric: Optional[Decimal] = None

class TranscriptLineRead(WithID, WithTimestamps):
    student_id: UUID
    course_id: Optional[UUID] = None
    term_id: Optional[UUID] = None
    credits_attempted: Optional[Decimal] = None
    credits_earned: Optional[Decimal] = None
    final_letter: Optional[str] = None
    final_numeric: Optional[Decimal] = None

class StandardizedTestCreate(ORMBase):
    name: str
    subject: Optional[str] = None

class StandardizedTestRead(WithID, WithTimestamps):
    name: str
    subject: Optional[str] = None

class TestAdministrationCreate(ORMBase):
    test_id: UUID
    administration_date: date
    school_id: Optional[UUID] = None

class TestAdministrationRead(WithID, WithTimestamps):
    test_id: UUID
    administration_date: date
    school_id: Optional[UUID] = None

class TestResultCreate(ORMBase):
    administration_id: UUID
    student_id: UUID
    scale_score: Optional[Decimal] = None
    percentile: Optional[Decimal] = None
    performance_level: Optional[str] = None

class TestResultRead(WithID, WithTimestamps):
    administration_id: UUID
    student_id: UUID
    scale_score: Optional[Decimal] = None
    percentile: Optional[Decimal] = None
    performance_level: Optional[str] = None

# ==================
# Behavior & Discipline
# ==================

class BehaviorCodeCreate(ORMBase):
    code: str
    description: Optional[str] = None

class BehaviorCodeRead(ORMBase):
    code: str
    description: Optional[str] = None

class ConsequenceTypeCreate(ORMBase):
    code: str
    description: Optional[str] = None

class ConsequenceTypeRead(ORMBase):
    code: str
    description: Optional[str] = None

class IncidentCreate(ORMBase):
    school_id: Optional[UUID] = None
    occurred_at: datetime
    behavior_code: str
    description: Optional[str] = None

class IncidentRead(WithID, WithTimestamps):
    school_id: Optional[UUID] = None
    occurred_at: datetime
    behavior_code: str
    description: Optional[str] = None

class IncidentParticipantCreate(ORMBase):
    incident_id: UUID
    person_id: UUID
    role: str

class IncidentParticipantRead(WithID, WithTimestamps):
    incident_id: UUID
    person_id: UUID
    role: str

class ConsequenceCreate(ORMBase):
    incident_id: UUID
    participant_id: UUID
    consequence_code: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None

class ConsequenceRead(WithID, WithTimestamps):
    incident_id: UUID
    participant_id: UUID
    consequence_code: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None

class BehaviorInterventionCreate(ORMBase):
    student_id: UUID
    intervention: str
    start_date: date
    end_date: Optional[date] = None

class BehaviorInterventionRead(WithID, WithTimestamps):
    student_id: UUID
    intervention: str
    start_date: date
    end_date: Optional[date] = None

# ==================
# Health & Safety
# ==================

class HealthProfileCreate(ORMBase):
    student_id: UUID
    allergies: Optional[str] = None
    conditions: Optional[str] = None

class HealthProfileRead(WithID, WithTimestamps):
    student_id: UUID
    allergies: Optional[str] = None
    conditions: Optional[str] = None

class ImmunizationCreate(ORMBase):
    name: str
    code: Optional[str] = None

class ImmunizationRead(WithID, WithTimestamps):
    name: str
    code: Optional[str] = None

class ImmunizationRecordCreate(ORMBase):
    student_id: UUID
    immunization_id: UUID
    date_administered: date
    dose_number: Optional[int] = None

class ImmunizationRecordRead(WithID, WithTimestamps):
    student_id: UUID
    immunization_id: UUID
    date_administered: date
    dose_number: Optional[int] = None

class MedicationCreate(ORMBase):
    name: str
    instructions: Optional[str] = None

class MedicationRead(WithID, WithTimestamps):
    name: str
    instructions: Optional[str] = None

class MedicationAdministrationCreate(ORMBase):
    student_id: UUID
    medication_id: UUID
    administered_at: datetime
    dose: Optional[str] = None
    notes: Optional[str] = None

class MedicationAdministrationRead(WithID, WithTimestamps):
    student_id: UUID
    medication_id: UUID
    administered_at: datetime
    dose: Optional[str] = None
    notes: Optional[str] = None

class NurseVisitCreate(ORMBase):
    student_id: UUID
    visited_at: datetime
    reason: Optional[str] = None
    disposition: Optional[str] = None

class NurseVisitRead(WithID, WithTimestamps):
    student_id: UUID
    visited_at: datetime
    reason: Optional[str] = None
    disposition: Optional[str] = None

class EmergencyContactCreate(ORMBase):
    person_id: UUID
    contact_name: str
    relationship: Optional[str] = None
    phone: Optional[str] = None

class EmergencyContactRead(WithID, WithTimestamps):
    person_id: UUID
    contact_name: str
    relationship: Optional[str] = None
    phone: Optional[str] = None

class ConsentCreate(ORMBase):
    person_id: UUID
    consent_type: str
    granted: bool = True
    effective_date: date
    expires_on: Optional[date] = None

class ConsentRead(WithID, WithTimestamps):
    person_id: UUID
    consent_type: str
    granted: bool
    effective_date: date
    expires_on: Optional[date] = None

# ==================
# Fees, Meals, Transportation, Library
# ==================

class FeeCreate(ORMBase):
    school_id: UUID
    name: str
    amount: Decimal

class FeeRead(WithID, WithTimestamps):
    school_id: UUID
    name: str
    amount: Decimal

class InvoiceCreate(ORMBase):
    student_id: UUID
    issued_on: date
    due_on: Optional[date] = None
    status: str = "open"

class InvoiceRead(WithID, WithTimestamps):
    student_id: UUID
    issued_on: date
    due_on: Optional[date] = None
    status: str

class PaymentCreate(ORMBase):
    invoice_id: UUID
    paid_on: date
    amount: Decimal
    method: Optional[str] = None

class PaymentRead(WithID, WithTimestamps):
    invoice_id: UUID
    paid_on: date
    amount: Decimal
    method: Optional[str] = None

class WaiverCreate(ORMBase):
    student_id: UUID
    reason: Optional[str] = None
    amount: Optional[Decimal] = None
    granted_on: Optional[date] = None

class WaiverRead(WithID, WithTimestamps):
    student_id: UUID
    reason: Optional[str] = None
    amount: Optional[Decimal] = None
    granted_on: Optional[date] = None

class MealAccountCreate(ORMBase):
    student_id: UUID
    balance: Decimal = Decimal("0")

class MealAccountRead(WithID, WithTimestamps):
    student_id: UUID
    balance: Decimal

class MealTransactionCreate(ORMBase):
    account_id: UUID
    transacted_at: datetime
    amount: Decimal
    description: Optional[str] = None

class MealTransactionRead(WithID, WithTimestamps):
    account_id: UUID
    transacted_at: datetime
    amount: Decimal
    description: Optional[str] = None

class MealEligibilityStatusCreate(ORMBase):
    student_id: UUID
    status: str
    effective_start: date
    effective_end: Optional[date] = None

class MealEligibilityStatusRead(WithID, WithTimestamps):
    student_id: UUID
    status: str
    effective_start: date
    effective_end: Optional[date] = None

class BusRouteCreate(ORMBase):
    name: str
    school_id: Optional[UUID] = None

class BusRouteRead(WithID, WithTimestamps):
    name: str
    school_id: Optional[UUID] = None

class BusStopCreate(ORMBase):
    route_id: UUID
    name: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

class BusStopRead(WithID, WithTimestamps):
    route_id: UUID
    name: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None

class BusStopTimeCreate(ORMBase):
    route_id: UUID
    stop_id: UUID
    arrival_time: str
    departure_time: Optional[str] = None

class BusStopTimeRead(WithID, WithTimestamps):
    route_id: UUID
    stop_id: UUID
    arrival_time: str
    departure_time: Optional[str] = None

class StudentTransportationAssignmentCreate(ORMBase):
    student_id: UUID
    route_id: Optional[UUID] = None
    stop_id: Optional[UUID] = None
    direction: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None

class StudentTransportationAssignmentRead(WithID, WithTimestamps):
    student_id: UUID
    route_id: Optional[UUID] = None
    stop_id: Optional[UUID] = None
    direction: Optional[str] = None
    effective_start: date
    effective_end: Optional[date] = None

class LibraryItemCreate(ORMBase):
    school_id: UUID
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    barcode: Optional[str] = None

class LibraryItemRead(WithID, WithTimestamps):
    school_id: UUID
    title: str
    author: Optional[str] = None
    isbn: Optional[str] = None
    barcode: Optional[str] = None

class LibraryCheckoutCreate(ORMBase):
    item_id: UUID
    person_id: UUID
    checked_out_on: date
    due_on: date
    returned_on: Optional[date] = None

class LibraryCheckoutRead(WithID, WithTimestamps):
    item_id: UUID
    person_id: UUID
    checked_out_on: date
    due_on: date
    returned_on: Optional[date] = None

class LibraryHoldCreate(ORMBase):
    item_id: UUID
    person_id: UUID
    placed_on: date
    expires_on: Optional[date] = None

class LibraryHoldRead(WithID, WithTimestamps):
    item_id: UUID
    person_id: UUID
    placed_on: date
    expires_on: Optional[date] = None

class LibraryFineCreate(ORMBase):
    person_id: UUID
    amount: Decimal
    reason: Optional[str] = None
    assessed_on: date
    paid_on: Optional[date] = None

class LibraryFineRead(WithID, WithTimestamps):
    person_id: UUID
    amount: Decimal
    reason: Optional[str] = None
    assessed_on: date
    paid_on: Optional[date] = None

# ==================
# Communication & Engagement
# ==================

class MessageCreate(ORMBase):
    sender_id: Optional[UUID] = None
    channel: str
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[datetime] = None

class MessageRead(WithID, WithTimestamps):
    sender_id: Optional[UUID] = None
    channel: str
    subject: Optional[str] = None
    body: Optional[str] = None
    sent_at: Optional[datetime] = None

class MessageRecipientCreate(ORMBase):
    message_id: UUID
    person_id: UUID
    delivery_status: Optional[str] = None
    delivered_at: Optional[datetime] = None

class MessageRecipientRead(ORMBase):
    message_id: UUID
    person_id: UUID
    delivery_status: Optional[str] = None
    delivered_at: Optional[datetime] = None

class FamilyPortalAccessCreate(ORMBase):
    guardian_id: UUID
    student_id: UUID
    permissions: Optional[str] = None

class FamilyPortalAccessRead(ORMBase):
    guardian_id: UUID
    student_id: UUID
    permissions: Optional[str] = None

class DocumentLinkCreate(ORMBase):
    document_id: UUID
    entity_type: str
    entity_id: UUID

class DocumentLinkRead(WithID, WithTimestamps):
    document_id: UUID
    entity_type: str
    entity_id: UUID

# ==================
# State Reporting & Auditing
# ==================

class StateReportingSnapshotCreate(ORMBase):
    as_of_date: date
    scope: Optional[str] = None
    payload: Optional[dict] = None

class StateReportingSnapshotRead(WithID, WithTimestamps):
    as_of_date: date
    scope: Optional[str] = None
    payload: Optional[dict] = None

class ExportRunCreate(ORMBase):
    export_name: str
    ran_at: Optional[datetime] = None
    status: str = "success"
    file_uri: Optional[str] = None
    error: Optional[str] = None

class ExportRunRead(WithID, WithTimestamps):
    export_name: str
    ran_at: datetime
    status: str
    file_uri: Optional[str] = None
    error: Optional[str] = None

class AuditLogCreate(ORMBase):
    actor_id: Optional[UUID] = None
    action: str
    entity_type: str
    entity_id: UUID
    details: Optional[dict] = None
    occurred_at: Optional[datetime] = None

class AuditLogRead(WithID, WithTimestamps):
    actor_id: Optional[UUID] = None
    action: str
    entity_type: str
    entity_id: UUID
    details: Optional[dict] = None
    occurred_at: datetime

class DataSharingAgreementCreate(ORMBase):
    vendor: str
    scope: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None

class DataSharingAgreementRead(WithID, WithTimestamps):
    vendor: str
    scope: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None

# ==================
# Analytics & ETL Support
# ==================

class SISImportJobCreate(ORMBase):
    source: str
    status: str = "running"
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    counts: Optional[dict] = None
    error_log: Optional[str] = None

class SISImportJobRead(WithID, WithTimestamps):
    source: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    counts: Optional[dict] = None
    error_log: Optional[str] = None

class DataQualityIssueCreate(ORMBase):
    entity_type: str
    entity_id: UUID
    rule: str
    severity: str
    details: Optional[str] = None
    detected_at: Optional[datetime] = None

class DataQualityIssueRead(WithID, WithTimestamps):
    entity_type: str
    entity_id: UUID
    rule: str
    severity: str
    details: Optional[str] = None
    detected_at: datetime

# ----------------------------------------------------------------------------
# CIC (Curriculum & Instruction Committee)
# ----------------------------------------------------------------------------

# Committees & Memberships
class CommitteeCreate(ORMBase):
    school_id: UUID
    name: str
    description: Optional[str] = None
    active: bool = True

class CommitteeRead(WithID, WithTimestamps):
    school_id: UUID
    name: str
    description: Optional[str] = None
    active: bool

class CommitteeMembershipCreate(ORMBase):
    committee_id: UUID
    person_id: UUID
    role: Optional[str] = None  # chair | member | secretary | guest
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    voting_member: bool = True

class CommitteeMembershipRead(WithID, WithTimestamps):
    committee_id: UUID
    person_id: UUID
    role: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    voting_member: bool

# Meetings & Agenda
class CICMeetingCreate(ORMBase):
    committee_id: UUID
    scheduled_at: datetime
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None  # planned | in_progress | completed | canceled
    notes: Optional[str] = None

class CICMeetingRead(WithID, WithTimestamps):
    committee_id: UUID
    scheduled_at: datetime
    ends_at: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class CICAgendaItemCreate(ORMBase):
    meeting_id: UUID
    title: str
    description: Optional[str] = None
    presenter_id: Optional[UUID] = None
    position: int = 0
    time_allocated_minutes: Optional[int] = None
    parent_id: Optional[UUID] = None

class CICAgendaItemRead(WithID, WithTimestamps):
    meeting_id: UUID
    title: str
    description: Optional[str] = None
    presenter_id: Optional[UUID] = None
    position: int
    time_allocated_minutes: Optional[int] = None
    parent_id: Optional[UUID] = None

# Motions, Votes, Resolutions
class CICMotionCreate(ORMBase):
    agenda_item_id: UUID
    text: str
    moved_by_id: Optional[UUID] = None
    seconded_by_id: Optional[UUID] = None

class CICMotionRead(WithID, WithTimestamps):
    agenda_item_id: UUID
    text: str
    moved_by_id: Optional[UUID] = None
    seconded_by_id: Optional[UUID] = None
    outcome: Optional[str] = None  # passed | failed | tabled
    tally_for: Optional[int] = None
    tally_against: Optional[int] = None
    tally_abstain: Optional[int] = None

class CICVoteCreate(ORMBase):
    motion_id: UUID
    member_id: UUID
    value: str  # yea | nay | abstain | absent

class CICVoteRead(WithID, WithTimestamps):
    motion_id: UUID
    member_id: UUID
    value: str

class CICResolutionCreate(ORMBase):
    committee_id: UUID
    title: str
    text: Optional[str] = None
    adopted_on: Optional[date] = None
    status: Optional[str] = None  # draft | adopted | rescinded

class CICResolutionRead(WithID, WithTimestamps):
    committee_id: UUID
    title: str
    text: Optional[str] = None
    adopted_on: Optional[date] = None
    status: Optional[str] = None

# Proposals & Reviews
class CurriculumProposalCreate(ORMBase):
    school_id: UUID
    submitted_by_id: UUID
    title: str
    summary: Optional[str] = None
    proposal_type: Optional[str] = None  # new_course | modify_course | textbook | policy
    status: Optional[str] = None         # submitted | under_review | approved | rejected
    submitted_at: Optional[datetime] = None
    target_term_id: Optional[UUID] = None

class CurriculumProposalRead(WithID, WithTimestamps):
    school_id: UUID
    submitted_by_id: UUID
    title: str
    summary: Optional[str] = None
    proposal_type: Optional[str] = None
    status: Optional[str] = None
    submitted_at: Optional[datetime] = None
    target_term_id: Optional[UUID] = None

class ProposalReviewCreate(ORMBase):
    proposal_id: UUID
    reviewer_id: UUID
    decision: Optional[str] = None  # approve | reject | revise
    comments: Optional[str] = None
    reviewed_at: Optional[datetime] = None

class ProposalReviewRead(WithID, WithTimestamps):
    proposal_id: UUID
    reviewer_id: UUID
    decision: Optional[str] = None
    comments: Optional[str] = None
    reviewed_at: Optional[datetime] = None

# Documents (attachments)
class ProposalDocumentCreate(ORMBase):
    proposal_id: UUID
    document_id: UUID
    label: Optional[str] = None

class ProposalDocumentRead(WithID, WithTimestamps):
    proposal_id: UUID
    document_id: UUID
    label: Optional[str] = None

class MeetingDocumentCreate(ORMBase):
    meeting_id: UUID
    document_id: UUID
    label: Optional[str] = None

class MeetingDocumentRead(WithID, WithTimestamps):
    meeting_id: UUID
    document_id: UUID
    label: Optional[str] = None

# Publications (public-facing)
class CICPublicationCreate(ORMBase):
    committee_id: UUID
    meeting_id: Optional[UUID] = None
    public_url: Optional[str] = None
    archive_url: Optional[str] = None
    published_at: Optional[datetime] = None

class CICPublicationRead(WithID, WithTimestamps):
    committee_id: UUID
    meeting_id: Optional[UUID] = None
    public_url: Optional[str] = None
    archive_url: Optional[str] = None
    published_at: Optional[datetime] = None


# === BEGIN: alias shim for acronym class names ===
# Auto-generated to satisfy imports expecting non-all-caps acronym style.
OrmBase = ORMBase
KpiCreate = KPICreate
KpiRead = KPIRead
KpiDatapointCreate = KPIDatapointCreate
KpiDatapointRead = KPIDatapointRead
IepPlanCreate = IEPPlanCreate
IepPlanRead = IEPPlanRead
EllPlanCreate = ELLPlanCreate
EllPlanRead = ELLPlanRead
GpaCalculationCreate = GPACalculationCreate
GpaCalculationRead = GPACalculationRead
SisImportJobCreate = SISImportJobCreate
SisImportJobRead = SISImportJobRead
# === END: alias shim ===
