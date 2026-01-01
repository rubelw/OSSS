# `taiga-protected` service

This page documents the configuration for the `taiga-protected` service from `docker-compose.yml`.

**Image:** `taigaio/taiga-protected:latest`
**Container name:** `taiga-protected`

**Ports:**

- `8103:8003`

**Volumes:**

- `taiga_media_data:/taiga-protected/media`

**Depends on:**

- `taiga-back`

**Networks:**

- `osss-net`
