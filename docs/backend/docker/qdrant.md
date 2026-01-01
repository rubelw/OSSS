# `qdrant` service

This page documents the configuration for the `qdrant` service from `docker-compose.yml`.

**Build context:** `.`
**Dockerfile:** `docker/qdrant/Dockerfile`
**Container name:** `qdrant`

**Ports:**

- `6333:6333`

**Volumes:**

- `qdrant_data:/qdrant/storage:z`

**Networks:**

- `osss-net`
