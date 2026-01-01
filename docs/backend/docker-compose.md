# Backend Docker Compose Services

This page documents the services defined in `docker-compose.yml`.

Each service also has its own page under `backend/docker/` with more detailed configuration.

## Services overview

| Service | Image | Description |
|---------|-------|-------------|
| [`consul`](docker/consul.md) | `hashicorp/consul:1.18` | consul |
| [`consul-jwt-init`](docker/consul-jwt-init.md) | `hashicorp/consul:1.18` | consul-jwt-init |
| [`app`](docker/app.md) | `` | app |
| [`tutor-db`](docker/tutor-db.md) | `pgvector/pgvector:pg16` | tutor-db |
| [`web`](docker/web.md) | `` | web |
| [`osss_postgres`](docker/osss_postgres.md) | `` | osss_postgres |
| [`redis`](docker/redis.md) | `redis:7-alpine` | redis |
| [`kc_postgres`](docker/kc_postgres.md) | `postgres:16` | kc_postgres |
| [`keycloak`](docker/keycloak.md) | `` | keycloak |
| [`vault`](docker/vault.md) | `hashicorp/vault:1.20.3` | vault |
| [`vault-oidc-setup`](docker/vault-oidc-setup.md) | `` | vault-oidc-setup |
| [`vault-seed`](docker/vault-seed.md) | `alpine:3.20` | vault-seed |
| [`shared-vol-init`](docker/shared-vol-init.md) | `alpine:3.20` | shared-vol-init |
| [`es-shared-init`](docker/es-shared-init.md) | `alpine:3.19` | es-shared-init |
| [`elasticsearch`](docker/elasticsearch.md) | `docker.elastic.co/elasticsearch/elasticsearch:8.14.3` | elasticsearch |
| [`kibana-pass-init`](docker/kibana-pass-init.md) | `curlimages/curl:8.8.0` | kibana-pass-init |
| [`kibana`](docker/kibana.md) | `docker.elastic.co/kibana/kibana:8.14.3` | kibana |
| [`api-key-init`](docker/api-key-init.md) | `curlimages/curl:8.8.0` | api-key-init |
| [`filebeat-setup`](docker/filebeat-setup.md) | `docker.elastic.co/beats/filebeat:8.14.3` | filebeat-setup |
| [`filebeat`](docker/filebeat.md) | `docker.elastic.co/beats/filebeat:8.14.3` | filebeat |
| [`trino`](docker/trino.md) | `trinodb/trino:latest` | trino |
| [`superset-build`](docker/superset-build.md) | `osss/superset:with-drivers` | superset-build |
| [`superset_redis`](docker/superset_redis.md) | `redis:7-alpine` | superset_redis |
| [`postgres-superset`](docker/postgres-superset.md) | `postgres:16` | postgres-superset |
| [`superset-init`](docker/superset-init.md) | `osss/superset:with-drivers` | superset-init |
| [`superset`](docker/superset.md) | `osss/superset:with-drivers` | superset |
| [`postgres-airflow`](docker/postgres-airflow.md) | `postgres:16` | postgres-airflow |
| [`airflow-init`](docker/airflow-init.md) | `apache/airflow:2.9.3-python3.11` | airflow-init |
| [`airflow-webserver`](docker/airflow-webserver.md) | `apache/airflow:2.9.3-python3.11` | airflow-webserver |
| [`airflow-scheduler`](docker/airflow-scheduler.md) | `apache/airflow:2.9.3-python3.11` | airflow-scheduler |
| [`airflow-redis`](docker/airflow-redis.md) | `redis:7-alpine` | airflow-redis |
| [`execute-migrate-all`](docker/execute-migrate-all.md) | `docker.getcollate.io/openmetadata/server:1.9.12` | execute_migrate_all |
| [`openmetadata-server`](docker/openmetadata-server.md) | `docker.getcollate.io/openmetadata/server:1.9.12` | openmetadata-server |
| [`mysql`](docker/mysql.md) | `docker.getcollate.io/openmetadata/db:1.9.12` | mysql |
| [`om-elasticsearch`](docker/om-elasticsearch.md) | `docker.elastic.co/elasticsearch/elasticsearch:8.11.4` | om-elasticsearch |
| [`ingestion`](docker/ingestion.md) | `docker.getcollate.io/openmetadata/ingestion:1.9.12` | openmetadata-ingestion |
| [`qdrant`](docker/qdrant.md) | `` | qdrant |
| [`minio`](docker/minio.md) | `minio/minio:latest` | minio |
| [`ai-redis`](docker/ai-redis.md) | `redis:7` | ai-redis |
| [`ai-postgres`](docker/ai-postgres.md) | `postgres:15` | ai-postgres |
| [`dvc`](docker/dvc.md) | `python:3.11-slim` | dvc |
| [`rasa-mentor`](docker/rasa-mentor.md) | `rasa/rasa:3.6.20` | rasa-mentor |
| [`a2a`](docker/a2a.md) | `` | a2a |
| [`metagpt`](docker/metagpt.md) | `` | metagpt |
| [`a2a-agent`](docker/a2a-agent.md) | `` | a2a-agent |
| [`zulip`](docker/zulip.md) | `` | zulip |
| [`zulip-db`](docker/zulip-db.md) | `zulip/zulip-postgresql:14` | zulip-db |
| [`zulip-memcached`](docker/zulip-memcached.md) | `memcached:1.6-alpine` | zulip-memcached |
| [`zulip-redis`](docker/zulip-redis.md) | `redis:7-alpine` | zulip-redis |
| [`zulip-rabbitmq`](docker/zulip-rabbitmq.md) | `rabbitmq:3.13-management-alpine` | zulip-rabbitmq |
| [`taiga-db`](docker/taiga-db.md) | `postgres:16` | taiga-db |
| [`taiga-rabbitmq`](docker/taiga-rabbitmq.md) | `rabbitmq:3.13-management` | taiga-rabbitmq |
| [`taiga-back`](docker/taiga-back.md) | `taigaio/taiga-back:latest` | taiga-back |
| [`taiga-async`](docker/taiga-async.md) | `taigaio/taiga-back:latest` | taiga-async |
| [`taiga-events`](docker/taiga-events.md) | `taigaio/taiga-events:latest` | taiga-events |
| [`taiga-protected`](docker/taiga-protected.md) | `taigaio/taiga-protected:latest` | taiga-protected |
| [`taiga-front`](docker/taiga-front.md) | `taigaio/taiga-front:latest` | taiga-front |
| [`taiga-gateway`](docker/taiga-gateway.md) | `nginx:1.27-alpine` | taiga-gateway |
| [`taiga-init-admin`](docker/taiga-init-admin.md) | `taigaio/taiga-back:latest` | taiga-init-admin |

