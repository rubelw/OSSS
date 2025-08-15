"""add states table and seed with U.S. states and DC

Revision ID: add_states_table
Revises: <previous_revision>
Create Date: 2025-08-15 00:00:00
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

# revision identifiers
revision = "0005_add_states_table"
down_revision = "0004_add_cic_tables"
branch_labels = None
depends_on = None

US_STATES_VALUES = """
('AL','Alabama'),('AK','Alaska'),('AZ','Arizona'),('AR','Arkansas'),
('CA','California'),('CO','Colorado'),('CT','Connecticut'),('DE','Delaware'),
('FL','Florida'),('GA','Georgia'),('HI','Hawaii'),('ID','Idaho'),
('IL','Illinois'),('IN','Indiana'),('IA','Iowa'),('KS','Kansas'),
('KY','Kentucky'),('LA','Louisiana'),('ME','Maine'),('MD','Maryland'),
('MA','Massachusetts'),('MI','Michigan'),('MN','Minnesota'),('MS','Mississippi'),
('MO','Missouri'),('MT','Montana'),('NE','Nebraska'),('NV','Nevada'),
('NH','New Hampshire'),('NJ','New Jersey'),('NM','New Mexico'),('NY','New York'),
('NC','North Carolina'),('ND','North Dakota'),('OH','Ohio'),('OK','Oklahoma'),
('OR','Oregon'),('PA','Pennsylvania'),('RI','Rhode Island'),('SC','South Carolina'),
('SD','South Dakota'),('TN','Tennessee'),('TX','Texas'),('UT','Utah'),
('VT','Vermont'),('VA','Virginia'),('WA','Washington'),('WV','West Virginia'),
('WI','Wisconsin'),('WY','Wyoming'),('DC','District of Columbia')
"""

def _has_table(bind, name: str) -> bool:
    insp = sa.inspect(bind)
    return insp.has_table(name)

def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))

def upgrade():
    bind = op.get_bind()

    # 1) Create table if missing
    if not _has_table(bind, "states"):
        op.create_table(
            "states",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("code", sa.String(2), nullable=False, unique=True),
            sa.Column("name", sa.String(64), nullable=False, unique=True),
        )
        op.execute(f"INSERT INTO states (code, name) VALUES {US_STATES_VALUES};")
        return  # done

    # 2) Table exists — add missing bits
    if not _has_column(bind, "states", "code"):
        op.add_column("states", sa.Column("code", sa.String(2), nullable=True))
        # best-effort backfill by name
        op.execute(f"""
        UPDATE states s SET code = m.code
        FROM (VALUES {US_STATES_VALUES}) AS m(code,name)
        WHERE s.name = m.name AND s.code IS NULL;
        """)
        op.alter_column("states", "code", nullable=False)

    # 3) Ensure uniqueness constraints (safe if already present)
    op.execute("""
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_states_code') THEN
            ALTER TABLE states ADD CONSTRAINT uq_states_code UNIQUE (code);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_states_name') THEN
            ALTER TABLE states ADD CONSTRAINT uq_states_name UNIQUE (name);
        END IF;
    END$$;
    """)

def downgrade():
    # conservative rollback: drop uniques and 'code' column if we added it
    bind = op.get_bind()
    if _has_table(bind, "states"):
        op.execute("ALTER TABLE states DROP CONSTRAINT IF EXISTS uq_states_code;")
        op.execute("ALTER TABLE states DROP CONSTRAINT IF EXISTS uq_states_name;")
        if _has_column(bind, "states", "code"):
            op.drop_column("states", "code")
        # If this migration originally created the table in your env, you can drop it:
        # op.drop_table("states")