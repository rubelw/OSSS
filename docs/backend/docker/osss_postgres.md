# `osss_postgres` service

This page documents the configuration for the `osss_postgres` service from `docker-compose.yml`.

**Build context:** `.`
**Dockerfile:** `docker/postgres/Dockerfile`
**Container name:** `osss_postgres`

**Ports:**

- `5433:5432`

**Volumes:**

- `osss_postgres_data:/var/lib/postgresql/data:z`
- `./scripts/init-osss.sh:/docker-entrypoint-initdb.d/20-init-osss.sh:ro,z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_USER=${POSTGRES_USER}`
- `POSTGRES_PASSWORD=${POSTGRES_PASSWORD}`
- `POSTGRES_DB=${POSTGRES_DB}`
- `OSSS_DB_USER=${OSSS_DB_USER}`
- `OSSS_DB_PASSWORD=${OSSS_DB_PASSWORD}`
- `OSSS_DB_NAME=${OSSS_DB_NAME}`
- `POSTGRES_INITDB_ARGS=${POSTGRES_INITDB_ARGS}`
- `A2A_SERVER_URL=http://a2a:8086`
