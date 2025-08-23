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
revision = "0008_create_cmms_iwms_tables"
down_revision = "0007_populate_schools_table"
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

def upgrade():
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    # Needed for gen_random_uuid() on PG
    if is_pg:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    # For a few places we re-use this pattern
    uuid_col = (
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()"))
        if is_pg else
        sa.Column("id", sa.CHAR(36), primary_key=True)
    )

    # --------------------------
    # IWMS Core: Facilities/Space
    # --------------------------
    op.create_table(
        "facilities",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64), nullable=True, unique=True),
        sa.Column("address", JSONB(), nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_facilities_school", "facilities", ["school_id"])

    op.create_table(
        "buildings",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("facility_id", sa.String(36), sa.ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64), nullable=True, unique=True),
        sa.Column("year_built", sa.Integer, nullable=True),
        sa.Column("floors_count", sa.Integer, nullable=True),
        sa.Column("gross_sqft", sa.Numeric(12, 2), nullable=True),
        sa.Column("use_type", sa.String(64), nullable=True),
        sa.Column("address", JSONB(), nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_buildings_facility", "buildings", ["facility_id"])

    # FIXED: single Column() with the FK inside; no stray comma/paren
    op.create_table(
        "floors",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level_code", sa.String(32), nullable=False),  # e.g., B1, 1, 2, MZ
        sa.Column("name", sa.String(128), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_floors_building", "floors", ["building_id"])

    op.create_table(
        "spaces",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("floor_id", sa.String(36), sa.ForeignKey("floors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),  # room number
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("space_type", sa.String(64), nullable=True),  # classroom, lab, office, gym, etc
        sa.Column("area_sqft", sa.Numeric(12, 2), nullable=True),
        sa.Column("capacity", sa.Integer, nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("building_id", "code", name="uq_spaces_building_code"),
    )
    op.create_index("ix_spaces_building", "spaces", ["building_id"])
    op.create_index("ix_spaces_floor", "spaces", ["floor_id"])

    # --------------------------
    # CMMS Core: Vendors/Parts/Assets
    # --------------------------
    op.create_table(
        "vendors",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("contact", JSONB(), nullable=True),  # phone, email, address
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text, nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "parts",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sku", sa.String(128), nullable=True, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("uom", sa.String(32), nullable=True),  # each, box, ft, gal, etc.
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "part_locations",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("part_id", sa.String(36), sa.ForeignKey("parts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("space_id", sa.String(36), sa.ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("location_code", sa.String(128), nullable=True),  # shelf/bin
        sa.Column("qty_on_hand", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("min_qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("max_qty", sa.Numeric(12, 2), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_part_locations_part", "part_locations", ["part_id"])

    op.create_table(
        "assets",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("space_id", sa.String(36), sa.ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("parent_asset_id", sa.String(36), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tag", sa.String(128), nullable=False),  # asset tag
        sa.Column("serial_no", sa.String(128), nullable=True),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("model", sa.String(255), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),  # HVAC, Electrical, Plumbing, IT, etc.
        sa.Column("status", sa.String(32), nullable=True),    # active, spare, retired
        sa.Column("install_date", sa.Date, nullable=True),
        sa.Column("warranty_expires_at", sa.Date, nullable=True),
        sa.Column("expected_life_months", sa.Integer, nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("tag", name="uq_assets_tag"),
    )
    op.create_index("ix_assets_building", "assets", ["building_id"])
    op.create_index("ix_assets_space", "assets", ["space_id"])

    op.create_table(
        "asset_parts",  # BOM
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("part_id", sa.String(36), sa.ForeignKey("parts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("qty", sa.Numeric(12, 2), nullable=False, server_default=sa.text("1")),
        *_timestamps(),
    )

    op.create_table(
        "meters",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("meter_type", sa.String(64), nullable=True),  # electricity, gas, water, runtime
        sa.Column("uom", sa.String(32), nullable=True),
        sa.Column("last_read_value", sa.Numeric(18, 6), nullable=True),
        sa.Column("last_read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    # --------------------------
    # Work Management
    # --------------------------
    op.create_table(
        "maintenance_requests",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("school_id",   sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("space_id",    sa.String(36), sa.ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_id",    sa.String(36), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submitted_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'new'")),  # new, triaged, converted, closed
        sa.Column("priority", sa.String(16), nullable=True),  # low, normal, high, urgent
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("converted_work_order_id", sa.String(36), nullable=True),  # FK added after work_orders exists
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_requests_status", "maintenance_requests", ["status"])

    op.create_table(
        "work_orders",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("school_id",   sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("space_id",    sa.String(36), sa.ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_id",    sa.String(36), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_id",  sa.String(36), nullable=True),  # FK added after maintenance_requests exists
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'open'")),  # open, in_progress, on_hold, closed, canceled
        sa.Column("priority", sa.String(16), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),   # HVAC, Electrical, Custodial, Grounds, IT, etc
        sa.Column("summary", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("requested_due_at",   sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("scheduled_start_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("scheduled_end_at",   sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at",       sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("assigned_to_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("materials_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("labor_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("other_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_work_orders_status", "work_orders", ["status"])
    op.create_index("ix_work_orders_asset", "work_orders", ["asset_id"])

    # Add the two circular FKs now that both tables exist
    op.create_foreign_key(
        "fk_mr_converted_wo",
        source_table="maintenance_requests",
        referent_table="work_orders",
        local_cols=["converted_work_order_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_wo_request_id",
        source_table="work_orders",
        referent_table="maintenance_requests",
        local_cols=["request_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "work_order_tasks",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("work_order_id", sa.String(36), sa.ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("is_mandatory", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(32), nullable=True),  # todo, done, skipped
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_wo_tasks_wo", "work_order_tasks", ["work_order_id"])

    op.create_table(
        "work_order_time_logs",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("work_order_id", sa.String(36), sa.ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("hours", sa.Numeric(10, 2), nullable=True),
        sa.Column("hourly_rate", sa.Numeric(12, 2), nullable=True),
        sa.Column("cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_wo_time_logs_wo", "work_order_time_logs", ["work_order_id"])

    op.create_table(
        "work_order_parts",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("work_order_id", sa.String(36), sa.ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("part_id", sa.String(36), sa.ForeignKey("parts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("qty", sa.Numeric(12, 2), nullable=False, server_default=sa.text("1")),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("extended_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_wo_parts_wo", "work_order_parts", ["work_order_id"])

    # Preventive Maintenance
    op.create_table(
        "pm_plans",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("frequency", sa.String(64), nullable=True),
        sa.Column("next_due_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("procedure", JSONB(), nullable=True),  # checklist/steps
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_pm_plans_asset", "pm_plans", ["asset_id"])

    op.create_table(
        "pm_work_generators",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pm_plan_id", sa.String(36), sa.ForeignKey("pm_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_generated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("lookahead_days", sa.Integer, nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    # Warranties / Compliance
    op.create_table(
        "warranties",
        uuid_col,
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vendor_id", sa.String(36), sa.ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("policy_no", sa.String(128), nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("terms", sa.Text, nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "compliance_records",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("record_type", sa.String(64), nullable=False),
        sa.Column("authority", sa.String(255), nullable=True),
        sa.Column("identifier", sa.String(128), nullable=True),
        sa.Column("issued_at", sa.Date, nullable=True),
        sa.Column("expires_at", sa.Date, nullable=True),
        sa.Column("documents", JSONB(), nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    # --------------------------
    # IWMS: Reservations / Leases / Projects / Moves
    # --------------------------
    op.create_table(
        "space_reservations",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("space_id", sa.String(36), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("booked_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("purpose", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'booked'")),
        sa.Column("setup", JSONB(), nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_space_resv_space", "space_reservations", ["space_id"])

    op.create_table(
        "leases",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("landlord", sa.String(255), nullable=True),
        sa.Column("tenant", sa.String(255), nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("base_rent", sa.Numeric(14, 2), nullable=True),
        sa.Column("rent_schedule", JSONB(), nullable=True),
        sa.Column("options", JSONB(), nullable=True),
        sa.Column("documents", JSONB(), nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("project_type", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("budget", sa.Numeric(14, 2), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "project_tasks",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("percent_complete", sa.Numeric(5, 2), nullable=True),
        sa.Column("assignee_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "move_orders",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("from_space_id", sa.String(36), sa.ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("to_space_id", sa.String(36), sa.ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("move_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )


def downgrade():
    # Drop in dependency order (children first)
    op.drop_table("move_orders")
    op.drop_table("project_tasks")
    op.drop_table("projects")
    op.drop_table("leases")
    op.drop_index("ix_space_resv_space", table_name="space_reservations")
    op.drop_table("space_reservations")

    op.drop_table("compliance_records")
    op.drop_table("warranties")
    op.drop_index("ix_pm_plans_asset", table_name="pm_plans")
    op.drop_table("pm_work_generators")
    op.drop_table("pm_plans")

    op.drop_index("ix_wo_parts_wo", table_name="work_order_parts")
    op.drop_table("work_order_parts")
    op.drop_index("ix_wo_time_logs_wo", table_name="work_order_time_logs")
    op.drop_table("work_order_time_logs")
    op.drop_index("ix_wo_tasks_wo", table_name="work_order_tasks")
    op.drop_table("work_order_tasks")

    # Drop circular FKs before tables (safe even if DB already dropped with child)
    try:
        op.drop_constraint("fk_wo_request_id", "work_orders", type_="foreignkey")
    except Exception:
        pass
    try:
        op.drop_constraint("fk_mr_converted_wo", "maintenance_requests", type_="foreignkey")
    except Exception:
        pass

    op.drop_index("ix_work_orders_asset", table_name="work_orders")
    op.drop_index("ix_work_orders_status", table_name="work_orders")
    op.drop_table("work_orders")
    op.drop_index("ix_requests_status", table_name="maintenance_requests")
    op.drop_table("maintenance_requests")

    op.drop_index("ix_assets_space", table_name="assets")
    op.drop_index("ix_assets_building", table_name="assets")
    op.drop_table("asset_parts")
    op.drop_table("assets")
    op.drop_index("ix_part_locations_part", table_name="part_locations")
    op.drop_table("part_locations")
    op.drop_table("parts")
    op.drop_table("vendors")

    op.drop_index("ix_spaces_floor", table_name="spaces")
    op.drop_index("ix_spaces_building", table_name="spaces")
    op.drop_table("spaces")
    op.drop_index("ix_floors_building", table_name="floors")
    op.drop_table("floors")
    op.drop_index("ix_buildings_facility", table_name="buildings")
    op.drop_table("buildings")
    op.drop_index("ix_facilities_school", table_name="facilities")
    op.drop_table("facilities")
