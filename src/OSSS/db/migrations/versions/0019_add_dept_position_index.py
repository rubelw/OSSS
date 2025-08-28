from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Alembic identifiers
revision = "0019_add_dept_position_index"
down_revision = "0018_populate_positions"
branch_labels = None
depends_on = None

TABLE = "department_position_index"
SCHEMA = None  # set to your schema (e.g., "public") if you use one

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(TABLE, schema=SCHEMA):
        op.create_table(
            TABLE,
            sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("department_id", "position_id", name=f"{TABLE}_pk"),
            sa.ForeignKeyConstraint(
                ["department_id"], ["departments.id"], ondelete="CASCADE", name=f"{TABLE}_department_id_fkey"
            ),
            sa.ForeignKeyConstraint(
                ["position_id"], ["hr_positions.id"], ondelete="CASCADE", name=f"{TABLE}_position_id_fkey"
            ),
            schema=SCHEMA,
        )
    else:
        # Optional: backfill missing columns/constraints if the table was created elsewhere.
        cols = {c["name"] for c in insp.get_columns(TABLE, schema=SCHEMA)}
        if "created_at" not in cols:
            op.add_column(
                TABLE,
                sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
                schema=SCHEMA,
            )
        # You could also inspect PK/FKs and add them if missing with op.create_primary_key / op.create_foreign_key.

def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table(TABLE, schema=SCHEMA):
        op.drop_table(TABLE, schema=SCHEMA)
