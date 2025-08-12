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