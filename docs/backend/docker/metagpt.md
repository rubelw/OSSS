# `metagpt` service

This page documents the configuration for the `metagpt` service from `docker-compose.yml`.

**Build context:** `.`
**Dockerfile:** `docker/metagpt/Dockerfile`
**Container name:** `metagpt`

**Ports:**

- `8001:8001`

**Volumes:**

- `./src/MetaGPT:/work/src/MetaGPT:cached`
- `./MetaGPT_workspace:/work/logs:rw`
- `./vector_indexes:/vector_indexes`

**Networks:**

- `osss-net`

**Environment:**

- `PYTHONUNBUFFERED=1`
- `WATCHFILES_FORCE_POLLING=true`
- `OLLAMA_BASE_URL=http://host.containers.internal:11434`
- `OLLAMA_MODEL=llama3.1:latest`
- `RAG_INDEX_PATH=/workspace/vector_indexes/main/embeddings.jsonl`

**Command:**

```bash
uvicorn MetaGPT.metagpt_server:app --host 0.0.0.0 --port 8001 --reload --reload-dir /work/src/MetaGPT
```
