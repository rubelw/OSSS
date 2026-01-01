# `zulip-rabbitmq` service

This page documents the configuration for the `zulip-rabbitmq` service from `docker-compose.yml`.

**Image:** `rabbitmq:3.13-management-alpine`
**Container name:** `zulip-rabbitmq`

**Ports:**

- `15672:15672`
- `5672:5672`

**Volumes:**

- `./zulip/rabbitmq/data:/var/lib/rabbitmq`
- `./zulip/rabbitmq/logs:/var/log/rabbitmq`

**Networks:**

- `osss-net`

**Environment:**

- `RABBITMQ_DEFAULT_USER=zulip`
- `RABBITMQ_DEFAULT_PASS=zulip`
- `RABBITMQ_LOGS=/var/log/rabbitmq/rabbit.log`
- `RABBITMQ_SASL_LOGS=/var/log/rabbitmq/rabbit-sasl.log`
