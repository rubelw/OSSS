from alembic import op
import sqlalchemy as sa

revision = "2025_11_10_000001"
down_revision = None
branch_labels = ("tutor",)
depends_on = None

def upgrade():
    # enable pgvector only if available
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='vector') THEN
        CREATE EXTENSION IF NOT EXISTS vector;
      END IF;
    END$$;
    """)

    # create table once
    op.execute("""
    DO $$
    BEGIN
      IF to_regclass('public.tutor_chunks') IS NULL THEN
        CREATE TABLE public.tutor_chunks (
          id         VARCHAR(36) PRIMARY KEY,
          doc_id     VARCHAR(36) NOT NULL,
          text       TEXT NOT NULL,
          embedding  DOUBLE PRECISION[],
          created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
      END IF;
    END$$;
    """)

    # create indexes once
    op.execute("""
    DO $$
    BEGIN
      IF to_regclass('public.ix_tutor_chunks_doc_id') IS NULL THEN
        CREATE INDEX ix_tutor_chunks_doc_id ON public.tutor_chunks (doc_id);
      END IF;
      IF to_regclass('public.idx_tutor_chunks_embedding') IS NULL THEN
        CREATE INDEX idx_tutor_chunks_embedding ON public.tutor_chunks (id);
      END IF;
    END$$;
    """)

def downgrade():
    op.execute("""
    DO $$
    BEGIN
      IF to_regclass('public.ix_tutor_chunks_doc_id') IS NOT NULL THEN
        DROP INDEX public.ix_tutor_chunks_doc_id;
      END IF;
      IF to_regclass('public.idx_tutor_chunks_embedding') IS NOT NULL THEN
        DROP INDEX public.idx_tutor_chunks_embedding;
      END IF;
      IF to_regclass('public.tutor_chunks') IS NOT NULL THEN
        DROP TABLE public.tutor_chunks;
      END IF;
    END$$;
    """)
