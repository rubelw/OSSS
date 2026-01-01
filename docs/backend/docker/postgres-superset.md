# `postgres-superset` service

This page documents the configuration for the `postgres-superset` service from `docker-compose.yml`.

**Image:** `postgres:16`
**Container name:** `postgres-superset`

**Ports:**

- `5434:5432`

**Volumes:**

- `pg_superset_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_USER=osss`
- `POSTGRES_PASSWORD=osss`
- `POSTGRES_DB=superset`
