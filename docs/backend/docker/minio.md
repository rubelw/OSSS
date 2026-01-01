# `minio` service

This page documents the configuration for the `minio` service from `docker-compose.yml`.

**Image:** `minio/minio:latest`
**Container name:** `minio`

**Ports:**

- `9000:9000`
- `9001:9001`

**Volumes:**

- `minio_data:/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `MINIO_ROOT_USER=${AI_MINIO_ROOT_USER}`
- `MINIO_ROOT_PASSWORD=${AI_MINIO_ROOT_PASSWORD}`

**Command:**

```bash
server /data --console-address ":9001"
```
