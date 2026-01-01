# `taiga-rabbitmq` service

This page documents the configuration for the `taiga-rabbitmq` service from `docker-compose.yml`.

**Image:** `rabbitmq:3.13-management`
**Container name:** `taiga-rabbitmq`

**Ports:**

- `8161:15672`
- `8162:5672`

**Volumes:**

- `taiga_rabbitmq_data:/var/lib/rabbitmq:z`

**Networks:**

- `osss-net`

**Environment:**

- `RABBITMQ_DEFAULT_USER=${TAIGA_RABBITMQ_USER:-taiga}`
- `RABBITMQ_DEFAULT_PASS=${TAIGA_RABBITMQ_PASS:-taiga}`
- `RABBITMQ_DEFAULT_VHOST=${TAIGA_RABBITMQ_VHOST:-taiga}`
- `RABBITMQ_ERLANG_COOKIE=${TAIGA_RABBITMQ_ERLANG_COOKIE:-changeme-cookie}`
