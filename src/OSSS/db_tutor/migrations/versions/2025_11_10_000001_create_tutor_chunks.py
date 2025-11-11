from alembic import op

# Revision identifiers, used by Alembic.
revision = "2025_11_10_000001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # pgvector extension (needs superuser or granted privileges)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # main table
    op.execute("""
    CREATE TABLE IF NOT EXISTS tutor_chunks (
      tutor_id    text NOT NULL,
      chunk_id    text PRIMARY KEY,
      source      text,
      page        int,
      text        text,
      embedding   vector(768)
    );
    """)

    # indexes
    op.execute("CREATE INDEX IF NOT EXISTS tutor_chunks_tutor_idx ON tutor_chunks (tutor_id);")
    op.execute("""
    CREATE INDEX IF NOT EXISTS tutor_chunks_embed_idx
      ON tutor_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
    """)

def downgrade():
    op.execute("DROP INDEX IF EXISTS tutor_chunks_embed_idx;")
    op.execute("DROP INDEX IF EXISTS tutor_chunks_tutor_idx;")
    op.execute("DROP TABLE IF EXISTS tutor_chunks;")
    # leave extension in place (safe), or uncomment to drop:
    # op.execute("DROP EXTENSION IF EXISTS vector;")
