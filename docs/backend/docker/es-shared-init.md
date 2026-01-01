# `es-shared-init` service

This page documents the configuration for the `es-shared-init` service from `docker-compose.yml`.

**Image:** `alpine:3.19`

**Volumes:**

- `es-shared:/shared:z`

**Depends on:**

- `shared-vol-init`

**Networks:**

- `osss-net`

**Command:**

```bash
sh -lc "mkdir -p /shared/filebeat-{data,logs} &&
        chown -R 501:501 /shared/filebeat-{data,logs} &&
        chmod -R 775 /shared/filebeat-{data,logs} &&
        ls -ld /shared/filebeat-*"

```
