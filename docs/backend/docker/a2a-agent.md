# `a2a-agent` service

This page documents the configuration for the `a2a-agent` service from `docker-compose.yml`.

**Build context:** `.`
**Dockerfile:** `docker/a2a-agent/Dockerfile`
**Container name:** `a2a-agent`

**Volumes:**

- `./src:/app/src:rw`
- `./MetaGPT_workspace:/logs:rw`

**Depends on:**

- `metagpt`

**Networks:**

- `osss-net`

**Environment:**

- `PYTHONPATH=/app/src`
- `METAGPT_BASE_URL=http://metagpt:8001`

**Command:**

```bash
python -m a2a_server.a2a_agent

```
