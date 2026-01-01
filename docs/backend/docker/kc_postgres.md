# `kc_postgres` service

This page documents the configuration for the `kc_postgres` service from `docker-compose.yml`.

**Image:** `postgres:16`
**Container name:** `kc_postgres`

**Volumes:**

- `kc_postgres_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_DB=${KC_DB_NAME}`
- `POSTGRES_USER=${KC_DB_USERNAME}`
- `POSTGRES_PASSWORD=${KC_DB_PASSWORD}`