## Service details

### `consul`

**Image:** `hashicorp/consul:1.18`
**Container name:** `consul`

**Ports:**

- `8500:8500`
- `8600:8600/tcp`
- `8600:8600/udp`

**Volumes:**

- `./config_files/consul_data:/consul/data:z`
- `./config_files/consul/config:/consul/config:rw,z`
- `./config_files/consul/jwt:/consul/jwt:rw,z`
- `./config_files/keycloak/secrets/ca/ca.crt:/usr/local/share/ca-certificates/keycloak-ca.crt:ro`

**Networks:**

- `osss-net`

**Environment:**

- `CONSUL_HTTP_TOKEN=${CONSUL_HTTP_TOKEN:-}`

**Command:**

```bash
/bin/sh -lc update-ca-certificates || true; exec consul agent -server -bootstrap-expect=1 -client=0.0.0.0 -ui -log-level=INFO -config-dir=/consul/config
```


### `consul-jwt-init`

**Image:** `hashicorp/consul:1.18`
**Container name:** `consul-jwt-init`

**Volumes:**

- `./config_files/consul/jwt/jwt.json:/cfg/jwt.json:ro,z`
- `./config_files/consul/init-jwt.sh:/cfg/init-jwt.sh:ro,z`

**Depends on:**

- `consul`

**Networks:**

- `osss-net`

**Environment:**

- `CONSUL_HTTP_ADDR=http://consul:8500`
- `CONSUL_HTTP_TOKEN=${CONSUL_HTTP_TOKEN}`

**Command:**

```bash
/cfg/init-jwt.sh
```


### `app`

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
- `AGENT_LLM_BASE_URL=http://host.containers.internal:11434/v1`
- `OSSS_AI_GATEWAY_BASE_URL=http://host.containers.internal:11434`

**Command:**

```bash
uvicorn src.OSSS.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /workspace/src/OSSS --log-level info --access-log --log-config /workspace/docker/logging.yaml
```

... (truncated for brevity in this code cell; in real use you'd paste the full document)
