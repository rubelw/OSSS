"""add domain tables (meetings, policies, planning, evaluations, documents, comms, core)

Revision ID: 0002_add_table
Revises: 0001_init
Create Date: 2025-08-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql
import sqlalchemy as sa
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


# revision identifiers, used by Alembic.
revision = "0002_add_table"
down_revision = "0001_init"
branch_labels = None
depends_on = None

# revision identifiers, used by Alembic.
revision = "0002_add_table"
down_revision = "0001_init"
branch_labels = None
depends_on = None

# ---- Timestamp helpers ----
def _timestamps():
    # NOTE: This sets created_at/updated_at defaults to now().
    # updated_at won't auto-bump on UPDATE without app logic or a DB trigger.
    return (
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

# (Optional) Postgres-only trigger to keep updated_at current for any table that includes it.
# Call _add_updated_at_trigger("document_links") AFTER creating the table if you want DB-side updates.
def _add_updated_at_trigger(table_name: str):
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_proc WHERE proname = 'set_updated_at'
            ) THEN
                CREATE OR REPLACE FUNCTION set_updated_at()
                RETURNS TRIGGER AS $BODY$
                BEGIN
                    NEW.updated_at = CURRENT_TIMESTAMP;
                    RETURN NEW;
                END;
                $BODY$ LANGUAGE plpgsql;
            END IF;
        END$$;
        """
    )
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_trigger
                WHERE tgname = 'trg_{table_name}_updated_at'
            ) THEN
                CREATE TRIGGER trg_{table_name}_updated_at
                BEFORE UPDATE ON {table_name}
                FOR EACH ROW
                EXECUTE FUNCTION set_updated_at();
            END IF;
        END$$;
        """
    )


def upgrade():
    # Enable gen_random_uuid() on Postgres (safe to re-run)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # --- define uuid_col ONCE, then reuse in every op.create_table ---
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    uuid_col = (
        sa.Column("id", sa.String(36), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"))  # Postgres default
        if is_pg else
        sa.Column("id", sa.CHAR(36), primary_key=True)  # e.g., SQLite fallback
    )

    # ---------- Core (shared) ----------
    op.create_table(
        "organizations",
        uuid_col,
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("code", sa.Text(), nullable=True, unique=True),
        *_timestamps(),
    )

    # The bodies table is designed to represent formal groups or governing/decision-making entities within an organization (district). In an SIS context, especially in large districts or Infinite Campus–style systems, schools and districts often have boards, committees, and councils that oversee policy, governance, or targeted areas (e.g., school board, advisory committees, curriculum councils).
    #
    # Think of it as the place where you model organizational structures above the individual school:
    #
    # District School Board (elected or appointed body overseeing all schools)
    #
    # Advisory Councils (e.g., Parent-Teacher Advisory, Student Advisory)
    #
    # Committees (e.g., Curriculum Committee, Safety Committee, Technology Steering Committee)
    #
    # By normalizing these into a table, you can attach memberships, decisions, meetings, and documents to them.

    op.create_table(
        "bodies",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(50), nullable=True),  # e.g., board, committee
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_bodies_org", "bodies", ["org_id"])

    op.create_table(
        "files",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("storage_key", sa.String(512), nullable=False),  # e.g., s3 key or URL
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("size", sa.BigInteger, nullable=True),
        sa.Column("mime_type", sa.String(127), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("label", sa.String(80), nullable=False, unique=True),
    )

    # What entity_tags represents
    #
    # entity_tags is a polymorphic many-to-many junction that lets you attach tags (from a shared tags table) to any kind of record in your system—students, incidents, goals, behavior codes, staff, courses, plans, etc.
    #
    # Instead of having separate join tables like student_tags, goal_tags, incident_tags, you centralize tagging in one place and distinguish the target record by entity_type and entity_id.
    #
    # Typical SIS use-cases:
    #
    # Tag students: IEP, 504, ELL, Gifted, At-Risk.
    #
    # Tag behavior incidents: Bus, Playground, Bullying, Tardy.
    #
    # Tag goals/plans: Literacy, PBIS, Attendance, STEM.
    #
    # Tag staff or committees: Math, SEL, Safety, Bilingual.

    op.create_table(
        "entity_tags",
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("tag_id", sa.String(36), sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("entity_type", "entity_id", "tag_id"),
    )

    # The audit_log table is your system of record for “who did what, when, to what.”
    #
    # In an SIS, you often have strict compliance and accountability needs:
    #
    # FERPA requires tracking access/modification of student records.
    #
    # Districts want visibility into who changed grades, attendance, IEPs, etc.
    #
    # Admins need to troubleshoot changes (e.g., “Why did this student’s enrollment disappear?”).
    #
    # This table lets you store a structured record of all key actions taken across the system.

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),  # created/updated/deleted/published/etc.
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("delta", JSONB(), nullable=True),
    )
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"])

    # ---------- Meetings ----------
    # The meetings table models formal gatherings tied to a district/organization, optionally linked to a governance body (board, committee, council).
    #
    # In a K-12 SIS (e.g., Infinite Campus + board/committee functionality), this provides structure for:
    #
    # School board meetings (policy, budgets, superintendent oversight).
    #
    # Committee meetings (curriculum, safety, technology, parent advisory).
    #
    # Student/parent council meetings (student government, PTO/PTA, advisory councils).
    #
    # Ad-hoc organizational meetings (task forces, hearings, planning groups).
    #
    # It gives administrators a way to schedule, track, and expose meetings (sometimes publicly), while linking them to the governing body that called them.

    op.create_table(
        "meetings",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body_id", sa.String(36), sa.ForeignKey("bodies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),  # draft/published/cancelled
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("stream_url", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_meetings_org", "meetings", ["org_id"])
    op.create_index("ix_meetings_body", "meetings", ["body_id"])

    op.create_table(
        "meeting_permissions",
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("principal_type", sa.String(20), nullable=False),  # user|group|role
        sa.Column("principal_id", sa.String(36), nullable=False),
        sa.Column("permission", sa.String(50), nullable=False),  # view|edit|publish
        sa.PrimaryKeyConstraint("meeting_id", "principal_type", "principal_id", "permission"),
    )

    op.create_table(
        "agenda_items",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=True),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("linked_policy_id", sa.String(36), nullable=True),    # FK added after policies table
        sa.Column("linked_objective_id", sa.String(36), nullable=True), # FK added after objectives table
        sa.Column("time_allocated", sa.Integer, nullable=True),  # minutes
    )
    op.create_index("ix_agenda_items_meeting", "agenda_items", ["meeting_id"])

    op.create_table(
        "agenda_workflows",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "agenda_workflow_steps",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("agenda_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_no", sa.Integer, nullable=False),
        sa.Column("approver_type", sa.String(20), nullable=False),  # user|group|role
        sa.Column("approver_id", sa.String(36), nullable=True),
        sa.Column("rule", sa.String(50), nullable=True),  # all|any|quorum
    )
    op.create_index("ix_agenda_steps_workflow", "agenda_workflow_steps", ["workflow_id"])

    op.create_table(
        "agenda_item_approvals",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.String(36), sa.ForeignKey("agenda_workflow_steps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approver_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decision", sa.String(16), nullable=True),  # approved|rejected
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
    )
    op.create_index("ix_agenda_item_approvals_item", "agenda_item_approvals", ["item_id"])

    op.create_table(
        "motions",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agenda_item_id", sa.String(36), sa.ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("moved_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("seconded_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("passed", sa.Boolean, nullable=True),
        sa.Column("tally_for", sa.Integer, nullable=True),
        sa.Column("tally_against", sa.Integer, nullable=True),
        sa.Column("tally_abstain", sa.Integer, nullable=True),
    )

    op.create_table(
        "votes",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("motion_id", sa.String(36), sa.ForeignKey("motions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("voter_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("value", sa.String(16), nullable=False),  # yea|nay|abstain|absent
        sa.UniqueConstraint("motion_id", "voter_id", name="uq_votes_motion_voter"),
    )

    op.create_table(
        "attendance",
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(16), nullable=True),  # present|absent|late
        sa.Column("arrived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("left_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "minutes",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_minutes_meeting", "minutes", ["meeting_id"])

    op.create_table(
        "meeting_files",
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("caption", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("meeting_id", "file_id"),
    )

    op.create_table(
        "agenda_item_files",
        sa.Column("agenda_item_id", sa.String(36), sa.ForeignKey("agenda_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.Column("caption", sa.String(255), nullable=True),
        sa.PrimaryKeyConstraint("agenda_item_id", "file_id"),
    )

    op.create_table(
        "personal_notes",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_personal_notes_user", "personal_notes", ["user_id"])

    op.create_table(
        "meeting_publications",
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("public_url", sa.String(1024), nullable=True),
        sa.Column("archive_url", sa.String(1024), nullable=True),
    )

    op.create_table(
        "meeting_search_index",
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("ts", TSVectorType(), nullable=True),
    )
    op.create_index("ix_meeting_search_gin", "meeting_search_index", ["ts"], postgresql_using="gin")

    # ---------- Policies ----------
    op.create_table(
        "policies",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(64), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'active'")),
    )
    op.create_index("ix_policies_org", "policies", ["org_id"])

    op.create_table(
        "policy_versions",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False, server_default="1"),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("supersedes_version_id", sa.String(36), sa.ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_policy_versions_policy", "policy_versions", ["policy_id"])

    op.create_table(
        "policy_legal_refs",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("policy_version_id", sa.String(36), sa.ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("citation", sa.String(255), nullable=False),
        sa.Column("url", sa.String(1024), nullable=True),
    )

    op.create_table(
        "policy_comments",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("policy_version_id", sa.String(36), sa.ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("visibility", sa.String(16), nullable=False, server_default=sa.text("'public'")),  # public|private
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_policy_comments_version", "policy_comments", ["policy_version_id"])

    op.create_table(
        "policy_workflows",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "policy_workflow_steps",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workflow_id", sa.String(36), sa.ForeignKey("policy_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_no", sa.Integer, nullable=False),
        sa.Column("approver_type", sa.String(20), nullable=False),
        sa.Column("approver_id", sa.String(36), nullable=True),
        sa.Column("rule", sa.String(50), nullable=True),
    )

    op.create_table(
        "policy_approvals",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("policy_version_id", sa.String(36), sa.ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_id", sa.String(36), sa.ForeignKey("policy_workflow_steps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approver_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
    )

    op.create_table(
        "policy_publications",
        sa.Column("policy_version_id", sa.String(36), sa.ForeignKey("policy_versions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("public_url", sa.String(1024), nullable=True),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "policy_files",
        sa.Column("policy_version_id", sa.String(36), sa.ForeignKey("policy_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("policy_version_id", "file_id"),
    )

    op.create_table(
        "policy_search_index",
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("ts", TSVectorType(), nullable=True),
    )
    op.create_index("ix_policy_search_gin", "policy_search_index", ["ts"], postgresql_using="gin")

    # ---------- Planning ----------
    op.create_table(
        "plans",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("cycle_start", sa.Date, nullable=True),
        sa.Column("cycle_end", sa.Date, nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
    )
    op.create_index("ix_plans_org", "plans", ["org_id"])

    op.create_table(
        "goals",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
    )
    op.create_index("ix_goals_plan", "goals", ["plan_id"])

    op.create_table(
        "objectives",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("goal_id", sa.String(36), sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
    )
    op.create_index("ix_objectives_goal", "objectives", ["goal_id"])

    op.create_table(
        "initiatives",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("objective_id", sa.String(36), sa.ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("priority", sa.String(16), nullable=True),
    )
    op.create_index("ix_initiatives_objective", "initiatives", ["objective_id"])

    op.create_table(
        "kpis",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("goal_id", sa.String(36), sa.ForeignKey("goals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("objective_id", sa.String(36), sa.ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("target", sa.Float, nullable=True),
        sa.Column("baseline", sa.Float, nullable=True),
        sa.Column("direction", sa.String(8), nullable=True),  # up|down
    )

    op.create_table(
        "kpi_datapoints",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kpi_id", sa.String(36), sa.ForeignKey("kpis.id", ondelete="CASCADE"), nullable=False),
        sa.Column("as_of", sa.Date, nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
    )
    op.create_index("ix_kpi_datapoints_kpi", "kpi_datapoints", ["kpi_id"])

    op.create_table(
        "scorecards",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )

    op.create_table(
        "scorecard_kpis",
        sa.Column("scorecard_id", sa.String(36), sa.ForeignKey("scorecards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kpi_id", sa.String(36), sa.ForeignKey("kpis.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_order", sa.Integer, nullable=True),
        sa.PrimaryKeyConstraint("scorecard_id", "kpi_id"),
    )

    op.create_table(
        "plan_assignments",
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("assignee_type", sa.String(20), nullable=False),  # user|group|role
        sa.Column("assignee_id", sa.String(36), nullable=False),
        sa.PrimaryKeyConstraint("entity_type", "entity_id", "assignee_type", "assignee_id"),
    )

    op.create_table(
        "plan_alignments",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agenda_item_id", sa.String(36), sa.ForeignKey("agenda_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("policy_id", sa.String(36), sa.ForeignKey("policies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("objective_id", sa.String(36), sa.ForeignKey("objectives.id", ondelete="SET NULL"), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
    )

    op.create_table(
        "plan_filters",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("criteria", JSONB(), nullable=True),  # saved filters
    )

    op.create_table(
        "plan_search_index",
        sa.Column("plan_id", sa.String(36), sa.ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("ts", TSVectorType(), nullable=True),
    )
    op.create_index("ix_plan_search_gin", "plan_search_index", ["ts"], postgresql_using="gin")

    # ---------- Evaluations ----------
    op.create_table(
        "evaluation_templates",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("for_role", sa.String(80), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "evaluation_sections",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("evaluation_templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("order_no", sa.Integer, nullable=False, server_default="0"),
    )

    op.create_table(
        "evaluation_questions",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("section_id", sa.String(36), sa.ForeignKey("evaluation_sections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("type", sa.String(16), nullable=False),  # scale|text|multi
        sa.Column("scale_min", sa.Integer, nullable=True),
        sa.Column("scale_max", sa.Integer, nullable=True),
        sa.Column("weight", sa.Float, nullable=True),
    )

    op.create_table(
        "evaluation_cycles",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("end_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    op.create_table(
        "evaluation_assignments",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cycle_id", sa.String(36), sa.ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("evaluator_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("evaluation_templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(32), nullable=True),  # assigned|in_progress|submitted|signed
    )
    op.create_index("ix_eval_assignments_cycle", "evaluation_assignments", ["cycle_id"])

    op.create_table(
        "evaluation_responses",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assignment_id", sa.String(36), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value_num", sa.Float, nullable=True),
        sa.Column("value_text", sa.Text, nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("answered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("assignment_id", "question_id", name="uq_eval_response_unique"),
    )

    op.create_table(
        "evaluation_signoffs",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assignment_id", sa.String(36), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("signed_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("note", sa.Text, nullable=True),
    )

    op.create_table(
        "evaluation_files",
        sa.Column("assignment_id", sa.String(36), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("assignment_id", "file_id"),
    )

    op.create_table(
        "evaluation_reports",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cycle_id", sa.String(36), sa.ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", JSONB(), nullable=True),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="SET NULL"), nullable=True),
    )

    # ---------- Documents (repository) ----------
    op.create_table(
        "folders",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("folders.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer, nullable=True),
    )
    op.create_index("ix_folders_org", "folders", ["org_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("folder_id", sa.String(36), sa.ForeignKey("folders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("current_version_id", sa.String(36), nullable=True),  # FK added after document_versions
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False, server_default="1"),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    # now that document_versions exists, tie documents.current_version_id to it
    op.create_foreign_key(
        "fk_documents_current_version",
        "documents",
        "document_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "document_permissions",
        sa.Column("resource_type", sa.String(20), nullable=False),  # folder|document
        sa.Column("resource_id", sa.String(36), nullable=False),
        sa.Column("principal_type", sa.String(20), nullable=False),  # user|group|role
        sa.Column("principal_id", sa.String(36), nullable=False),
        sa.Column("permission", sa.String(20), nullable=False),  # view|edit|manage
        sa.PrimaryKeyConstraint("resource_type", "resource_id", "principal_type", "principal_id", "permission"),
    )

    op.create_table(
        "document_notifications",
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscribed", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("document_id", "user_id"),
    )

    op.create_table(
        "document_activity",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("meta", JSONB(), nullable=True),
    )
    op.create_index("ix_document_activity_doc", "document_activity", ["document_id"])

    op.create_table(
        "document_search_index",
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("ts", TSVectorType(), nullable=True),
    )
    op.create_index("ix_document_search_gin", "document_search_index", ["ts"], postgresql_using="gin")

    # ---------- Communications ----------
    op.create_table(
        "channels",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("audience", sa.String(16), nullable=False, server_default=sa.text("'public'")),  # public|staff|board
        sa.Column("description", sa.Text, nullable=True),
    )
    op.create_index("ix_channels_org", "channels", ["org_id"])

    op.create_table(
        "posts",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),  # draft|scheduled|published
        sa.Column("publish_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_posts_channel", "posts", ["channel_id"])

    op.create_table(
        "post_attachments",
        sa.Column("post_id", sa.String(36), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("post_id", "file_id"),
    )

    op.create_table(
        "subscriptions",
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("principal_type", sa.String(20), nullable=False),  # user|group|role
        sa.Column("principal_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("channel_id", "principal_type", "principal_id"),
    )

    op.create_table(
        "deliveries",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("post_id", sa.String(36), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("delivered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("medium", sa.String(16), nullable=True),  # email|push|rss
        sa.Column("status", sa.String(16), nullable=True),  # sent|failed|opened
    )
    op.create_index("ix_deliveries_post", "deliveries", ["post_id"])

    op.create_table(
        "pages",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.UniqueConstraint("channel_id", "slug", name="uq_pages_channel_slug"),
    )

    op.create_table(
        "document_links",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        *_timestamps(),
    )


    op.create_table(
        "comm_search_index",
        sa.Column("entity_type", sa.String(32), primary_key=True),
        sa.Column("entity_id", sa.String(36), primary_key=True),
        sa.Column("ts", TSVectorType(), nullable=True),
    )
    op.create_index("ix_comm_search_gin", "comm_search_index", ["ts"], postgresql_using="gin")

    # ---------- Cross-cutting ----------
    op.create_table(
        "embeds",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("meta", JSONB(), nullable=True),
    )

    op.create_table(
        "webhooks",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("target_url", sa.String(1024), nullable=False),
        sa.Column("secret", sa.String(255), nullable=True),
        sa.Column("events", psql.ARRAY(sa.String(64)), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_notifications_user", "notifications", ["user_id"])

    op.create_table(
        "feature_flags",
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "retention_rules",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("policy", JSONB(), nullable=False),
    )

    # ---------- Late FKs for agenda_items links ----------
    op.create_foreign_key(
        "fk_agenda_item_linked_policy",
        "agenda_items",
        "policies",
        ["linked_policy_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_agenda_item_linked_objective",
        "agenda_items",
        "objectives",
        ["linked_objective_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    # Reverse order of creation to satisfy FKs
    # Late FKs
    with op.batch_alter_table("agenda_items") as b:
        b.drop_constraint("fk_agenda_item_linked_policy", type_="foreignkey")
        b.drop_constraint("fk_agenda_item_linked_objective", type_="foreignkey")

    # Cross-cutting
    op.drop_table("retention_rules")
    op.drop_table("feature_flags")
    op.drop_index("ix_notifications_user", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("webhooks")
    op.drop_table("embeds")

    # Communications
    op.drop_index("ix_comm_search_gin", table_name="comm_search_index")
    op.drop_table("comm_search_index")
    op.drop_table("pages")
    op.drop_index("ix_deliveries_post", table_name="deliveries")
    op.drop_table("deliveries")
    op.drop_table("subscriptions")
    op.drop_table("post_attachments")
    op.drop_index("ix_posts_channel", table_name="posts")
    op.drop_table("posts")
    op.drop_index("ix_channels_org", table_name="channels")
    op.drop_table("channels")

    # Documents
    op.drop_index("ix_document_search_gin", table_name="document_search_index")
    op.drop_table("document_search_index")
    op.drop_index("ix_document_activity_doc", table_name="document_activity")
    op.drop_table("document_activity")
    op.drop_table("document_notifications")
    op.drop_table("document_permissions")
    op.drop_constraint("fk_documents_current_version", "documents", type_="foreignkey")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_index("ix_folders_org", table_name="folders")
    op.drop_table("folders")

    # Evaluations
    op.drop_table("evaluation_reports")
    op.drop_table("evaluation_files")
    op.drop_table("evaluation_signoffs")
    op.drop_table("evaluation_responses")
    op.drop_index("ix_eval_assignments_cycle", table_name="evaluation_assignments")
    op.drop_table("evaluation_assignments")
    op.drop_table("evaluation_cycles")
    op.drop_table("evaluation_questions")
    op.drop_table("evaluation_sections")
    op.drop_table("evaluation_templates")

    # Planning
    op.drop_index("ix_plan_search_gin", table_name="plan_search_index")
    op.drop_table("plan_search_index")
    op.drop_table("plan_filters")
    op.drop_table("plan_alignments")
    op.drop_table("plan_assignments")
    op.drop_table("scorecard_kpis")
    op.drop_table("scorecards")
    op.drop_index("ix_kpi_datapoints_kpi", table_name="kpi_datapoints")
    op.drop_table("kpi_datapoints")
    op.drop_table("kpis")
    op.drop_index("ix_initiatives_objective", table_name="initiatives")
    op.drop_table("initiatives")
    op.drop_index("ix_objectives_goal", table_name="objectives")
    op.drop_table("objectives")
    op.drop_index("ix_goals_plan", table_name="goals")
    op.drop_table("goals")
    op.drop_index("ix_plans_org", table_name="plans")
    op.drop_table("plans")

    # Policies
    op.drop_index("ix_policy_search_gin", table_name="policy_search_index")
    op.drop_table("policy_search_index")
    op.drop_table("policy_files")
    op.drop_table("policy_publications")
    op.drop_table("policy_approvals")
    op.drop_table("policy_workflow_steps")
    op.drop_table("policy_workflows")
    op.drop_index("ix_policy_comments_version", table_name="policy_comments")
    op.drop_table("policy_comments")
    op.drop_table("policy_legal_refs")
    op.drop_index("ix_policy_versions_policy", table_name="policy_versions")
    op.drop_table("policy_versions")
    op.drop_index("ix_policies_org", table_name="policies")
    op.drop_table("policies")

    # Meetings
    op.drop_index("ix_meeting_search_gin", table_name="meeting_search_index")
    op.drop_table("meeting_search_index")
    op.drop_table("meeting_publications")
    op.drop_index("ix_personal_notes_user", table_name="personal_notes")
    op.drop_table("personal_notes")
    op.drop_table("agenda_item_files")
    op.drop_table("meeting_files")
    op.drop_index("ix_minutes_meeting", table_name="minutes")
    op.drop_table("minutes")
    op.drop_table("attendance")
    op.drop_table("votes")
    op.drop_table("motions")
    op.drop_index("ix_agenda_item_approvals_item", table_name="agenda_item_approvals")
    op.drop_table("agenda_item_approvals")
    op.drop_index("ix_agenda_steps_workflow", table_name="agenda_workflow_steps")
    op.drop_table("agenda_workflow_steps")
    op.drop_table("agenda_workflows")
    op.drop_index("ix_agenda_items_meeting", table_name="agenda_items")
    op.drop_table("agenda_items")
    op.drop_table("meeting_permissions")
    op.drop_index("ix_meetings_body", table_name="meetings")
    op.drop_index("ix_meetings_org", table_name="meetings")
    op.drop_table("meetings")

    # Core
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("entity_tags")
    op.drop_table("tags")
    op.drop_table("files")
    op.drop_index("ix_bodies_org", table_name="bodies")
    op.drop_table("bodies")
    op.drop_table("organizations")
