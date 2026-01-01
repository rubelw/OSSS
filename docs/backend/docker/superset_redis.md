# `superset_redis` service

This page documents the configuration for the `superset_redis` service from `docker-compose.yml`.

**Image:** `redis:7-alpine`
**Container name:** `superset_redis`

**Ports:**

- `6381:6379`

**Volumes:**

- `superset_redis_data:/data:z`

**Networks:**

- `osss-net`

**Command:**

```bash
redis-server --appendonly yes
```
