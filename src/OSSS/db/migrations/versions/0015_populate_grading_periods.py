from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple



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
revision = "0015_populate_grading_periods"
down_revision = "0014_populate_courses"
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


def _even_chunks(start: date, end: date, n: int) -> List[Tuple[date, date]]:
    """
    Split inclusive [start, end] date range into n contiguous chunks whose sizes
    differ by at most one day. Returns [(chunk_start, chunk_end), ...].
    """
    assert n >= 1
    total_days = (end - start).days + 1  # inclusive
    if total_days <= 0:
        # Defensive: if dates are invalid or equal in wrong order, just make one chunk
        return [(start, end)]

    base = total_days // n
    extra = total_days % n  # first 'extra' chunks get +1 day

    chunks: List[Tuple[date, date]] = []
    cursor = start
    for i in range(n):
        span = base + (1 if i < extra else 0)
        chunk_start = cursor
        chunk_end = cursor + timedelta(days=span - 1)
        chunks.append((chunk_start, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def _plan_for_term(term_type: str | None) -> Tuple[List[str], int]:
    """
    Decide period names and count for a term type.
    """
    t = (term_type or "").strip().lower()
    if t in ("", "year", "school_year", "yearlong"):
        return (["Q1", "Q2", "Q3", "Q4"], 4)
    if t in ("semester", "sem"):
        return (["Q1", "Q2"], 2)
    # For quarters, trimesters, or custom terms, create a single full-term period.
    return (["Term"], 1)


def upgrade() -> None:
    conn = op.get_bind()

    # Load all terms
    terms = conn.execute(
        sa.text(
            """
            SELECT id, name, type, start_date, end_date
            FROM academic_terms
            ORDER BY start_date
            """
        )
    ).mappings().all()

    # For each term, skip if grading periods already exist
    to_insert: list[dict] = []

    for term in terms:
        term_id = term["id"]
        tname = term["name"]
        ttype = term["type"]
        start = term["start_date"]
        end = term["end_date"]

        if start is None or end is None:
            # Skip malformed terms
            continue

        existing = conn.execute(
            sa.text(
                "SELECT 1 FROM grading_periods WHERE term_id = :term_id LIMIT 1"
            ),
            {"term_id": term_id},
        ).scalar()
        if existing:
            continue  # already populated

        names, n = _plan_for_term(ttype)
        chunks = _even_chunks(start, end, n)

        # If the number of names doesn't match n (shouldn't happen), normalize.
        if len(names) != n:
            if n == 1:
                names = ["Term"]
            elif n == 2:
                names = ["Q1", "Q2"]
            elif n == 3:
                names = ["T1", "T2", "T3"]
            else:
                names = [f"Q{i+1}" for i in range(n)]

        for label, (p_start, p_end) in zip(names, chunks):
            to_insert.append(
                {
                    "term_id": term_id,
                    "name": label,
                    "start_date": p_start,
                    "end_date": p_end,
                }
            )

    if to_insert:
        grading_periods = sa.table(
            "grading_periods",
            sa.column("term_id", sa.String),
            sa.column("name", sa.Text),
            sa.column("start_date", sa.Date),
            sa.column("end_date", sa.Date),
        )
        op.bulk_insert(grading_periods, to_insert)


def downgrade() -> None:
    # Best-effort rollback: remove only grading periods we likely created.
    # (This avoids dropping any custom periods with other names.)
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            DELETE FROM grading_periods
            WHERE name IN ('Q1','Q2','Q3','Q4','Term')
            """
        )
    )