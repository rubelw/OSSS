# `app` service

This page documents the configuration for the `app` service from `docker-compose.yml`.

**Build context:** `.`
**Dockerfile:** `docker/app/Dockerfile`
**Container name:** `app`

**Ports:**

- `127.0.0.1:8081:8000`

**Volumes:**

- `./:/workspace:cached`
- `./docker/logging.yml:/workspace/docker/logging.yaml:ro,z`
- `./scripts/app-entrypoint.sh:/usr/local/bin/app-entrypoint.sh:ro,z`
- `langgraph_data:/workspace/langgraph_data:z`

**Depends on:**

- `redis`
- `osss_postgres`
- `tutor-db`

**Networks:**

- `osss-net`

**Environment:**

- `OSSS_VERBOSE_AUTH=1`
- `PYTHONUNBUFFERED=1`
- `PYTHONLOGLEVEL=DEBUG`
- `LOG_LEVEL=DEBUG`
- `UVICORN_LOG_LEVEL=debug`
- `UVICORN_ACCESS_LOG=1`
- `KEYCLOAK_ISSUER=${KEYCLOAK_ISSUER}`
- `KEYCLOAK_JWKS_URL=${KEYCLOAK_JWKS_URL}`
- `OSSS_DISABLE_AUTH=${OSSS_DISABLE_AUTH}`
- `AUTHLIB_DEBUG=1`
- `OAUTHLIB_INSECURE_TRANSPORT=1`
- `HTTPX_LOG_LEVEL=DEBUG`
- `REQUESTS_LOG_LEVEL=DEBUG`
- `JOSE_LOG_LEVEL=DEBUG`
- `JWcrypto_LOG_LEVEL=DEBUG`
- `HOST=0.0.0.0`
- `PORT=8000`
- `PYTHONPATH=/workspace/src`
- `WATCHFILES_FORCE_POLLING=true`
- `CORS_ALLOW_ORIGINS=${CORS_ALLOW_ORIGINS}`
- `CORS_ORIGINS=${CORS_ORIGINS}`
- `REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt`
- `SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt`
- `CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt`
- `OIDC_DISCOVERY_URL_INTERNAL=${OIDC_DISCOVERY_URL_INTERNAL}`
- `OIDC_TOKEN_URL_INTERNAL=${OIDC_TOKEN_URL_INTERNAL}`
- `KEYCLOAK_INTERNAL_BASE=${KEYCLOAK_INTERNAL_BASE}`
- `OIDC_ISSUER=${OIDC_ISSUER}`
- `OIDC_CLIENT_ID=osss-api`
- `OIDC_CLIENT_SECRET=${OIDC_CLIENT_SECRET:-password}`
- `OSSS_PUBLIC_BASE_URL=http://localhost:8081`
- `OIDC_REDIRECT_URL=http://localhost:8081/callback`
- `OIDC_LOGOUT_REDIRECT_URL=http://localhost:8081/`
- `OIDC_VERIFY_AUD=0`
- `ALLOWED_CLOCK_SKEW=60`
- `REDIS_URL=redis://redis:6379/0`
- `SESSION_REDIS_HOST=redis`
- `SESSION_REDIS_PORT=6379`
- `KEYCLOAK_CLIENT_ID=osss-api`
- `KEYCLOAK_CLIENT_SECRET=password`
- `ASYNC_DATABASE_URL=postgresql+asyncpg://${OSSS_DB_USER}:${OSSS_DB_PASSWORD}@osss_postgres:5432/${OSSS_DB_NAME}`
- `ALEMBIC_DATABASE_URL=postgresql+asyncpg://${OSSS_DB_USER}:${OSSS_DB_PASSWORD}@osss_postgres:5432/${OSSS_DB_NAME}`
- `OIDC_JWKS_URL_INTERNAL=${OIDC_JWKS_URL_INTERNAL}`
- `OIDC_VERIFY_ISS=${OIDC_VERIFY_ISS}`
- `MIGRATIONS_DIR=/app/src/OSSS/db/migrations`
- `REPO_ROOT=/app`
- `ALEMBIC_CMD=alembic`
- `ALEMBIC_INI=/app/alembic.ini`
- `OSSS_DB_PASSWORD=${OSSS_DB_PASSWORD}`
- `OSSS_DB_NAME=${OSSS_DB_NAME}`
- `OSSS_DB_USER=${OSSS_DB_USER}`
- `POSTGRES_USER=${POSTGRES_USER}`
- `POSTGRES_PASSWORD=${POSTGRES_PASSWORD}`
- `POSTGRES_DB=${POSTGRES_DB}`
- `DATABASE_URL=${ASYNC_DATABASE_URL}`
- `TUTOR_CONFIG_DIR=/app/config/tutors`
- `OLLAMA_BASE=http://host.containers.internal:11434`
- `OSSS_TUTOR_DB_USER=${OSSS_TUTOR_DB_USER}`
- `OSSS_TUTOR_DB_PASSWORD=${OSSS_TUTOR_DB_PASSWORD}`
- `OSSS_TUTOR_DB_NAME=${OSSS_TUTOR_DB_NAME}`
- `OSSS_TUTOR_DB_HOST=tutor-db`
- `OSSS_TUTOR_DB_PORT=5432`
- `OSSS_TUTOR_CONFIG_DIR=${OSSS_TUTOR_CONFIG_DIR}`
- `SAFE_OPENAI_API_BASE=${SAFE_OPENAI_API_BASE}`
- `OPENAI_API_BASE=${OPENAI_API_BASE}`
- `OPENAI_API_KEY=${OPENAI_API_KEY}`
- `OSSS_ADDITIONAL_INDEX_PATH=/workspace/vector_indexes/main/embeddings.jsonl`
- `TUTOR_INDEX_PATH=/workspace/vector_indexes/tutor/embeddings.jsonl`
- `AGENT_INDEX_PATH=/workspace/vector_indexes/agent/embeddings.jsonl`
- `METAGPT_URL=http://metagpt:8001`
- `SEED_JSON_PATH=/mnt/data/seed_full_school.json`
- `OSSS_LANGCHAIN_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://localhost:11434/v1`
- `OSSS_LANGCHAIN_MODEL=llama3.1:latest`
- `SKIP_GL_SEGMENTS=false`
- `OPENBLAS_NUM_THREADS=1`
- `OMP_NUM_THREADS=1`
- `MKL_NUM_THREADS=1`
- `NUMEXPR_NUM_THREADS=1`
- `LLM_PROVIDER=ollama`
- `OLLAMA_MODEL=llama3.1`
- `OLLAMA_TEMPERATURE=0.2`
- `OLLAMA_NUM_CTX=8192`
- `OSSS_SYNTHESIS_LLM_PROVIDER=ollama`
- `OSSS_SYNTHESIS_MODEL=llama3.1:latest`
- `OSSS_OLLAMA_BASE_URL=http://host.containers.internal:11434`
- `OSSS_AI_DB_PERSIST_ENABLED=true`
- `AGENT_LLM_BASE_URL=http://host:containers:internal:11434/v1`
- `OSSS_AI_GATEWAY_BASE_URL=http://host.containers.internal:11434`

**Command:**

```bash
uvicorn src.OSSS.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /workspace/src/OSSS --log-level info --access-log --log-config /workspace/docker/logging.yaml
```

**Labels:**

- `co.elastic.logs/enabled = true`
- `co.elastic.logs/processors.1.decode_json_fields.fields = message`
- `co.elastic.logs/processors.1.decode_json_fields.target = `
- `co.elastic.logs/processors.1.decode_json_fields.overwrite_keys = true`
- `co.elastic.logs/processors.2.add_fields.target = app`
- `co.elastic.logs/processors.2.add_fields.fields.service = osss-api`
- `co.elastic.logs/json.keys_under_root = true`
- `co.elastic.logs/json.add_error_key = true`
- `co.elastic.logs/json.overwrite_keys = true`
