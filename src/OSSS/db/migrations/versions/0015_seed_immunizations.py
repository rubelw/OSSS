from __future__ import annotations

import logging
import uuid
import random
import datetime as dt

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0015"
down_revision = "0014_2"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "immunizations"
STUDENTS_TABLE_NAME = "students"

VACCINE_NAMES = ["MMR", "DTaP", "Polio", "Varicella", "HepB"]
BASE_DATE = dt.date(2024, 8, 1)
DATE_RANGE_DAYS = 120


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python value to appropriate DB value."""
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

    # Dates: allow date/datetime → ISO string, DB can cast
    if isinstance(raw, (dt.date, dt.datetime)):
        return raw.isoformat()

    # Otherwise, pass raw through and let DB cast (e.g. ints, strings)
    return raw


def upgrade() -> None:
    """Generate random immunizations for ~75% of students in the students table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Ensure tables exist
    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not inspector.has_table(STUDENTS_TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", STUDENTS_TABLE_NAME)
        return

    metadata = sa.MetaData()
    immun_table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)
    students_table = sa.Table(STUDENTS_TABLE_NAME, metadata, autoload_with=bind)

    # Quick check: if immunizations already has rows, skip to avoid duplicates
    existing = bind.execute(sa.select(sa.func.count()).select_from(immun_table)).scalar()
    if existing and existing > 0:
        log.info(
            "%s already has %s rows; skipping random immunization seed",
            TABLE_NAME,
            existing,
        )
        return

    # We assume students table has a "student_number" column that maps to
    # immunizations.student_local_id
    if "student_number" not in students_table.c:
        log.warning(
            "%s.student_number column not found; cannot seed immunizations",
            STUDENTS_TABLE_NAME,
        )
        return

    # Also ensure immunizations has student_local_id
    if "student_local_id" not in immun_table.c:
        log.warning(
            "%s.student_local_id column not found; cannot seed immunizations",
            TABLE_NAME,
        )
        return

    # Fetch all student local IDs
    result = bind.execute(sa.select(students_table.c.student_number))
    student_numbers = [row[0] for row in result]

    if not student_numbers:
        log.info("No students found; skipping immunization seed")
        return

    total_students = len(student_numbers)

    # Select ~75% of students at random (but at least 1)
    random.seed(42)  # deterministic for repeatable migrations
    random.shuffle(student_numbers)
    target_count = max(1, int(total_students * 0.75))
    selected_students = student_numbers[:target_count]

    inserted = 0

    for student_local_id in selected_students:
        # Generate one random immunization per selected student
        vaccine_name = random.choice(VACCINE_NAMES)
        dose_number = 1  # could randomize if you want multiple doses
        random_offset = dt.timedelta(days=random.randint(0, DATE_RANGE_DAYS))
        date_administered = BASE_DATE + random_offset

        raw_row = {
            "id": str(uuid.uuid4()),
            "student_local_id": student_local_id,
            "vaccine_name": vaccine_name,
            "dose_number": dose_number,
            "date_administered": date_administered,
        }

        row = {}
        # Only include columns that actually exist on the table
        for col in immun_table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            row[col.name] = value

        if not row:
            continue

        nested = bind.begin_nested()
        try:
            bind.execute(immun_table.insert().values(**row))
            nested.commit()
            inserted += 1
        except (IntegrityError, DataError, StatementError) as exc:
            nested.rollback()
            log.warning(
                "Skipping immunization row for student %s due to error: %s. Row: %s",
                student_local_id,
                exc,
                raw_row,
            )

    log.info(
        "Inserted %s immunization rows into %s for %s of %s students (~75%% target)",
        inserted,
        TABLE_NAME,
        len(selected_students),
        total_students,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
