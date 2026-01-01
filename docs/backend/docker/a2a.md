# `a2a` service

This page documents the configuration for the `a2a` service from `docker-compose.yml`.

**Build context:** `.`
**Dockerfile:** `docker/a2a/Dockerfile`
**Container name:** `a2a`

**Ports:**

- `8086:8086`

**Volumes:**

- `./src:/app/src:rw`
- `./MetaGPT_workspace:/logs:rw`

**Networks:**

- `osss-net`

**Environment:**

- `OSSS_ENV=dev`
- `A2A_SERVER_HOST=0.0.0.0`
- `A2A_SERVER_PORT=8086`
- `PYTHONPATH=/app/src`
- `OPENAI_API_BASE=http://ollama:11434/v1`
- `OPENAI_API_KEY=test-ollama`
- `A2A_MODEL_NAME=llama3.1`
- `WATCHFILES_FORCE_POLLING=true`
- `METAGPT_BASE_URL=http://metagpt:8001`

**Command:**

```bash
uvicorn a2a_server.main:app --host 0.0.0.0 --port 8086 --reload --reload-dir /app/src/a2a_server --reload-include '*.py' --log-level info

```
