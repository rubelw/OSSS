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
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

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
revision = "0004_add_cic_tables"
down_revision = "0003_add_sis_tables"
branch_labels = None
depends_on = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade() -> None:
    # Committees
    op.create_table(
        "cic_committees",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        # scope at district or school; keep both optional so you can use either
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        * _timestamps(),
        sa.CheckConstraint("(organization_id IS NOT NULL) OR (school_id IS NOT NULL)", name="ck_cic_committee_scope")
    )
    op.create_index("ix_cic_committees_scope", "cic_committees", ["organization_id", "school_id"])

    # Memberships (people on the committee)
    op.create_table(
        "cic_memberships",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("committee_id", sa.String(36), sa.ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=True),  # chair, vice-chair, member, secretary, etc.
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("voting_member", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        * _timestamps(),
        sa.UniqueConstraint("committee_id", "person_id", name="uq_cic_membership_unique")
    )
    op.create_index("ix_cic_memberships_committee", "cic_memberships", ["committee_id"])
    op.create_index("ix_cic_memberships_person", "cic_memberships", ["person_id"])

    # Meetings
    op.create_table(
        "cic_meetings",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("committee_id", sa.String(36), sa.ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'scheduled'")),  # scheduled|in_progress|completed|cancelled
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        * _timestamps(),
    )
    op.create_index("ix_cic_meetings_committee", "cic_meetings", ["committee_id"])
    op.create_index("ix_cic_meetings_when", "cic_meetings", ["scheduled_at"])

    # Agenda Items
    op.create_table(
        "cic_agenda_items",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("cic_agenda_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("time_allocated_minutes", sa.Integer(), nullable=True),
        # Optional cross-links (curriculum artifacts)
        sa.Column("subject_id", sa.String(36), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
        * _timestamps(),
        sa.UniqueConstraint("meeting_id", "position", name="uq_cic_agenda_position")
    )
    op.create_index("ix_cic_agenda_items_meeting", "cic_agenda_items", ["meeting_id"])

    # Motions
    op.create_table(
        "cic_motions",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agenda_item_id", sa.String(36), sa.ForeignKey("cic_agenda_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("moved_by_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("seconded_by_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),  # passed|failed|tabled
        sa.Column("tally_for", sa.Integer(), nullable=True),
        sa.Column("tally_against", sa.Integer(), nullable=True),
        sa.Column("tally_abstain", sa.Integer(), nullable=True),
        * _timestamps(),
    )
    op.create_index("ix_cic_motions_agenda_item", "cic_motions", ["agenda_item_id"])

    # Votes
    op.create_table(
        "cic_votes",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("motion_id", sa.String(36), sa.ForeignKey("cic_motions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),  # yea|nay|abstain|absent
        * _timestamps(),
        sa.UniqueConstraint("motion_id", "person_id", name="uq_cic_vote_unique")
    )
    op.create_index("ix_cic_votes_motion", "cic_votes", ["motion_id"])

    # Decisions / Resolutions (meeting-level outcomes)
    op.create_table(
        "cic_resolutions",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),  # adopted|rejected|tabled
        * _timestamps(),
    )

    # Proposals (new course, course change, materials adoption, etc.)
    op.create_table(
        "cic_proposals",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("committee_id", sa.String(36), sa.ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submitted_by_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),  # new_course|course_change|materials_adoption|policy
        sa.Column("subject_id", sa.String(36), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),  # draft|under_review|approved|rejected|withdrawn
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("review_deadline", sa.Date(), nullable=True),
        * _timestamps(),
    )
    op.create_index("ix_cic_proposals_committee", "cic_proposals", ["committee_id"])
    op.create_index("ix_cic_proposals_status", "cic_proposals", ["status"])

    # Proposal Reviews (individual reviews/comments & decisions)
    op.create_table(
        "cic_proposal_reviews",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("cic_proposals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision", sa.Text(), nullable=True),  # approve|reject|revise
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        * _timestamps(),
        sa.UniqueConstraint("proposal_id", "reviewer_id", name="uq_cic_proposal_reviewer")
    )
    op.create_index("ix_cic_proposal_reviews_proposal", "cic_proposal_reviews", ["proposal_id"])

    # Attach documents (reuse your existing 'documents' table if present)
    op.create_table(
        "cic_proposal_documents",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("proposal_id", sa.String(36), sa.ForeignKey("cic_proposals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("file_uri", sa.Text(), nullable=True),  # optional direct URI if not using documents repository
        sa.Column("label", sa.Text(), nullable=True),
        * _timestamps(),
    )

    # Meeting files (agenda packets, minutes drafts, etc.)
    op.create_table(
        "cic_meeting_documents",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("file_uri", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=True),
        * _timestamps(),
    )

    # Public notices / publications for transparency (optional)
    op.create_table(
        "cic_publications",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("meeting_id", sa.String(36), sa.ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("public_url", sa.Text(), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        * _timestamps(),
        sa.UniqueConstraint("meeting_id", "is_final", name="uq_cic_publication_final_once")
    )


def downgrade() -> None:
    op.drop_table("cic_publications")
    op.drop_table("cic_meeting_documents")
    op.drop_table("cic_proposal_documents")
    op.drop_table("cic_proposal_reviews")
    op.drop_table("cic_proposals")
    op.drop_table("cic_resolutions")
    op.drop_table("cic_votes")
    op.drop_table("cic_motions")
    op.drop_table("cic_agenda_items")
    op.drop_table("cic_meetings")
    op.drop_table("cic_memberships")
    op.drop_table("cic_committees")