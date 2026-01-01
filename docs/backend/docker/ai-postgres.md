# `ai-postgres` service

This page documents the configuration for the `ai-postgres` service from `docker-compose.yml`.

**Image:** `postgres:15`
**Container name:** `ai-postgres`

**Ports:**

- `5436:5432`

**Volumes:**

- `ai_pg_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_DB=${AI_POSTGRES_DB}`
- `POSTGRES_USER=${AI_POSTGRES_USER}`
- `POSTGRES_PASSWORD=${AI_POSTGRES_PASSWORD}`
