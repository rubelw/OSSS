# `taiga-front` service

This page documents the configuration for the `taiga-front` service from `docker-compose.yml`.

**Image:** `taigaio/taiga-front:latest`
**Container name:** `taiga-front`

**Depends on:**

- `taiga-back`
- `taiga-events`

**Networks:**

- `osss-net`

**Environment:**

- `TAIGA_URL=http://localhost:8120`
- `TAIGA_WEBSOCKETS_URL=ws://localhost:8120`
- `TAIGA_SUBPATH=`
