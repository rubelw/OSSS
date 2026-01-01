# `dvc` service

This page documents the configuration for the `dvc` service from `docker-compose.yml`.

**Image:** `python:3.11-slim`
**Container name:** `dvc`

**Volumes:**

- `./:/workspace`
- `dvc-cache:/workspace/.dvc/cache`
- `dvc-cache:/root/.cache/dvc`

**Networks:**

- `osss-net`

**Environment:**

- `AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-minioadmin}`
- `AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-minioadmin}`
- `AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}`
- `HEALTH_PORT=8010`
