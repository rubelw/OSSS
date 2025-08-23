from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# Pull the shims from your app (preferred)
try:
    from app.models.base import GUID, JSONB, TSVectorType  # GUID/JSONB TypeDecorator; TSVectorType for PG tsvector
except Exception:
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

    try:
        from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
        class TSVectorType(PG_TSVECTOR):
            pass
    except Exception:
        class TSVectorType(sa.Text):
            pass

# --- Alembic identifiers ---
revision = "0013_add_parentcomms_tables"
down_revision = "0012_add_year_to_fiscal_years"
branch_labels = None
depends_on = None

# ---- Timestamp helpers ----
def _timestamps():
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


def upgrade() -> None:




    # ---- groups/classes and memberships ----
    op.create_table(
        "groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("group_type", sa.String(64), nullable=False),  # e.g., class, club, grade, schoolwide
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", "school_id", name="uq_groups_name_school"),
    )
    op.create_index("ix_groups_school_id", "groups", ["school_id"])
    op.create_index("ix_groups_group_type", "groups", ["group_type"])

    op.create_table(
        "group_members",
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("member_role", sa.String(32), nullable=False, server_default="member"),  # member | owner | teacher
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ---- posts/messages and comments ----


    op.create_table(
        "comments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("post_id", sa.String(36), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_comments_post_id", "comments", ["post_id"])

    # ---- attachments (can attach to post OR comment) ----
    op.create_table(
        "attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("post_id", sa.String(36), sa.ForeignKey("posts.id", ondelete="CASCADE")),
        sa.Column("comment_id", sa.String(36), sa.ForeignKey("comments.id", ondelete="CASCADE")),
        sa.Column("file_url", sa.Text, nullable=False),
        sa.Column("content_type", sa.String(128)),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "(post_id IS NOT NULL) OR (comment_id IS NOT NULL)",
            name="ck_attachments_parent_not_null",
        ),
    )
    op.create_index("ix_attachments_post_id", "attachments", ["post_id"])
    op.create_index("ix_attachments_comment_id", "attachments", ["comment_id"])

    # ---- events & signups ----
    op.create_table(
        "comm_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("location", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_comm_events_group_id", "comm_events", ["group_id"])
    op.create_index("ix_comm_events_starts_at", "comm_events", ["starts_at"])

    op.create_table(
        "event_signups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("comm_event_id", sa.String(36), sa.ForeignKey("comm_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="going"),  # going | maybe | declined
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("comm_event_id", "user_id", name="uq_event_signups_event_user"),
    )
    op.create_index("ix_event_signups_event_id", "event_signups", ["comm_event_id"])
    op.create_index("ix_event_signups_user_id", "event_signups", ["user_id"])

def downgrade() -> None:
    # drop in reverse dependency order

    op.drop_index("ix_event_signups_user_id", table_name="event_signups")
    op.drop_index("ix_event_signups_event_id", table_name="event_signups")
    op.drop_table("event_signups")

    op.drop_index("ix_comm_events_starts_at", table_name="comm_events")
    op.drop_index("ix_comm_events_group_id", table_name="comm_events")
    op.drop_table("comm_events")

    op.drop_index("ix_attachments_comment_id", table_name="attachments")
    op.drop_index("ix_attachments_post_id", table_name="attachments")
    op.drop_table("attachments")

    op.drop_index("ix_comments_post_id", table_name="comments")
    op.drop_table("comments")


    op.drop_table("group_members")

    op.drop_index("ix_groups_group_type", table_name="groups")
    op.drop_index("ix_groups_school_id", table_name="groups")
    op.drop_table("groups")



