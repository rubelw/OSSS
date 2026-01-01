# `shared-vol-init` service

This page documents the configuration for the `shared-vol-init` service from `docker-compose.yml`.

**Image:** `alpine:3.20`
**Container name:** `shared-vol-init`

**Volumes:**

- `es-shared:/shared:z`

**Networks:**

- `osss-net`

**Command:**

```bash
set -e
mkdir -p /shared
chmod 0777 /shared         # or 0770 with a shared group if you prefer

```
