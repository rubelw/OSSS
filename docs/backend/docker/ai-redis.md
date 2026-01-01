# `ai-redis` service

This page documents the configuration for the `ai-redis` service from `docker-compose.yml`.

**Image:** `redis:7`
**Container name:** `ai-redis`

**Ports:**

- `6382:6379`

**Volumes:**

- `ai_redis_data:/data:z`

**Networks:**

- `osss-net`

**Command:**

```bash
redis-server --save  --appendonly no
```
