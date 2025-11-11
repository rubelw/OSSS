[alembic-env] OFFLINE versions_path=/Users/rubelw/projects/OSSS/src/OSSS/db_tutor/migrations/versions
[alembic-env] OFFLINE url=postgresql+psycopg2://postgres:postgres@localhost:5437/postgres?sslmode=disable  version_table=alembic_version_tutor
BEGIN;

CREATE TABLE alembic_version_tutor (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_tutor_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 2025_11_10_000001

DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='vector') THEN
        CREATE EXTENSION IF NOT EXISTS vector;
      END IF;
    END$$;;

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
    END$$;;

DO $$
    BEGIN
      IF to_regclass('public.ix_tutor_chunks_doc_id') IS NULL THEN
        CREATE INDEX ix_tutor_chunks_doc_id ON public.tutor_chunks (doc_id);
      END IF;
      IF to_regclass('public.idx_tutor_chunks_embedding') IS NULL THEN
        CREATE INDEX idx_tutor_chunks_embedding ON public.tutor_chunks (id);
      END IF;
    END$$;;

INSERT INTO alembic_version_tutor (version_num) VALUES ('2025_11_10_000001') RETURNING alembic_version_tutor.version_num;

COMMIT;

