from alembic import op
import sqlalchemy as sa

revision = "0003_add_updated_at_to_users"
down_revision = "0002_add_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only add the column if it doesn't already exist (safe for dev)
    bind = op.get_bind()
    insp = sa.inspect(bind)

    cols = {c["name"] for c in insp.get_columns("users")}
    if "updated_at" not in cols:
        op.add_column(
            "users",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        # Optional: drop default after backfilling so app controls it
        op.alter_column("users", "updated_at", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "updated_at")
