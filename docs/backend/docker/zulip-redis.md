# `zulip-redis` service

This page documents the configuration for the `zulip-redis` service from `docker-compose.yml`.

**Image:** `redis:7-alpine`
**Container name:** `zulip-redis`

**Ports:**

- `6383:6379`

**Volumes:**

- `zulip_redis_data:/data:z`

**Networks:**

- `osss-net`

**Command:**

```bash
redis-server --requirepass super-secret-redis-pass --appendonly yes
```
