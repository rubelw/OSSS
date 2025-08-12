from __future__ import annotations
from fastapi.security import HTTPBearer, OAuth2AuthorizationCodeBearer
from fastapi import FastAPI, Depends, status, Security
from typing import List, Type, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from fastapi.openapi.utils import get_openapi
from .settings import settings
from .auth_keycloak import (
    get_current_claims,
    require_realm_roles,
    require_any_realm_role,
    require_client_roles,
    require_any_client_role,
    require_groups,
    require_scopes,
)
from .database import get_session
from .user_models import User
from .schemas import UserCreate, UserRead

# --- NEW: import the domain models & schemas ---
from . import models  # relies on app/models/__init__.py exporting all
from . import schemas as S

app = FastAPI(title=settings.APP_NAME, version="1.0.0")

# Browser-facing URL for the OAuth popup
KEYCLOAK_PUBLIC = (getattr(settings, "KEYCLOAK_PUBLIC_URL", None) or settings.KEYCLOAK_SERVER_URL).rstrip("/")
realm = settings.KEYCLOAK_REALM

SECURITY = {"security": [{"KeycloakOAuth2": ["openid"]}]}
DEPS = [Depends(require_realm_roles("admin"))]


# Show both options in Swagger: OAuth2 (Keycloak) and simple Bearer
oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{KEYCLOAK_PUBLIC}/realms/{realm}/protocol/openid-connect/auth",
    tokenUrl=f"{KEYCLOAK_PUBLIC}/realms/{realm}/protocol/openid-connect/token",
    scopes={"openid": "OpenID Connect", "profile": "Basic profile", "email": "Email"},
    scheme_name="KeycloakOAuth2",
)
bearer_scheme = HTTPBearer(scheme_name="BearerAuth")

# Help Swagger’s OAuth popup
app.swagger_ui_init_oauth = {
    "clientId": settings.KEYCLOAK_CLIENT_ID,
    "usePkceWithAuthorizationCodeGrant": True,
    "scopes": "openid profile email",
}

# Patch OpenAPI so ALL routes advertise OAuth2(openid) OR Bearer
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version="1.0.0", routes=app.routes)
    comps = schema.setdefault("components", {}).setdefault("securitySchemes", {})
    comps["KeycloakOAuth2"] = {
        "type": "oauth2",
        "flows": {
            "authorizationCode": {
                "authorizationUrl": f"{KEYCLOAK_PUBLIC}/realms/{realm}/protocol/openid-connect/auth",
                "tokenUrl": f"{KEYCLOAK_PUBLIC}/realms/{realm}/protocol/openid-connect/token",
                "scopes": {"openid": "OpenID Connect", "profile": "Basic profile", "email": "Email"},
            }
        },
    }
    comps["BearerAuth"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    schema["security"] = [{"KeycloakOAuth2": ["openid"]}, {"BearerAuth": []}]
    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

# -------------------------------------------------
# Helpers to reduce CRUD boilerplate
# -------------------------------------------------
def add_crud(
    resource,
    model_cls,
    read_schema,
    create_schema=None,
    read_dep=Depends(get_current_claims),
    write_dep=Depends(get_current_claims),
    *,
    openapi_extra: dict | None = None,
    dependencies: list | None = None,
):

    extra = openapi_extra or {}
    deps = dependencies or []

    # GET
    async def list_items(session=Depends(get_session), _=read_dep):
        res = await session.execute(select(model_cls))
        return res.scalars().all()
    list_items.__annotations__ = {"return": list[read_schema]}
    app.add_api_route(
        f"/{resource}",
        list_items,
        methods=["GET"],
        response_model=list[read_schema],
        openapi_extra=extra,
        dependencies=deps,
    )

    # POST (if enabled)
    if create_schema is not None:
        async def create_item(payload, session=Depends(get_session), _=write_dep):
            obj = model_cls(**payload.model_dump(exclude_unset=True))
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

        create_item.__annotations__ = {"payload": create_schema, "return": read_schema}

        app.add_api_route(
            f"/{resource}",
            create_item,
            methods=["POST"],
            response_model=read_schema,
            status_code=201,
            openapi_extra=extra,
            dependencies=deps,
        )

@app.get("/_debug/claims")
async def debug_claims(claims = Depends(get_current_claims)):
    return claims

@app.get("/health")
async def health():
    return {"ok": True}

@app.get(
    "/me",
    openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}, {"BearerAuth": []}]},
)


