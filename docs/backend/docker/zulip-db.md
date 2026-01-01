# `zulip-db` service

This page documents the configuration for the `zulip-db` service from `docker-compose.yml`.

**Image:** `zulip/zulip-postgresql:14`
**Container name:** `zulip-db`

**Ports:**

- `5438:5432`

**Volumes:**

- `zulip_postgres_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_DB=zulip`
- `POSTGRES_USER=zulip`
- `POSTGRES_PASSWORD=zulip`
