from __future__ import annotations

import csv
import io
import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0014_2"
down_revision = "0014_1"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "students"

# Inline CSV data for students.
# Header must match the students table columns below exactly.
CSV_DATA = """person_id,student_number,graduation_year,created_at,updated_at,id
2263bbdc-ce79-4481-9435-dec4f5455718,STU0001,2024,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,d4f53e78-1012-5322-a4f3-4bca2efc51be
accd7c7b-385b-41f5-ab3b-c6fb1bfeee4d,STU0002,2025,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,c69e40d1-eeb3-5ecd-bd7d-46b2543ac349
f4bc9013-7d7a-4906-ac02-b292917f0fb2,STU0003,2026,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,244b09b8-8606-55df-8c29-140225ec31b2
a6b98fc3-54fa-4150-9ebf-15385230ecb1,STU0004,2027,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,76a9f47b-bfec-5243-8de4-5988f209feb7
43fdd13c-f007-4101-9fe7-e3fe02698051,STU0005,2028,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,8606c02c-5baa-5b51-9b0c-9cd1bb5fe832
7996f817-0a5a-4597-af29-c919de22322c,STU0006,2029,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,2b779574-bfed-556c-8ce5-9e62cc73025f
43bca8bb-a3b9-48ec-959b-be27748d653f,STU0007,2030,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,a3eaf728-caaf-5ff6-8e3c-cd6b512df107
d954d372-eb49-424e-8fc2-cb4610447314,STU0008,2031,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,0e43dc79-c2a4-5c7d-8016-21414e6de33b
8550e6b9-358e-490d-89bd-f42680224bd4,STU0009,2032,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,938e519e-e267-5750-8a66-5042e402aee4
4166f435-976f-451f-a25f-ff785c245671,STU0010,2033,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,4a2214a1-44a5-570f-8471-4ed19fc1599b
95299ff1-8735-4b58-8f21-b3069210071d,STU0011,2034,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,b01bb891-24d3-570c-af91-53fe613ae196
f62e306a-f92e-488c-9189-311128c41092,STU0012,2035,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,ef91495c-164c-5ddb-b295-335d72682832
1b0123e9-2c11-4a70-8493-8f8f1d55986b,STU0013,2036,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,f3382e77-e831-5dcf-9245-8b7f5e066e47
b101f749-2385-4d42-8c07-7bf58741596d,STU0014,2037,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,243c331c-4187-5fc3-a753-8507ae672faf
fb4d6771-3440-48ba-b8cb-a79d8ded69a3,STU0015,2024,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,873413a0-5c8e-525a-87cd-a28ce74d588c
4e66fc84-4e49-4a5c-8148-5c97330abddf,STU0016,2025,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,d118e568-a365-59f5-8427-ee23dbffba8d
1ba3e85d-daf2-48bf-b8c6-6154f0ab1eaa,STU0017,2026,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,c7b7b486-2fd7-52f5-b454-98bb1848f523
2bf6b36b-27f7-424f-9334-bc6dd1d5041f,STU0018,2027,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,e940a7d2-e5fa-5d70-8e5c-775d38fb5ac2
189d02dd-438a-4e20-8ac3-35ac402314d6,STU0019,2028,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,5d0f6db8-b7f9-5abb-b987-7cf9108f2786
86c7da76-2c84-47b4-8e7c-9f9bb614c16f,STU0020,2029,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,e708eec0-67d0-5cc5-9072-c557c702e17e
cd9dcf87-9751-4a1f-a9ca-8ef04852ff80,STU0021,2030,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,31f5a3ca-2d95-554a-aca1-133d1fb6b801
6ecd6506-4efa-4a08-91d6-1b3cb40f4305,STU0022,2031,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,f7e1a4da-5ab8-53c9-bfae-486e3ce17996
2f94b5bd-e773-4fc3-93c8-0ba1104a9b4f,STU0023,2032,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,b764d434-5af3-54c8-b0fd-98455c00902d
1a9ed98a-dcb3-4418-923e-bd6d43a91c9b,STU0024,2033,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,3ed705a2-f42c-550a-a203-b744278d9a67
d85e4830-62fd-4a50-bd32-3ecbf6a41983,STU0025,2034,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,6fcdb723-443f-5ef6-b747-0da6e15a2929
364114a4-9b72-4fdd-8140-b85bfdafbd7e,STU0026,2035,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,9431f538-cf40-5512-a032-eb9a1642f494
1f537d26-46d0-4631-aeaa-98d92f328b2e,STU0027,2036,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,f8032d9f-f1b7-53db-bbf4-9838d331c2b4
b1119a5d-56da-4dec-b55d-9a3e5dfdca10,STU0028,2037,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,87d1678a-5117-5b0a-87d9-001c72c9135d
5bc44320-8727-4e26-a3c5-fb7d441a7028,STU0029,2024,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,538483fc-c5b9-5a08-a634-be26e3923bea
858f87db-f292-46be-8176-098387fff0dc,STU0030,2025,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,6b3638aa-2a58-58f8-b860-57262708cb69
01614a40-43df-43d6-a8dd-a8b6c7fd538c,STU0031,2026,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,09a8b3a1-8f23-5856-a57a-78c0930c0d40
e93b1ff2-948d-46f4-bc6e-ea6d3aabb948,STU0032,2027,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,db0dc5de-2e18-576e-a3ea-152b301cced5
4ec3a9ce-fa27-4b83-a2d9-d217802e7aef,STU0033,2028,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z,42b94771-000e-52a3-a9b1-869af66783fc
"""


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV string to appropriate Python value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean needs special handling because SQLAlchemy is strict
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL",
                TABLE_NAME,
                col.name,
                raw,
            )
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Load seed data for students from embedded CSV_DATA.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not CSV_DATA.strip():
        log.warning("CSV_DATA is empty for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    f = io.StringIO(CSV_DATA.strip())
    reader = csv.DictReader(f)
    rows = list(reader)

    if not rows:
        log.info("Embedded CSV_DATA for %s is empty", TABLE_NAME)
        return

    inserted = 0
    for raw_row in rows:
        row = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            row[col.name] = value

        if not row:
            continue

        nested = bind.begin_nested()
        try:
            bind.execute(table.insert().values(**row))
            nested.commit()
            inserted += 1
        except (IntegrityError, DataError, StatementError) as exc:
            nested.rollback()
            log.warning(
                "Skipping row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s rows into %s from embedded CSV_DATA", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
