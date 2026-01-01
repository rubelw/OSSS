# `taiga-db` service

This page documents the configuration for the `taiga-db` service from `docker-compose.yml`.

**Image:** `postgres:16`
**Container name:** `taiga-db`

**Ports:**

- `5439:5432`

**Volumes:**

- `taiga_db_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_DB=taiga`
- `POSTGRES_USER=${TAIGA_DB_USER:-taiga}`
- `POSTGRES_PASSWORD=${TAIGA_DB_PASSWORD:-taiga}`
