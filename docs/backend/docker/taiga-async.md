# `taiga-async` service

This page documents the configuration for the `taiga-async` service from `docker-compose.yml`.

**Image:** `taigaio/taiga-back:latest`
**Container name:** `taiga-async`

**Volumes:**

- `taiga_static_data:/taiga-back/static`
- `taiga_media_data:/taiga-back/media`

**Depends on:**

- `taiga-db`
- `taiga-rabbitmq`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_HOST=taiga-db`
- `POSTGRES_DB=taiga`
- `POSTGRES_USER=${TAIGA_DB_USER:-taiga}`
- `POSTGRES_PASSWORD=${TAIGA_DB_PASSWORD:-taiga}`
- `RABBITMQ_HOST=taiga-rabbitmq`
- `RABBITMQ_USER=${TAIGA_RABBITMQ_USER:-taiga}`
- `RABBITMQ_PASSWORD=${TAIGA_RABBITMQ_PASS:-taiga}`

**Command:**

```bash
/taiga-back/docker/async_entrypoint.sh
```
