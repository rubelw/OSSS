# `tutor-db` service

This page documents the configuration for the `tutor-db` service from `docker-compose.yml`.

**Image:** `pgvector/pgvector:pg16`
**Container name:** `tutor-db`

**Ports:**

- `5437:5432`

**Volumes:**

- `tutor_postgres_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=postgres`
- `POSTGRES_DB=postgres`
- `OSSS_DB_USER=osss`
- `OSSS_DB_PASSWORD=password`
- `OSSS_DB_NAME=osss`
- `POSTGRES_INITDB_ARGS=${POSTGRES_INITDB_ARGS}`
