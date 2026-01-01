# `taiga-gateway` service

This page documents the configuration for the `taiga-gateway` service from `docker-compose.yml`.

**Image:** `nginx:1.27-alpine`
**Container name:** `taiga-gateway`

**Ports:**

- `8120:80`

**Volumes:**

- `./docker/taiga/taiga-gateway.conf:/etc/nginx/conf.d/default.conf:ro`
- `taiga_static_data:/taiga/static`
- `taiga_media_data:/taiga/media`

**Depends on:**

- `taiga-front`
- `taiga-back`
- `taiga-events`

**Networks:**

- `osss-net`
