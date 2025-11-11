from alembic import op
from sqlalchemy import text
import sys

# revision identifiers
revision = "2025_11_10_000001"
down_revision = None            # separate branch; not linked to core
branch_labels = ("tutor",)
depends_on = None

def _should_run() -> bool:
    # correct API: read tag passed from env.py's context.configure(tag="tutor")
    try:
        tag = op.get_context().get_tag_argument()
    except Exception:
        tag = None
    print(f"[tutor rev {revision}] tag={tag!r}", file=sys.stderr)
    # Allow either explicit "tutor" or None (when running ad-hoc tests)
    return tag in (None, "tutor")

def upgrade():
    if not _should_run():
        print(f"[tutor rev {revision}] SKIPPED due to tag mismatch", file=sys.stderr)
        return

    print(f"[tutor rev {revision}] RUNNING upgrade()", file=sys.stderr)

    # ensure pgvector (your 5437 container already has it)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    # gen_random_uuid() needs pgcrypto in some images; enable defensively
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS tutor_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            doc_id TEXT NOT NULL,
            chunk_idx INTEGER NOT NULL,
            embedding vector(1536),
            content TEXT,
            created_at TIMESTAMPTZ DEFAULT now() NOT NULL
        )
    """)

def downgrade():
    if not _should_run():
        return
    op.execute("DROP TABLE IF EXISTS tutor_chunks")
