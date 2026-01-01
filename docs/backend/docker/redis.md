# `redis` service

This page documents the configuration for the `redis` service from `docker-compose.yml`.

**Image:** `redis:7-alpine`
**Container name:** `redis`

**Ports:**

- `6379:6379`

**Volumes:**

- `redis-data:/data:z`

**Networks:**

- `osss-net`

**Command:**

```bash
redis-server --appendonly yes
```
