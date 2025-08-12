from __future__ import annotations
from typing import Optional, Any, List
from uuid import UUID
from datetime import datetime, date

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