async def me(_=Security(oauth2_scheme), claims=Depends(get_current_claims)):
    # `oauth2_scheme` only informs docs; `get_current_claims` does real validation
    return {
        "sub": claims.get("sub"),
        "preferred_username": claims.get("preferred_username"),
        "email": claims.get("email"),
        "iss": claims.get("iss"),
        "aud": claims.get("aud"),
        "realm_access": claims.get("realm_access", {}).get("roles", []) or [],
        "raw": claims.get("scope") or claims.get("scp") or []


    }


@app.get("/users", openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))], response_model=List[UserRead])
async def list_users(session: AsyncSession = Depends(get_session), _=Depends(get_current_claims)):
    res = await session.execute(select(User))
    return res.scalars().all()

@app.post("/users", response_model=UserRead, openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))],status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, session: AsyncSession = Depends(get_session), _=Depends(get_current_claims)):
    u = User(id=uuid4(), username=payload.username, email=str(payload.email))
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u



# -------------------------------------------------
# Core (shared)
# -------------------------------------------------
add_crud("organizations", models.Organization, S.OrganizationRead, S.OrganizationCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("bodies", models.Body, S.BodyRead, S.BodyCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("files", models.File, S.FileRead, S.FileCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("tags", models.Tag, S.TagRead, S.TagCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("entity-tags", models.EntityTag, S.EntityTagCreate, S.EntityTagCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
# Audit log is usually system-generated → GET only
add_crud("audit-log", models.AuditLog, S.AuditLogRead, create_schema=None,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("embeds", models.Embed, S.EmbedRead, S.EmbedCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("webhooks", models.Webhook, S.WebhookRead, S.WebhookCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
# Notifications are typically emitted by the app → GET only
add_crud("notifications", models.Notification, S.NotificationRead, create_schema=None,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("feature-flags", models.FeatureFlag, S.FeatureFlagUpsert, S.FeatureFlagUpsert,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("retention-rules", models.RetentionRule, S.RetentionRuleRead, S.RetentionRuleCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])

# -------------------------------------------------
# Meetings
# -------------------------------------------------
add_crud("meetings", models.Meeting, S.MeetingRead,S.MeetingCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("meeting-permissions", models.MeetingPermission, S.MeetingPermissionCreate, S.MeetingPermissionCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("agenda-items", models.AgendaItem, S.AgendaItemRead, S.AgendaItemCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("agenda-workflows", models.AgendaWorkflow, S.AgendaWorkflowRead, S.AgendaWorkflowCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("agenda-workflow-steps", models.AgendaWorkflowStep, S.AgendaWorkflowStepRead, S.AgendaWorkflowStepCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("agenda-item-approvals", models.AgendaItemApproval, S.AgendaItemApprovalRead, S.AgendaItemApprovalCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("motions", models.Motion, S.MotionRead, S.MotionCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("votes", models.Vote, S.VoteRead, S.VoteCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("attendance", models.Attendance, S.AttendanceRead, S.AttendanceUpsert,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("minutes", models.Minutes, S.MinutesRead, S.MinutesCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("meeting-files", models.MeetingFile, S.MeetingFileLinkCreate, S.MeetingFileLinkCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("agenda-item-files", models.AgendaItemFile, S.AgendaItemFileLinkCreate, S.AgendaItemFileLinkCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("personal-notes", models.PersonalNote, S.PersonalNoteRead, S.PersonalNoteCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("meeting-publications", models.MeetingPublication, S.MeetingPublicationRead, S.MeetingPublicationCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
# meeting_search_index is internal → omit POST

# -------------------------------------------------
# Policies
# -------------------------------------------------
add_crud("policies", models.Policy, S.PolicyRead, S.PolicyCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("policy-versions", models.PolicyVersion, S.PolicyVersionRead, S.PolicyVersionCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("policy-legal-refs", models.PolicyLegalRef, S.PolicyLegalRefRead, S.PolicyLegalRefCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("policy-comments", models.PolicyComment, S.PolicyCommentRead, S.PolicyCommentCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("policy-workflows", models.PolicyWorkflow, S.PolicyWorkflowRead, S.PolicyWorkflowCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("policy-workflow-steps", models.PolicyWorkflowStep, S.PolicyWorkflowStepRead, S.PolicyWorkflowStepCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("policy-approvals", models.PolicyApproval, S.PolicyApprovalRead, S.PolicyApprovalCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("policy-files", models.PolicyFile, S.PolicyFileLinkCreate, S.PolicyFileLinkCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
# Publications are often system/publish action – read only in this basic API:
add_crud("policy-publications", models.PolicyPublication, S.PolicyPublicationRead, create_schema=None,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
# policy_search_index is internal → omit POST

# -------------------------------------------------
# Planning
# -------------------------------------------------
add_crud("plans", models.Plan, S.PlanRead, S.PlanCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("goals", models.Goal, S.GoalRead, S.GoalCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("objectives", models.Objective, S.ObjectiveRead, S.ObjectiveCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("initiatives", models.Initiative, S.InitiativeRead, S.InitiativeCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("kpis", models.KPI, S.KPIRead, S.KPICreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("kpi-datapoints", models.KPIDatapoint, S.KPIDatapointRead, S.KPIDatapointCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("scorecards", models.Scorecard, S.ScorecardRead, S.ScorecardCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("scorecard-kpis", models.ScorecardKPI, S.ScorecardKPIAttach, S.ScorecardKPIAttach,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("plan-assignments", models.PlanAssignment, S.PlanAssignmentCreate, S.PlanAssignmentCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("plan-alignments", models.PlanAlignment, S.PlanAlignmentCreate, S.PlanAlignmentCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("plan-filters", models.PlanFilter, S.PlanFilterRead, S.PlanFilterCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
# plan_search_index is internal → omit POST

# -------------------------------------------------
# Evaluations
# -------------------------------------------------
add_crud("evaluation-templates", models.EvaluationTemplate, S.EvaluationTemplateRead, S.EvaluationTemplateCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("evaluation-sections", models.EvaluationSection, S.EvaluationSectionRead, S.EvaluationSectionCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("evaluation-questions", models.EvaluationQuestion, S.EvaluationQuestionRead, S.EvaluationQuestionCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("evaluation-cycles", models.EvaluationCycle, S.EvaluationCycleRead, S.EvaluationCycleCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("evaluation-assignments", models.EvaluationAssignment, S.EvaluationAssignmentRead, S.EvaluationAssignmentCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("evaluation-responses", models.EvaluationResponse, S.EvaluationResponseRead, S.EvaluationResponseCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("evaluation-signoffs", models.EvaluationSignoff, S.EvaluationSignoffRead, S.EvaluationSignoffCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("evaluation-files", models.EvaluationFile, S.EvaluationFileLinkCreate, S.EvaluationFileLinkCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
# evaluation_reports are generated → GET only
add_crud("evaluation-reports", models.EvaluationReport, S.EvaluationReportRead, create_schema=None,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])

# -------------------------------------------------
# Documents (repository)
# -------------------------------------------------
add_crud("folders", models.Folder, S.FolderRead, S.FolderCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("documents", models.Document, S.DocumentRead, S.DocumentCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("document-versions", models.DocumentVersion, S.DocumentVersionRead, S.DocumentVersionCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("document-permissions", models.DocumentPermission, S.DocumentPermissionUpsert, S.DocumentPermissionUpsert,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("document-notifications", models.DocumentNotification, S.DocumentNotificationRead, S.DocumentNotificationUpsert,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("document-activity", models.DocumentActivity, S.DocumentActivityRead, create_schema=None,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
# document_search_index is internal → omit POST

# -------------------------------------------------
# Communications
# -------------------------------------------------
add_crud("channels", models.Channel, S.ChannelRead, S.ChannelCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("posts", models.Post, S.PostRead, S.PostCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("post-attachments", models.PostAttachment, S.PostAttachmentLinkCreate, S.PostAttachmentLinkCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("subscriptions", models.Subscription, S.SubscriptionRead, S.SubscriptionCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
add_crud("deliveries", models.Delivery, S.DeliveryRead, create_schema=None,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])  # typically system/worker generated
add_crud("pages", models.Page, S.PageRead, S.PageCreate,openapi_extra={"security": [{"KeycloakOAuth2": ["openid"]}]},dependencies=[Depends(require_realm_roles("admin"))])
# comm_search_index is internal → omit POST

# ---- Auto-generated CRUD registrations ----
add_crud("districts", models.District, S.DistrictRead, S.DistrictCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("schools", models.School, S.SchoolRead, S.SchoolCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("academic_terms", models.AcademicTerm, S.AcademicTermRead, S.AcademicTermCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("grading_periods", models.GradingPeriod, S.GradingPeriodRead, S.GradingPeriodCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("calendars", models.Calendar, S.CalendarRead, S.CalendarCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("calendar_days", models.CalendarDay, S.CalendarDayRead, S.CalendarDayCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("bell_schedules", models.BellSchedule, S.BellScheduleRead, S.BellScheduleCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("periods", models.Period, S.PeriodRead, S.PeriodCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("grade_levels", models.GradeLevel, S.GradeLevelRead, S.GradeLevelCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("departments", models.Department, S.DepartmentRead, S.DepartmentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("subjects", models.Subject, S.SubjectRead, S.SubjectCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("courses", models.Course, S.CourseRead, S.CourseCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("course_sections", models.CourseSection, S.CourseSectionRead, S.CourseSectionCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("rooms", models.Room, S.RoomRead, S.RoomCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("persons", models.Person, S.PersonRead, S.PersonCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("students", models.Student, S.StudentRead, S.StudentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("staff", models.Staff, S.StaffRead, S.StaffCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("guardians", models.Guardian, S.GuardianRead, S.GuardianCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("user_accounts", models.UserAccount, S.UserAccountRead, S.UserAccountCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("roles", models.Role, S.RoleRead, S.RoleCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("permissions", models.Permission, S.PermissionRead, S.PermissionCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("role_permissions", models.RolePermission, S.RolePermissionRead, S.RolePermissionCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("addresses", models.Address, S.AddressRead, S.AddressCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("contacts", models.Contact, S.ContactRead, S.ContactCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("person_addresses", models.PersonAddress, S.PersonAddressRead, S.PersonAddressCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("person_contacts", models.PersonContact, S.PersonContactRead, S.PersonContactCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("student_guardians", models.StudentGuardian, S.StudentGuardianRead, S.StudentGuardianCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("external_ids", models.ExternalId, S.ExternalIdRead, S.ExternalIdCreate, openapi_extra=SECURITY, dependencies=DEPS)

# Enrollment & Programs
add_crud("student_school_enrollments", models.StudentSchoolEnrollment, S.StudentSchoolEnrollmentRead, S.StudentSchoolEnrollmentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("student_program_enrollments", models.StudentProgramEnrollment, S.StudentProgramEnrollmentRead, S.StudentProgramEnrollmentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("special_education_cases", models.SpecialEducationCase, S.SpecialEducationCaseRead, S.SpecialEducationCaseCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("iep_plans", models.IepPlan, S.IepPlanRead, S.IepPlanCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("accommodations", models.Accommodation, S.AccommodationRead, S.AccommodationCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("ell_plans", models.EllPlan, S.EllPlanRead, S.EllPlanCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("section504_plans", models.Section504Plan, S.Section504PlanRead, S.Section504PlanCreate, openapi_extra=SECURITY, dependencies=DEPS)

# Scheduling
add_crud("section_meetings", models.SectionMeeting, S.SectionMeetingRead, S.SectionMeetingCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("teacher_section_assignments", models.TeacherSectionAssignment, S.TeacherSectionAssignmentRead, S.TeacherSectionAssignmentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("student_section_enrollments", models.StudentSectionEnrollment, S.StudentSectionEnrollmentRead, S.StudentSectionEnrollmentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("course_prerequisites", models.CoursePrerequisite, S.CoursePrerequisiteRead, S.CoursePrerequisiteCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("section_room_assignments", models.SectionRoomAssignment, S.SectionRoomAssignmentRead, S.SectionRoomAssignmentCreate, openapi_extra=SECURITY, dependencies=DEPS)

# Attendance
add_crud("attendance_codes", models.AttendanceCode, S.AttendanceCodeRead, S.AttendanceCodeCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("attendance_events", models.AttendanceEvent, S.AttendanceEventRead, S.AttendanceEventCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("attendance_daily_summary", models.AttendanceDailySummary, S.AttendanceDailySummaryRead, S.AttendanceDailySummaryCreate, openapi_extra=SECURITY, dependencies=DEPS)

# Assessment, Grades & Transcripts
add_crud("grade_scales", models.GradeScale, S.GradeScaleRead, S.GradeScaleCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("grade_scale_bands", models.GradeScaleBand, S.GradeScaleBandRead, S.GradeScaleBandCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("assignment_categories", models.AssignmentCategory, S.AssignmentCategoryRead, S.AssignmentCategoryCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("assignments", models.Assignment, S.AssignmentRead, S.AssignmentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("gradebook_entries", models.GradebookEntry, S.GradebookEntryRead, S.GradebookEntryCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("final_grades", models.FinalGrade, S.FinalGradeRead, S.FinalGradeCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("gpa_calculations", models.GpaCalculation, S.GpaCalculationRead, S.GpaCalculationCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("class_ranks", models.ClassRank, S.ClassRankRead, S.ClassRankCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("report_cards", models.ReportCard, S.ReportCardRead, S.ReportCardCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("transcript_lines", models.TranscriptLine, S.TranscriptLineRead, S.TranscriptLineCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("standardized_tests", models.StandardizedTest, S.StandardizedTestRead, S.StandardizedTestCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("test_administrations", models.TestAdministration, S.TestAdministrationRead, S.TestAdministrationCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("test_results", models.TestResult, S.TestResultRead, S.TestResultCreate, openapi_extra=SECURITY, dependencies=DEPS)

# Behavior & Discipline
add_crud("behavior_codes", models.BehaviorCode, S.BehaviorCodeRead, S.BehaviorCodeCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("consequence_types", models.ConsequenceType, S.ConsequenceTypeRead, S.ConsequenceTypeCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("incidents", models.Incident, S.IncidentRead, S.IncidentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("incident_participants", models.IncidentParticipant, S.IncidentParticipantRead, S.IncidentParticipantCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("consequences", models.Consequence, S.ConsequenceRead, S.ConsequenceCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("behavior_interventions", models.BehaviorIntervention, S.BehaviorInterventionRead, S.BehaviorInterventionCreate, openapi_extra=SECURITY, dependencies=DEPS)

# Health & Safety
add_crud("health_profiles", models.HealthProfile, S.HealthProfileRead, S.HealthProfileCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("immunizations", models.Immunization, S.ImmunizationRead, S.ImmunizationCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("immunization_records", models.ImmunizationRecord, S.ImmunizationRecordRead, S.ImmunizationRecordCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("medications", models.Medication, S.MedicationRead, S.MedicationCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("medication_administrations", models.MedicationAdministration, S.MedicationAdministrationRead, S.MedicationAdministrationCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("nurse_visits", models.NurseVisit, S.NurseVisitRead, S.NurseVisitCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("emergency_contacts", models.EmergencyContact, S.EmergencyContactRead, S.EmergencyContactCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("consents", models.Consent, S.ConsentRead, S.ConsentCreate, openapi_extra=SECURITY, dependencies=DEPS)

# Fees, Meals, Transportation, Library
add_crud("fees", models.Fee, S.FeeRead, S.FeeCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("invoices", models.Invoice, S.InvoiceRead, S.InvoiceCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("payments", models.Payment, S.PaymentRead, S.PaymentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("waivers", models.Waiver, S.WaiverRead, S.WaiverCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("meal_accounts", models.MealAccount, S.MealAccountRead, S.MealAccountCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("meal_transactions", models.MealTransaction, S.MealTransactionRead, S.MealTransactionCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("meal_eligibility_statuses", models.MealEligibilityStatus, S.MealEligibilityStatusRead, S.MealEligibilityStatusCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("bus_routes", models.BusRoute, S.BusRouteRead, S.BusRouteCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("bus_stops", models.BusStop, S.BusStopRead, S.BusStopCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("bus_stop_times", models.BusStopTime, S.BusStopTimeRead, S.BusStopTimeCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("student_transportation_assignments", models.StudentTransportationAssignment, S.StudentTransportationAssignmentRead, S.StudentTransportationAssignmentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("library_items", models.LibraryItem, S.LibraryItemRead, S.LibraryItemCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("library_checkouts", models.LibraryCheckout, S.LibraryCheckoutRead, S.LibraryCheckoutCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("library_holds", models.LibraryHold, S.LibraryHoldRead, S.LibraryHoldCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("library_fines", models.LibraryFine, S.LibraryFineRead, S.LibraryFineCreate, openapi_extra=SECURITY, dependencies=DEPS)

# Communication & Engagement
add_crud("messages", models.Message, S.MessageRead, S.MessageCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("message_recipients", models.MessageRecipient, S.MessageRecipientRead, S.MessageRecipientCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("family_portal_access", models.FamilyPortalAccess, S.FamilyPortalAccessRead, S.FamilyPortalAccessCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("documents", models.Document, S.DocumentRead, S.DocumentCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("document_links", models.DocumentLink, S.DocumentLinkRead, S.DocumentLinkCreate, openapi_extra=SECURITY, dependencies=DEPS)

# State Reporting & Auditing
add_crud("state_reporting_snapshots", models.StateReportingSnapshot, S.StateReportingSnapshotRead, S.StateReportingSnapshotCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("export_runs", models.ExportRun, S.ExportRunRead, S.ExportRunCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("audit_logs", models.AuditLog, S.AuditLogRead, S.AuditLogCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("data_sharing_agreements", models.DataSharingAgreement, S.DataSharingAgreementRead, S.DataSharingAgreementCreate, openapi_extra=SECURITY, dependencies=DEPS)

# Analytics & ETL Support
add_crud("sis_import_jobs", models.SisImportJob, S.SisImportJobRead, S.SisImportJobCreate, openapi_extra=SECURITY, dependencies=DEPS)
add_crud("data_quality_issues", models.DataQualityIssue, S.DataQualityIssueRead, S.DataQualityIssueCreate, openapi_extra=SECURITY, dependencies=DEPS)

# -----------------------------
# CIC (Curriculum & Instruction Committee)
# -----------------------------
add_crud(
    "cic_committees",
    models.CICCommittee,
    S.CommitteeRead,
    S.CommitteeCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_memberships",
    models.CICMembership,
    S.CommitteeMembershipRead,
    S.CommitteeMembershipCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_meetings",
    models.CICMeeting,
    S.CICMeetingRead,
    S.CICMeetingCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_agenda_items",
    models.CICAgendaItem,
    S.CICAgendaItemRead,
    S.CICAgendaItemCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_motions",
    models.CICMotion,
    S.CICMotionRead,
    S.CICMotionCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_votes",
    models.CICVote,
    S.CICVoteRead,
    S.CICVoteCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_resolutions",
    models.CICResolution,
    S.CICResolutionRead,
    S.CICResolutionCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_proposals",
    models.CICProposal,
    S.CurriculumProposalRead,
    S.CurriculumProposalCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_proposal_reviews",
    models.CICProposalReview,
    S.ProposalReviewRead,
    S.ProposalReviewCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_proposal_documents",
    models.CICProposalDocument,
    S.ProposalDocumentRead,
    S.ProposalDocumentCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_meeting_documents",
    models.CICMeetingDocument,
    S.MeetingDocumentRead,
    S.MeetingDocumentCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)

add_crud(
    "cic_publications",
    models.CICPublication,
    S.CICPublicationRead,
    S.CICPublicationCreate,
    openapi_extra=SECURITY,
    dependencies=DEPS,
)
