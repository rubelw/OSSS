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
revision = "0015_add_activities_tables"
down_revision = "0014_populate_behavior_codes"
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


    # activities
    op.create_table(
        "activities",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("school_id",sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # events
    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("activity_id", sa.String(36), sa.ForeignKey("activities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("venue", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'draft'")),  # draft|published|cancelled
        sa.Column("attributes", JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('draft','published','cancelled')", name="ck_events_status"),
    )
    op.create_index("ix_events_starts_at", "events", ["starts_at"])

    # ticket_types
    op.create_table(
        "ticket_types",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("price_cents", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("quantity_total", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("quantity_sold", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("sales_starts_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("sales_ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("attributes", JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("event_id", "name", name="uq_event_tickettype_name"),
        sa.CheckConstraint("price_cents >= 0", name="ck_tickettype_price_nonneg"),
        sa.CheckConstraint("quantity_total >= 0", name="ck_tickettype_qty_total_nonneg"),
    )
    op.create_index("ix_ticket_types_event_id", "ticket_types", ["event_id"])

    # orders
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purchaser_user_id",sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("total_cents", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("currency", sa.String(8), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),  # pending|paid|cancelled|refunded
        sa.Column("external_ref", sa.String(255), nullable=True),
        sa.Column("attributes", JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('pending','paid','cancelled','refunded')", name="ck_orders_status"),
        sa.CheckConstraint("total_cents >= 0", name="ck_orders_total_nonneg"),
    )
    op.create_index("ix_orders_event_id", "orders", ["event_id"])

    # tickets
    op.create_table(
        "tickets",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_type_id", sa.String(36), sa.ForeignKey("ticket_types.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("serial_no", sa.Integer, nullable=False),
        sa.Column("price_cents", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("holder_person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("qr_code", sa.String(128), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'issued'")),  # issued|checked_in|void
        sa.Column("issued_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("checked_in_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("ticket_type_id", "serial_no", name="uq_ticket_serial_per_type"),
        sa.CheckConstraint("price_cents >= 0", name="ck_ticket_price_nonneg"),
        sa.CheckConstraint("status IN ('issued','checked_in','void')", name="ck_ticket_status"),
    )
    op.create_index("ix_tickets_order_id", "tickets", ["order_id"])
    op.create_index("ix_tickets_ticket_type_id", "tickets", ["ticket_type_id"])

    # ticket_scans
    op.create_table(
        "ticket_scans",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scanned_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scanned_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("result", sa.String(16), nullable=False),  # ok|duplicate|invalid|void
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("meta", JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("result IN ('ok','duplicate','invalid','void')", name="ck_ticket_scans_result"),
    )
    op.create_index("ix_ticket_scans_ticket_id", "ticket_scans", ["ticket_id"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index("ix_ticket_scans_ticket_id", table_name="ticket_scans")
    op.drop_table("ticket_scans")

    op.drop_index("ix_tickets_ticket_type_id", table_name="tickets")
    op.drop_index("ix_tickets_order_id", table_name="tickets")
    op.drop_table("tickets")

    op.drop_index("ix_orders_event_id", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_ticket_types_event_id", table_name="ticket_types")
    op.drop_table("ticket_types")

    op.drop_index("ix_events_starts_at", table_name="events")
    op.drop_table("events")

    op.drop_table("activities")