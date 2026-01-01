# `taiga-events` service

This page documents the configuration for the `taiga-events` service from `docker-compose.yml`.

**Image:** `taigaio/taiga-events:latest`
**Container name:** `taiga-events`

**Ports:**

- `8188:8888`

**Depends on:**

- `taiga-rabbitmq`

**Networks:**

- `osss-net`

**Environment:**

- `RABBITMQ_USER=${TAIGA_RABBITMQ_USER:-taiga}`
- `RABBITMQ_PASSWORD=${TAIGA_RABBITMQ_PASS:-taiga}`
- `RABBITMQ_HOST=taiga-rabbitmq`
- `TAIGA_SECRET_KEY=${TAIGA_SECRET_KEY:-changeme-super-secret}`
