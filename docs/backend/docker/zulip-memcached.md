# `zulip-memcached` service

This page documents the configuration for the `zulip-memcached` service from `docker-compose.yml`.

**Image:** `memcached:1.6-alpine`
**Container name:** `zulip-memcached`

**Networks:**

- `osss-net`

**Command:**

```bash
memcached -m 256
```
