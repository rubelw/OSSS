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
| [`es-shared-init`](docker/es-shared-init.md) | `alpine:3.19` |  |
| [`elasticsearch`](docker/elasticsearch.md) | `docker.elastic.co/elasticsearch/elasticsearch:8.14.3` | elasticsearch |
| [`kibana-pass-init`](docker/kibana-pass-init.md) | `curlimages/curl:8.8.0` | kibana-pass-init |
| [`kibana`](docker/kibana.md) | `docker.elastic.co/kibana/kibana:8.14.3` | kibana |
| [`api-key-init`](docker/api-key-init.md) | `curlimages/curl:8.8.0` | api-key-init |
| [`filebeat-setup`](docker/filebeat-setup.md) | `docker.elastic.co/beats/filebeat:8.14.3` | filebeat-setup |
| [`filebeat`](docker/filebeat.md) | `docker.elastic.co/beats/filebeat:8.14.3` | filebeat |
| [`trino`](docker/trino.md) | `trinodb/trino:latest` | trino |
| [`superset-build`](docker/superset-build.md) | `osss/superset:with-drivers` |  |
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


### `tutor-db`

**Image:** `pgvector/pgvector:pg16`
**Container name:** `tutor-db`

**Ports:**

- `5437:5432`

**Volumes:**

- `tutor_postgres_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=postgres`
- `POSTGRES_DB=postgres`
- `OSSS_DB_USER=osss`
- `OSSS_DB_PASSWORD=password`
- `OSSS_DB_NAME=osss`
- `POSTGRES_INITDB_ARGS=${POSTGRES_INITDB_ARGS}`


### `web`

**Build context:** `./src/osss-web`
**Dockerfile:** `../../docker/osss-web/Dockerfile`
**Container name:** `web`

**Ports:**

- `3000:3000`

**Volumes:**

- `./src/osss-web:/app:cached`
- `web_node_modules:/app/node_modules:z`
- `./config_files/keycloak/secrets/ca/ca.crt:/app/certs/keycloak-ca.crt:ro,z`

**Networks:**

- `osss-net`

**Environment:**

- `REDIS_URL=redis://redis:6379/0`
- `NODE_EXTRA_CA_CERTS=/app/certs/keycloak-ca.crt`
- `NODE_ENV=development`
- `CHOKIDAR_USEPOLLING=true`
- `WATCHPACK_POLLING=true`
- `OSSS_API_URL=${OSSS_API_URL}`
- `NEXT_PUBLIC_A2A_SERVER_URL=http://localhost:8086`

**Labels:**

- `co.elastic.logs/enabled = true`
- `co.elastic.logs/processors.1.decode_json_fields.fields = message`
- `co.elastic.logs/processors.1.decode_json_fields.target = `
- `co.elastic.logs/processors.1.decode_json_fields.overwrite_keys = true`
- `co.elastic.logs/processors.2.add_fields.target = app`
- `co.elastic.logs/processors.2.add_fields.fields.service = osss-web`


### `osss_postgres`

**Build context:** `.`
**Dockerfile:** `docker/postgres/Dockerfile`
**Container name:** `osss_postgres`

**Ports:**

- `5433:5432`

**Volumes:**

- `osss_postgres_data:/var/lib/postgresql/data:z`
- `./scripts/init-osss.sh:/docker-entrypoint-initdb.d/20-init-osss.sh:ro,z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_USER=${POSTGRES_USER}`
- `POSTGRES_PASSWORD=${POSTGRES_PASSWORD}`
- `POSTGRES_DB=${POSTGRES_DB}`
- `OSSS_DB_USER=${OSSS_DB_USER}`
- `OSSS_DB_PASSWORD=${OSSS_DB_PASSWORD}`
- `OSSS_DB_NAME=${OSSS_DB_NAME}`
- `POSTGRES_INITDB_ARGS=${POSTGRES_INITDB_ARGS}`
- `A2A_SERVER_URL=http://a2a:8086`


### `redis`

**Image:** `redis:7-alpine`
**Container name:** `redis`

**Ports:**

- `6379:6379`

**Volumes:**

- `redis-data:/data:z`

**Networks:**

- `osss-net`

**Command:**

```bash
redis-server --appendonly yes
```


### `kc_postgres`

**Image:** `postgres:16`
**Container name:** `kc_postgres`

**Volumes:**

- `kc_postgres_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_DB=${KC_DB_NAME}`
- `POSTGRES_USER=${KC_DB_USERNAME}`
- `POSTGRES_PASSWORD=${KC_DB_PASSWORD}`


### `keycloak`

**Build context:** `.`
**Dockerfile:** `docker/keycloak/Dockerfile`
**Container name:** `keycloak`

**Ports:**

- `8443:8443`

**Volumes:**

- `./realm-export.json:/opt/keycloak/data/import/10-OSSS.json:ro,z`
- `./docker/keycloak/quarkus.properties:/opt/keycloak/conf/quarkus.properties:ro,z`
- `./config_files/keycloak/secrets/keycloak:/opt/keycloak/conf/tls:ro,z`

**Depends on:**

- `kc_postgres`

**Networks:**

- `osss-net`

**Environment:**

- `KC_HTTP_MANAGEMENT_PORT=9000`
- `KC_HTTP_MANAGEMENT_SCHEME=http`
- `KC_HTTP_PORT=8080`
- `KC_DB=${KC_DB}`
- `KC_DB_URL=jdbc:postgresql://${KC_DB_HOST}:${KC_DB_PORT}/${KC_DB_NAME}`
- `KC_DB_USERNAME=${KC_DB_USERNAME}`
- `KC_DB_PASSWORD=${KC_DB_PASSWORD}`
- `KEYCLOAK_ADMIN=${KEYCLOAK_ADMIN}`
- `KEYCLOAK_ADMIN_PASSWORD=${KEYCLOAK_ADMIN_PASSWORD}`
- `KC_HTTPS_CERTIFICATE_FILE=/opt/keycloak/conf/tls/server.crt`
- `KC_HTTPS_CERTIFICATE_KEY_FILE=/opt/keycloak/conf/tls/server.key`
- `KC_HEALTH_ENABLED=true`
- `KC_HOSTNAME=${KC_HOSTNAME}`
- `KC_DB_SCHEMA=${KC_DB_SCHEMA}`
- `QUARKUS_HIBERNATE_ORM_PERSISTENCE_XML_IGNORE=true`
- `JAVA_OPTS=${JAVA_OPTS}`
- `KC_DB_POOL_INITIAL_SIZE=20`
- `KC_DB_POOL_MIN_SIZE=20`
- `KC_DB_POOL_MAX_SIZE=50`
- `KC_LOG_LEVEL=${KC_LOG_LEVEL}`
- `KC_PROXY=${KC_PROXY}`
- `KC_HTTP_ENABLED=${KC_HTTP_ENABLED}`
- `KC_HOSTNAME_STRICT=${KC_HOSTNAME_STRICT}`
- `ADMIN_USER=${KEYCLOAK_ADMIN}`
- `ADMIN_PWD=${KEYCLOAK_ADMIN_PASSWORD}`
- `KC_URL=${KC_URL}`
- `QUARKUS_MANAGEMENT_HOST=0.0.0.0`
- `QUARKUS_MANAGEMENT_ENABLED=true`
- `QUARKUS_MANAGEMENT_PORT=9000`
- `QUARKUS_HTTP_HOST=0.0.0.0`


### `vault`

**Image:** `hashicorp/vault:1.20.3`
**Container name:** `vault`

**Ports:**

- `8200:8200`

**Networks:**

- `osss-net`

**Environment:**

- `VAULT_DEV_ROOT_TOKEN_ID=${VAULT_DEV_ROOT_TOKEN_ID}`
- `VAULT_DEV_LISTEN_ADDRESS=${VAULT_DEV_LISTEN_ADDRESS}`
- `VAULT_UI=${VAULT_UI}`
- `VAULT_API_ADDR=${VAULT_API_ADDR}`

**Command:**

```bash
server -dev -dev-root-token-id=root -dev-listen-address=0.0.0.0:8200
```


### `vault-oidc-setup`

**Build context:** `.`
**Dockerfile:** `docker/vault-oidc-setup/Dockerfile`
**Container name:** `vault-oidc-setup`

**Volumes:**

- `./scripts/vault-oidc-setup.sh:/setup.sh:ro,z`
- `~/.vault-token:/root/.vault-token:ro,z`
- `./config_files/keycloak/secrets/ca/ca.crt:/etc/ssl/certs/keycloak-ca.crt:ro,z`

**Depends on:**

- `vault`

**Networks:**

- `osss-net`

**Environment:**

- `VERBOSE=1`
- `DEBUG=1`
- `VAULT_LOG_LEVEL=debug`
- `GODEBUG=http2debug=2`
- `VAULT_ADDR=${VAULT_ADDR}`
- `VAULT_TOKEN=${VAULT_TOKEN}`
- `OIDC_DISCOVERY_URL=${OIDC_DISCOVERY_URL}`
- `VAULT_OIDC_DISCOVERY_URL=${VAULT_OIDC_DISCOVERY_URL}`
- `VAULT_OIDC_CLIENT_ID=${VAULT_OIDC_CLIENT_ID}`
- `VAULT_OIDC_CLIENT_SECRET=${VAULT_OIDC_CLIENT_SECRET}`
- `VAULT_OIDC_ROLE=${VAULT_OIDC_ROLE}`
- `VAULT_TOKEN_FILE=/root/.vault-token`
- `OIDC_ADMIN_GROUP=/vault-a2a`
- `VAULT_UI_REDIRECT_1=http://127.0.0.1:8200/ui/vault/auth/oidc/oidc/callback`
- `VAULT_UI_REDIRECT_2=http://localhost:8200/ui/vault/auth/oidc/oidc/callback`
- `VAULT_UI_REDIRECT_3=http://vault:8200/ui/vault/auth/oidc/oidc/callback`
- `VAULT_CLI_REDIRECT_1=http://127.0.0.1:8250/oidc/callback`
- `VAULT_CLI_REDIRECT_2=http://localhost:8250/oidc/callback`
- `VAULT_CLI_REDIRECT_3=http://vault:8250/oidc/callback`
- `CURL_CA_BUNDLE=/etc/ssl/certs/keycloak-ca.crt`
- `SSL_CERT_FILE=/etc/ssl/certs/keycloak-ca.crt`


### `vault-seed`

**Image:** `alpine:3.20`
**Container name:** `vault-seed`

**Volumes:**

- `./scripts/seed-vault.sh:/usr/local/bin/seed-vault:ro,z`

**Depends on:**

- `vault`

**Networks:**

- `osss-net`

**Environment:**

- `VAULT_ADDR=http://vault:8200`
- `VAULT_TOKEN=${VAULT_TOKEN:-root}`
- `VAULT_KV_PATH=${VAULT_KV_PATH:-app}`
- `SEED_VAULT_TOKEN=${VAULT_TOKEN:-root}`
- `VERBOSE=1`
- `DEBUG=1`


### `shared-vol-init`

**Image:** `alpine:3.20`
**Container name:** `shared-vol-init`

**Volumes:**

- `es-shared:/shared:z`

**Networks:**

- `osss-net`

**Command:**

```bash
set -e
mkdir -p /shared
chmod 0777 /shared         # or 0770 with a shared group if you prefer

```


### `es-shared-init`

**Image:** `alpine:3.19`

**Volumes:**

- `es-shared:/shared:z`

**Depends on:**

- `shared-vol-init`

**Networks:**

- `osss-net`

**Command:**

```bash
sh -lc "mkdir -p /shared/filebeat-{data,logs} &&
        chown -R 501:501 /shared/filebeat-{data,logs} &&
        chmod -R 775 /shared/filebeat-{data,logs} &&
        ls -ld /shared/filebeat-*"

```


### `elasticsearch`

**Image:** `docker.elastic.co/elasticsearch/elasticsearch:8.14.3`
**Container name:** `elasticsearch`

**Ports:**

- `9200:9200`
- `9300:9300`

**Volumes:**

- `es-data:/usr/share/elasticsearch/data:z`
- `./config_files/elastic/elasticsearch.yml:/usr/share/elasticsearch/config/elasticsearch.yml:ro,z`
- `./config_files/keycloak/secrets/ca/ca.crt:/usr/share/elasticsearch/config/keycloak-ca.crt:ro,z`

**Networks:**

- `osss-net`

**Environment:**

- `OIDC_CLIENT_SECRET=${KIBANA_OIDC_CLIENT_SECRET}`
- `discovery.type=single-node`
- `xpack.security.enabled=true`
- `xpack.security.http.ssl.enabled=false`
- `ELASTIC_PASSWORD=${ELASTIC_PASSWORD}`
- `ES_JAVA_OPTS=-Xms512m -Xmx512m`
- `network.host=0.0.0.0`

**Command:**

```bash
/bin/bash -lc set -euo pipefail; [ -f config/elasticsearch.keystore ] || bin/elasticsearch-keystore create; if ! bin/elasticsearch-keystore list | grep -qx 'xpack.security.authc.realms.oidc.oidc1.rp.client_secret'; then echo "$OIDC_CLIENT_SECRET" | bin/elasticsearch-keystore add -xf xpack.security.authc.realms.oidc.oidc1.rp.client_secret; fi; exec /usr/local/bin/docker-entrypoint.sh eswrapper
```


### `kibana-pass-init`

**Image:** `curlimages/curl:8.8.0`
**Container name:** `kibana-pass-init`

**Depends on:**

- `elasticsearch`

**Networks:**

- `osss-net`

**Environment:**

- `ELASTIC_PASSWORD=${ELASTIC_PASSWORD}`
- `KIBANA_PASSWORD=${KIBANA_PASSWORD}`
- `ES_URL=http://elasticsearch:9200`

**Command:**

```bash
set -euo pipefail; now() { date -Iseconds; }; log() { printf '%s %s\n' "$$(now)" "$$*"; }; mask() { s="$$1"; [ -z "$$s" ] && printf '(empty)\n' || { [ "$${#s}" -le 8 ] && printf '******\n' || printf '%s******\n' "$${s%??????}"; }; }; log "ES_URL=$$ES_URL"; log "ELASTIC_PASSWORD=$$(mask "$$ELASTIC_PASSWORD")"; log "KIBANA_PASSWORD=$$(mask "$$KIBANA_PASSWORD")"; log "Waiting for Elasticsearch cluster health..."; __tries=0; while :; do
  __code="$$(curl -sS -o /dev/null -w '%{http_code}' -u "elastic:$$ELASTIC_PASSWORD" "$$ES_URL/_cluster/health" || echo 000)";
  log "cluster health http_code=$$__code";
  [ "$$__code" = "200" ] && break;
  __tries=$$((__tries+1)); [ "$$__tries" -le 180 ] || { log "Elasticsearch not ready after 180 attempts"; exit 1; };
  sleep 3;
done; log "Elasticsearch reachable"; log "Setting kibana_system password..."; __resp="$$(curl -sS -u "elastic:$$ELASTIC_PASSWORD" -H 'Content-Type: application/json' -w '\nHTTP_STATUS:%{http_code}\n' -X POST "$$ES_URL/_security/user/kibana_system/_password" -d "{\"password\":\"$$KIBANA_PASSWORD\"}")"; __rc="$$(printf '%s' "$$__resp" | sed -n 's/^HTTP_STATUS://p')"; __body="$$(printf '%s' "$$__resp" | sed '$$d')"; log "POST /_security/user/kibana_system/_password -> $$__rc"; if [ -z "$$__rc" ] || [ "$$__rc" -ge 400 ]; then log "Failed to set kibana_system password; response follows:"; printf '%s\n' "$$__body"; exit 1; fi; log "kibana_system password set"; log "Verifying kibana_system authentication..."; __v="$$(curl -sS -u "kibana_system:$$KIBANA_PASSWORD" -w '\nHTTP_STATUS:%{http_code}\n' "$$ES_URL/_security/_authenticate" || true)"; __v_code="$$(printf '%s' "$$__v" | sed -n 's/^HTTP_STATUS://p')"; __v_body="$$(printf '%s' "$$__v" | sed '$$d')"; log "GET /_security/_authenticate as kibana_system -> $$__v_code"; [ "$$__v_code" = "200" ] || { printf '%s\n' "$$__v_body"; exit 1; }; log "kibana-pass-init complete.";

```


### `kibana`

**Image:** `docker.elastic.co/kibana/kibana:8.14.3`
**Container name:** `kibana`

**Ports:**

- `5601:5601`

**Volumes:**

- `./config_files/elastic/kibana.yml:/usr/share/kibana/config/kibana.yml:ro,z`

**Depends on:**

- `elasticsearch`
- `kibana-pass-init`

**Networks:**

- `osss-net`

**Environment:**

- `ELASTICSEARCH_HOSTS=http://elasticsearch:9200`
- `SERVER_PUBLICBASEURL=http://kibana:5601`
- `LOGGING_VERBOSE=true`
- `ELASTICSEARCH_USERNAME=kibana_system`
- `ELASTICSEARCH_PASSWORD=${KIBANA_PASSWORD}`
- `KBN_SERVER_PUBLICBASEURL=http://localhost:5601`
- `XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY=caeb7879368e3dd66d7302f6810daec1`
- `XPACK_REPORTING_ENCRYPTIONKEY=c1c89f500966ac710f7fa5eaf2939976`
- `XPACK_SECURITY_ENCRYPTIONKEY=e1458d710ffb321e4a4f4eb792c78b2b`


### `api-key-init`

**Image:** `curlimages/curl:8.8.0`
**Container name:** `api-key-init`

**Volumes:**

- `./config_files/filebeat/mint_apikey.sh:/usr/local/bin/mint_apikey.sh:ro,z`
- `es-shared:/shared:z`

**Depends on:**

- `shared-vol-init`
- `elasticsearch`

**Networks:**

- `osss-net`

**Environment:**

- `ES_URL=http://elasticsearch:9200`
- `ELASTIC_PASSWORD=${ELASTIC_PASSWORD:-password}`

**Command:**

```bash
/bin/sh -exc echo "[api-key-init] begin"
ls -l /usr/local/bin/mint_apikey.sh || { echo "missing mint_apikey.sh" >&2; exit 1; }
# run script explicitly; we don't need +x on the file this way
/bin/sh /usr/local/bin/mint_apikey.sh

echo "[verify] checking /shared/.env.apikey"
ls -l /shared || true
if [ -s /shared/.env.apikey ]; then
  echo "[verify] permissions/owner for /shared/.env.apikey"
  stat -c 'mode=%a owner=%U group=%G' /shared/.env.apikey || true
  echo "[verify] masked key preview"
  awk -F= '/^ELASTIC_API_KEY=/{print "ELASTIC_API_KEY=" substr($$2,1,6) "..."}' /shared/.env.apikey || true
else
  echo "❌ /shared/.env.apikey missing or empty" >&2
  exit 2
fi
echo "[api-key-init] done"

```


### `filebeat-setup`

**Image:** `docker.elastic.co/beats/filebeat:8.14.3`
**Container name:** `filebeat-setup`

**Volumes:**

- `./config_files/filebeat/filebeat.setup.yml:/usr/share/filebeat/filebeat.yml:ro,z`
- `es-shared:/shared:z`
- `./config_files/filebeat/setup.sh:/usr/local/bin/setup.sh:ro,z`
- `filebeat-data:/usr/share/filebeat/data:z`
- `filebeat-logs:/usr/share/filebeat/logs:z`

**Depends on:**

- `elasticsearch`
- `kibana`
- `es-shared-init`

**Networks:**

- `osss-net`

**Environment:**

- `KIBANA_URL=http://host.containers.internal:5601`
- `ES_URL=http://host.containers.internal:9200`
- `KIBANA_USERNAME=${KIBANA_USERNAME:-elastic}`
- `KIBANA_PASSWORD=${ELASTIC_PASSWORD:-password}`
- `ELASTIC_PASSWORD=${ELASTIC_PASSWORD:-password}`

**Command:**

```bash
/usr/local/bin/setup.sh
```


### `filebeat`

**Image:** `docker.elastic.co/beats/filebeat:8.14.3`
**Container name:** `filebeat`

**Volumes:**

- `es-shared:/shared:z`
- `./:/work:ro`
- `/run/systemd/journal:/run/systemd/journal:ro,rslave,z`
- `/run/log/journal:/run/log/journal:ro,rslave,z`
- `/var/log/journal:/var/log/journal:ro,rslave,z`
- `/etc/machine-id:/etc/machine-id:ro,z`
- `/var/lib/containers:/var/lib/containers:ro,rslave,z`
- `/run/podman/podman.sock:/var/run/podman.sock:ro`

**Environment:**

- `DOCKER_HOST=unix:///var/run/podman.sock`
- `VM_PROJ=/home/core/OSSS`

**Command:**

```bash
filebeat -e -c /work/config_files/filebeat/filebeat.podman.yml -E path.data=/shared/filebeat-data -E path.logs=/shared/filebeat-logs -E logging.level=debug -E logging.selectors=journald
```


### `trino`

**Image:** `trinodb/trino:latest`
**Container name:** `trino`

**Ports:**

- `8444:8443`

**Volumes:**

- `./config_files/trino_data:/var/trino:z`
- `./config_files/trino/etc:/etc/trino:ro,z`
- `./config_files/trino/opt/osss-truststore.p12:/opt/trust/osss-truststore.p12:ro,z`

**Networks:**

- `osss-net`

**Environment:**

- `JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=/opt/trust/osss-truststore.p12 -Djavax.net.ssl.trustStorePassword=changeit -Djavax.net.ssl.trustStoreType=PKCS12
`


### `superset-build`

**Image:** `osss/superset:with-drivers`
**Build context:** `.`
**Dockerfile:** `docker/superset/Dockerfile`

**Command:**

```bash
true
```


### `superset_redis`

**Image:** `redis:7-alpine`
**Container name:** `superset_redis`

**Ports:**

- `6381:6379`

**Volumes:**

- `superset_redis_data:/data:z`

**Networks:**

- `osss-net`

**Command:**

```bash
redis-server --appendonly yes
```


### `postgres-superset`

**Image:** `postgres:16`
**Container name:** `postgres-superset`

**Ports:**

- `5434:5432`

**Volumes:**

- `pg_superset_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_USER=osss`
- `POSTGRES_PASSWORD=osss`
- `POSTGRES_DB=superset`


### `superset-init`

**Image:** `osss/superset:with-drivers`
**Container name:** `superset-init`

**Volumes:**

- `./config_files/superset:/app/pythonpath:ro,z`
- `./config_files/keycloak/secrets/ca/ca.crt:/etc/ssl/certs/keycloak-ca.crt:ro,z`
- `./config_files/keycloak/secrets/ca/ca-chain.pem:/etc/ssl/certs/osss-dev-ca-chain.pem:ro,z`

**Depends on:**

- `postgres-superset`

**Networks:**

- `osss-net`

**Environment:**

- `SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py`
- `PYTHONUNBUFFERED=1`
- `PYTHONPATH=/app/pythonpath:/app/superset_home/pythonpath`
- `REQUESTS_CA_BUNDLE=/etc/ssl/certs/osss-dev-ca-chain.pem`
- `SSL_CERT_FILE=/etc/ssl/certs/osss-dev-ca-chain.pem`
- `OAUTHLIB_INSECURE_TRANSPORT=0`
- `KEYCLOAK_CLIENT_ID=superset`
- `KEYCLOAK_CLIENT_SECRET=password`
- `KEYCLOAK_BASE_URL=https://keycloak.local:8443/realms/OSSS`
- `KEYCLOAK_TOKEN_URL=https://keycloak.local:8443/realms/OSSS/protocol/openid-connect/token`
- `KEYCLOAK_AUTH_URL=https://keycloak.local:8443/realms/OSSS/protocol/openid-connect/auth`
- `KEYCLOAK_REALM=OSSS`
- `KEYCLOAK_HOST=keycloak.local:8443`

**Command:**

```bash
bash -lc set -euo pipefail && echo "[deps] installing wheels into /app/superset_home/pythonpath..." && REQUESTS_CA_BUNDLE= SSL_CERT_FILE= PIP_CERT= \
  pip install --no-cache-dir --target /app/superset_home/pythonpath \
  "psycopg2-binary==2.9.*" pillow redis Authlib &&
echo "[init] db upgrade..." && /app/.venv/bin/superset db upgrade && echo "[init] create admin if missing..." && /app/.venv/bin/superset fab create-admin \
  --username admin --firstname Admin --lastname User \
  --email admin@example.com --password admin || true &&
echo "[init] superset init..." && /app/.venv/bin/superset init && echo "[init] done."

```


### `superset`

**Image:** `osss/superset:with-drivers`
**Container name:** `superset`

**Ports:**

- `8088:8088`

**Volumes:**

- `./config_files/superset:/app/pythonpath:ro`
- `./config_files/keycloak/secrets/ca/ca.crt:/etc/ssl/certs/keycloak-ca.crt:ro,z`
- `./config_files/keycloak/secrets/ca/ca-chain.pem:/etc/ssl/certs/osss-dev-ca-chain.pem:ro,z`

**Depends on:**

- `postgres-superset`
- `superset_redis`
- `superset-init`

**Networks:**

- `osss-net`

**Environment:**

- `SUPERSET_SECRET_KEY=please_change_me`
- `SUPERSET__SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://osss:osss@postgres-superset:5432/superset`
- `SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://osss:osss@postgres-superset:5432/superset`
- `FLASK_LIMITER_ENABLED=false`
- `GUNICORN_CMD_ARGS=--limit-request-field_size 65536 --limit-request-line 16384`
- `RATELIMIT_STORAGE_URI=redis://superset_redis:6379/1`
- `ENABLE_PROXY_FIX=true`
- `PYTHONPATH=/app/pythonpath:/app/superset_home/pythonpath`
- `REQUESTS_CA_BUNDLE=/etc/ssl/certs/osss-dev-ca-chain.pem`
- `SSL_CERT_FILE=/etc/ssl/certs/osss-dev-ca-chain.pem`
- `OAUTHLIB_INSECURE_TRANSPORT=0`
- `KEYCLOAK_CLIENT_ID=superset`
- `KEYCLOAK_CLIENT_SECRET=password`
- `KEYCLOAK_BASE_URL=https://keycloak.local:8443/realms/OSSS`
- `KEYCLOAK_TOKEN_URL=https://keycloak.local:8443/realms/OSSS/protocol/openid-connect/token`
- `KEYCLOAK_AUTH_URL=https://keycloak.local:8443/realms/OSSS/protocol/openid-connect/auth`
- `KEYCLOAK_REALM=OSSS`
- `KEYCLOAK_HOST=keycloak.local:8443`

**Command:**

```bash
bash -lc set -euo pipefail && echo "[deps] installing wheels into /app/superset_home/pythonpath..." && REQUESTS_CA_BUNDLE= SSL_CERT_FILE= PIP_CERT= \
  pip install --no-cache-dir --target /app/superset_home/pythonpath \
  "psycopg2-binary==2.9.*" pillow redis Authlib &&
exec /app/.venv/bin/gunicorn -w 4 --timeout 300 -b 0.0.0.0:8088 'superset.app:create_app()'

```


### `postgres-airflow`

**Image:** `postgres:16`
**Container name:** `postgres-airflow`

**Ports:**

- `5435:5432`

**Volumes:**

- `airflow-pgdata:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_USER=airflow`
- `POSTGRES_PASSWORD=airflow`
- `POSTGRES_DB=airflow`


### `airflow-init`

**Image:** `apache/airflow:2.9.3-python3.11`
**Container name:** `airflow-init`

**Volumes:**

- `./config_files/airflow/dags:/opt/airflow/dags:z`

**Depends on:**

- `postgres-airflow`

**Networks:**

- `osss-net`

**Environment:**

- `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow`
- `AIRFLOW__CORE__LOAD_EXAMPLES=False`
- `AIRFLOW__LOGGING__LOGGING_LEVEL=INFO`

**Command:**

```bash
set -euo pipefail
airflow db migrate
airflow users create --username admin --firstname Admin --lastname User --role Admin --email admin@example.com --password admin || true

```


### `airflow-webserver`

**Image:** `apache/airflow:2.9.3-python3.11`
**Container name:** `airflow-webserver`

**Ports:**

- `8083:8080`

**Volumes:**

- `./config_files/airflow/dags:/opt/airflow/dags:z`
- `./config_files/airflow/webserver_config.py:/opt/airflow/webserver_config.py:ro,z`
- `./config_files/keycloak/secrets/ca/ca.crt:/etc/ssl/certs/keycloak-ca.crt:ro,z`
- `./config_files/keycloak/secrets/ca/ca-chain.pem:/etc/ssl/certs/osss-dev-ca-chain.pem:ro,z`

**Depends on:**

- `airflow-init`
- `airflow-redis`

**Networks:**

- `osss-net`

**Environment:**

- `AIRFLOW__WEBSERVER__WEB_SERVER_CONFIG=/opt/airflow/webserver_config.py`
- `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow`
- `AIRFLOW__WEBSERVER__AUTHENTICATE=True`
- `AIRFLOW__WEBSERVER__BASE_URL=http://localhost:8083`
- `AIRFLOW__WEBSERVER__SECRET_KEY=change-this-in-prod`
- `AIRFLOW__WEBSERVER__ENABLE_PROXY_FIX=True`
- `KEYCLOAK_URL=https://keycloak.local:8443`
- `KEYCLOAK_REALM=OSSS`
- `KEYCLOAK_AIRFLOW_CLIENT_ID=airflow`
- `KEYCLOAK_AIRFLOW_CLIENT_SECRET=password`
- `AIRFLOW__FAB__LIMITER_ENABLED=True`
- `FAB_LIMITER_STORAGE_URI=redis://airflow-redis:6379/0`
- `RATELIMIT_STORAGE_URI=redis://airflow-redis:6379/0`
- `GUNICORN_CMD_ARGS=--limit-request-field_size 65536 --limit-request-line 16384`
- `REQUESTS_CA_BUNDLE=/etc/ssl/certs/keycloak-ca.crt`
- `SSL_CERT_FILE=/etc/ssl/certs/keycloak-ca.crt`
- `CURL_CA_BUNDLE=/etc/ssl/certs/keycloak-ca.crt`

**Command:**

```bash
webserver
```


### `airflow-scheduler`

**Image:** `apache/airflow:2.9.3-python3.11`
**Container name:** `airflow-scheduler`

**Volumes:**

- `./config_files/airflow/dags:/opt/airflow/dags:z`
- `./config_files/airflow/webserver_config.py:/opt/airflow/webserver_config.py:ro,z`

**Depends on:**

- `airflow-init`
- `airflow-redis`

**Networks:**

- `osss-net`

**Environment:**

- `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@postgres-airflow/airflow`
- `KEYCLOAK_URL=https://keycloak.local:8443`
- `KEYCLOAK_REALM=OSSS`

**Command:**

```bash
scheduler
```


### `airflow-redis`

**Image:** `redis:7-alpine`
**Container name:** `airflow-redis`

**Ports:**

- `6380:6379`

**Networks:**

- `osss-net`


### `execute-migrate-all`

**Image:** `docker.getcollate.io/openmetadata/server:1.9.12`
**Container name:** `execute_migrate_all`

**Volumes:**

- `./config_files/openmetadata/openmetadata.yaml:/usr/local/openmetadata/conf/openmetadata.yaml:ro`
- `./config_files/openmetadata/openmetadata.yaml:/openmetadata/conf/openmetadata.yaml:ro`
- `./config_files/openmetadata/certs:/opt/om-trust:ro,z`

**Depends on:**

- `om-elasticsearch`
- `mysql`

**Networks:**

- `osss-net`

**Environment:**

- `OPENMETADATA_CLUSTER_NAME=${OPENMETADATA_CLUSTER_NAME:-openmetadata}`
- `SERVER_PORT=${SERVER_PORT:-8585}`
- `SERVER_ADMIN_PORT=${SERVER_ADMIN_PORT:-8586}`
- `LOG_LEVEL=${LOG_LEVEL:-INFO}`
- `MIGRATION_LIMIT_PARAM=${MIGRATION_LIMIT_PARAM:-1200}`
- `AUTHENTICATION_PROVIDER=${OM_AUTHENTICATION_PROVIDER:-basic}`
- `CUSTOM_OIDC_AUTHENTICATION_PROVIDER_NAME=${CUSTOM_OIDC_AUTHENTICATION_PROVIDER_NAME:-"Keycloak"}`
- `AUTHENTICATION_RESPONSE_TYPE=${OM_AUTHENTICATION_RESPONSE_TYPE:-id_token}`
- `AUTHENTICATION_CALLBACK_URL=${OM_AUTHENTICATION_CALLBACK_URL:-http://localhost:8585/callback}`
- `AUTHENTICATION_ENABLE_SELF_SIGNUP=${AUTHENTICATION_ENABLE_SELF_SIGNUP:-true}`
- `OIDC_DISCOVERY_URI=${OM_OIDC_DISCOVERY_URI:-""}`
- `OIDC_CLIENT_ID=${OM_OIDC_CLIENT_ID:-""}`
- `OIDC_CLIENT_SECRET=${OM_OIDC_CLIENT_SECRET:-""}`
- `OIDC_SCOPES=openid profile email`
- `AUTHORIZER_CLASS_NAME=${AUTHORIZER_CLASS_NAME:-org.openmetadata.service.security.DefaultAuthorizer}`
- `AUTHORIZER_REQUEST_FILTER=${AUTHORIZER_REQUEST_FILTER:-org.openmetadata.service.security.JwtFilter}`
- `AUTHORIZER_ADMIN_PRINCIPALS=${AUTHORIZER_ADMIN_PRINCIPALS:-[a2a]}`
- `AUTHORIZER_ALLOWED_REGISTRATION_DOMAIN=${AUTHORIZER_ALLOWED_REGISTRATION_DOMAIN:-["all"]}`
- `AUTHORIZER_INGESTION_PRINCIPALS=${AUTHORIZER_INGESTION_PRINCIPALS:-[ingestion-bot]}`
- `AUTHORIZER_PRINCIPAL_DOMAIN=${AUTHORIZER_PRINCIPAL_DOMAIN:-"open-metadata.org"}`
- `AUTHORIZER_ALLOWED_DOMAINS=${AUTHORIZER_ALLOWED_DOMAINS:-[]}`
- `AUTHORIZER_ENFORCE_PRINCIPAL_DOMAIN=${AUTHORIZER_ENFORCE_PRINCIPAL_DOMAIN:-false}`
- `AUTHORIZER_ENABLE_SECURE_SOCKET=${AUTHORIZER_ENABLE_SECURE_SOCKET:-false}`
- `AUTHENTICATION_AUTHORITY=${AUTHENTICATION_AUTHORITY:-https://accounts.google.com}`
- `AUTHENTICATION_CLIENT_ID=${AUTHENTICATION_CLIENT_ID:-""}`
- `AUTHENTICATION_JWT_PRINCIPAL_CLAIMS_MAPPING=${AUTHENTICATION_JWT_PRINCIPAL_CLAIMS_MAPPING:-[]}`
- `AUTHENTICATION_CLIENT_TYPE=${AUTHENTICATION_CLIENT_TYPE:-public}`
- `OIDC_TYPE=${OIDC_TYPE:-""}`
- `OIDC_SCOPE=${OIDC_SCOPE:-"openid email profile"}`
- `OIDC_USE_NONCE=${OIDC_USE_NONCE:-true}`
- `OIDC_PREFERRED_JWS=${OIDC_PREFERRED_JWS:-"RS256"}`
- `OIDC_RESPONSE_TYPE=${OIDC_RESPONSE_TYPE:-"code"}`
- `OIDC_DISABLE_PKCE=${OIDC_DISABLE_PKCE:-true}`
- `OIDC_CALLBACK=${OIDC_CALLBACK:-"http://localhost:8585/callback"}`
- `OIDC_SERVER_URL=${OIDC_SERVER_URL:-"http://localhost:8585"}`
- `OIDC_CLIENT_AUTH_METHOD=${OIDC_CLIENT_AUTH_METHOD:-"client_secret_post"}`
- `OIDC_TENANT=${OIDC_TENANT:-""}`
- `OIDC_MAX_CLOCK_SKEW=${OIDC_MAX_CLOCK_SKEW:-""}`
- `OIDC_CUSTOM_PARAMS=${OIDC_CUSTOM_PARAMS:-}`
- `OIDC_MAX_AGE=${OIDC_MAX_AGE:-"0"}`
- `OIDC_PROMPT_TYPE=${OIDC_PROMPT_TYPE:-"consent"}`
- `OIDC_SESSION_EXPIRY=${OIDC_SESSION_EXPIRY:-"604800"}`
- `RSA_PUBLIC_KEY_FILE_PATH=${RSA_PUBLIC_KEY_FILE_PATH:-"./conf/public_key.der"}`
- `RSA_PRIVATE_KEY_FILE_PATH=${RSA_PRIVATE_KEY_FILE_PATH:-"./conf/private_key.der"}`
- `JWT_ISSUER=${JWT_ISSUER:-"open-metadata.org"}`
- `JWT_KEY_ID=${JWT_KEY_ID:-"Gb389a-9f76-gdjs-a92j-0242bk94356"}`
- `PIPELINE_SERVICE_CLIENT_ENDPOINT=${PIPELINE_SERVICE_CLIENT_ENDPOINT:-http://ingestion:8080}`
- `PIPELINE_SERVICE_CLIENT_HEALTH_CHECK_INTERVAL=${PIPELINE_SERVICE_CLIENT_HEALTH_CHECK_INTERVAL:-300}`
- `SERVER_HOST_API_URL=${SERVER_HOST_API_URL:-http://openmetadata-server:8585/api}`
- `PIPELINE_SERVICE_CLIENT_VERIFY_SSL=${PIPELINE_SERVICE_CLIENT_VERIFY_SSL:-"no-ssl"}`
- `PIPELINE_SERVICE_CLIENT_SSL_CERT_PATH=${PIPELINE_SERVICE_CLIENT_SSL_CERT_PATH:-""}`
- `DB_DRIVER_CLASS=${DB_DRIVER_CLASS:-com.mysql.cj.jdbc.Driver}`
- `DB_SCHEME=${DB_SCHEME:-mysql}`
- `DB_PARAMS=${DB_PARAMS:-allowPublicKeyRetrieval=true&useSSL=false&serverTimezone=UTC}`
- `DB_USER=${DB_USER:-openmetadata_user}`
- `DB_USER_PASSWORD=${DB_USER_PASSWORD:-openmetadata_password}`
- `DB_HOST=${DB_HOST:-mysql}`
- `DB_PORT=${DB_PORT:-3306}`
- `OM_DATABASE=${OM_DATABASE:-openmetadata}`
- `ELASTICSEARCH_HOST=${OM_ELASTICSEARCH_HOST:-om-elasticsearch}`
- `ELASTICSEARCH_PORT=${OM_ELASTICSEARCH_PORT:-9201}`
- `ELASTICSEARCH_SCHEME=${ELASTICSEARCH_SCHEME:-http}`
- `ELASTICSEARCH_USER=${ELASTICSEARCH_USER:-""}`
- `ELASTICSEARCH_PASSWORD=${ELASTICSEARCH_PASSWORD:-""}`
- `SEARCH_TYPE=${SEARCH_TYPE:- "elasticsearch"}`
- `ELASTICSEARCH_TRUST_STORE_PATH=${ELASTICSEARCH_TRUST_STORE_PATH:-""}`
- `ELASTICSEARCH_TRUST_STORE_PASSWORD=${ELASTICSEARCH_TRUST_STORE_PASSWORD:-""}`
- `ELASTICSEARCH_CONNECTION_TIMEOUT_SECS=${ELASTICSEARCH_CONNECTION_TIMEOUT_SECS:-5}`
- `ELASTICSEARCH_SOCKET_TIMEOUT_SECS=${ELASTICSEARCH_SOCKET_TIMEOUT_SECS:-60}`
- `ELASTICSEARCH_KEEP_ALIVE_TIMEOUT_SECS=${ELASTICSEARCH_KEEP_ALIVE_TIMEOUT_SECS:-600}`
- `ELASTICSEARCH_BATCH_SIZE=${ELASTICSEARCH_BATCH_SIZE:-100}`
- `ELASTICSEARCH_PAYLOAD_BYTES_SIZE=${ELASTICSEARCH_PAYLOAD_BYTES_SIZE:-10485760}`
- `ELASTICSEARCH_INDEX_MAPPING_LANG=${ELASTICSEARCH_INDEX_MAPPING_LANG:-EN}`
- `EVENT_MONITOR=${EVENT_MONITOR:-prometheus}`
- `EVENT_MONITOR_BATCH_SIZE=${EVENT_MONITOR_BATCH_SIZE:-10}`
- `EVENT_MONITOR_PATH_PATTERN=${EVENT_MONITOR_PATH_PATTERN:-["/api/v1/tables/*", "/api/v1/health-check"]}`
- `EVENT_MONITOR_LATENCY=${EVENT_MONITOR_LATENCY:-[]}`
- `PIPELINE_SERVICE_CLIENT_ENABLED=${PIPELINE_SERVICE_CLIENT_ENABLED:-true}`
- `PIPELINE_SERVICE_CLIENT_CLASS_NAME=${PIPELINE_SERVICE_CLIENT_CLASS_NAME:-"org.openmetadata.service.clients.pipeline.airflow.AirflowRESTClient"}`
- `PIPELINE_SERVICE_IP_INFO_ENABLED=${PIPELINE_SERVICE_IP_INFO_ENABLED:-false}`
- `PIPELINE_SERVICE_CLIENT_HOST_IP=${PIPELINE_SERVICE_CLIENT_HOST_IP:-""}`
- `PIPELINE_SERVICE_CLIENT_SECRETS_MANAGER_LOADER=${PIPELINE_SERVICE_CLIENT_SECRETS_MANAGER_LOADER:-"noop"}`
- `AIRFLOW_USERNAME=${AIRFLOW_USERNAME:-a2a}`
- `AIRFLOW_PASSWORD=${AIRFLOW_PASSWORD:-a2a}`
- `AIRFLOW_TIMEOUT=${AIRFLOW_TIMEOUT:-10}`
- `AIRFLOW_TRUST_STORE_PATH=${AIRFLOW_TRUST_STORE_PATH:-""}`
- `AIRFLOW_TRUST_STORE_PASSWORD=${AIRFLOW_TRUST_STORE_PASSWORD:-""}`
- `FERNET_KEY=${FERNET_KEY:-jJ/9sz0g0OHxsfxOoSfdFdmk3ysNmPRnH3TUAbz3IHA=}`
- `SECRET_MANAGER=${SECRET_MANAGER:-db}`
- `OM_SM_REGION=${OM_SM_REGION:-""}`
- `OM_SM_ACCESS_KEY_ID=${OM_SM_ACCESS_KEY_ID:-""}`
- `OM_SM_ACCESS_KEY=${OM_SM_ACCESS_KEY:-""}`
- `OM_SM_VAULT_NAME=${OM_SM_VAULT_NAME:-""}`
- `OM_SM_CLIENT_ID=${OM_SM_CLIENT_ID:-""}`
- `OM_SM_CLIENT_SECRET=${OM_SM_CLIENT_SECRET:-""}`
- `OM_SM_TENANT_ID=${OM_SM_TENANT_ID:-""}`
- `OM_EMAIL_ENTITY=${OM_EMAIL_ENTITY:-"OpenMetadata"}`
- `OM_SUPPORT_URL=${OM_SUPPORT_URL:-"https://slack.open-metadata.org"}`
- `AUTHORIZER_ENABLE_SMTP=${AUTHORIZER_ENABLE_SMTP:-false}`
- `OPENMETADATA_SERVER_URL=${OPENMETADATA_SERVER_URL:-""}`
- `OPENMETADATA_SMTP_SENDER_MAIL=${OPENMETADATA_SMTP_SENDER_MAIL:-""}`
- `SMTP_SERVER_ENDPOINT=${SMTP_SERVER_ENDPOINT:-""}`
- `SMTP_SERVER_PORT=${SMTP_SERVER_PORT:-""}`
- `SMTP_SERVER_USERNAME=${SMTP_SERVER_USERNAME:-""}`
- `SMTP_SERVER_PWD=${SMTP_SERVER_PWD:-""}`
- `SMTP_SERVER_STRATEGY=${SMTP_SERVER_STRATEGY:-"SMTP_TLS"}`
- `OPENMETADATA_HEAP_OPTS=${OPENMETADATA_HEAP_OPTS:--Xmx1G -Xms1G}`
- `MASK_PASSWORDS_API=${MASK_PASSWORDS_API:-false}`
- `WEB_CONF_URI_PATH=${WEB_CONF_URI_PATH:-"/api"}`
- `WEB_CONF_HSTS_ENABLED=${WEB_CONF_HSTS_ENABLED:-false}`
- `WEB_CONF_HSTS_MAX_AGE=${WEB_CONF_HSTS_MAX_AGE:-"365 days"}`
- `WEB_CONF_HSTS_INCLUDE_SUBDOMAINS=${WEB_CONF_HSTS_INCLUDE_SUBDOMAINS:-"true"}`
- `WEB_CONF_HSTS_PRELOAD=${WEB_CONF_HSTS_PRELOAD:-"true"}`
- `WEB_CONF_FRAME_OPTION_ENABLED=${WEB_CONF_FRAME_OPTION_ENABLED:-false}`
- `WEB_CONF_FRAME_OPTION=${WEB_CONF_FRAME_OPTION:-"SAMEORIGIN"}`
- `WEB_CONF_FRAME_ORIGIN=${WEB_CONF_FRAME_ORIGIN:-""}`
- `WEB_CONF_CONTENT_TYPE_OPTIONS_ENABLED=${WEB_CONF_CONTENT_TYPE_OPTIONS_ENABLED:-false}`
- `WEB_CONF_XSS_PROTECTION_ENABLED=${WEB_CONF_XSS_PROTECTION_ENABLED:-false}`
- `WEB_CONF_XSS_PROTECTION_ON=${WEB_CONF_XSS_PROTECTION_ON:-true}`
- `WEB_CONF_XSS_PROTECTION_BLOCK=${WEB_CONF_XSS_PROTECTION_BLOCK:-true}`
- `WEB_CONF_XSS_CSP_ENABLED=${WEB_CONF_XSS_CSP_ENABLED:-false}`
- `WEB_CONF_XSS_CSP_POLICY=${WEB_CONF_XSS_CSP_POLICY:-"default-src 'self'"}`
- `WEB_CONF_XSS_CSP_REPORT_ONLY_POLICY=${WEB_CONF_XSS_CSP_REPORT_ONLY_POLICY:-""}`
- `WEB_CONF_REFERRER_POLICY_ENABLED=${WEB_CONF_REFERRER_POLICY_ENABLED:-false}`
- `WEB_CONF_REFERRER_POLICY_OPTION=${WEB_CONF_REFERRER_POLICY_OPTION:-"SAME_ORIGIN"}`
- `WEB_CONF_PERMISSION_POLICY_ENABLED=${WEB_CONF_PERMISSION_POLICY_ENABLED:-false}`
- `WEB_CONF_PERMISSION_POLICY_OPTION=${WEB_CONF_PERMISSION_POLICY_OPTION:-""}`
- `WEB_CONF_CACHE_CONTROL=${WEB_CONF_CACHE_CONTROL:-""}`
- `WEB_CONF_PRAGMA=${WEB_CONF_PRAGMA:-""}`
- `JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=/opt/om-trust/om-truststore.p12 -Djavax.net.ssl.trustStorePassword=changeit -Djavax.net.ssl.trustStoreType=PKCS12`

**Command:**

```bash
./bootstrap/openmetadata-ops.sh migrate
```


### `openmetadata-server`

**Image:** `docker.getcollate.io/openmetadata/server:1.9.12`
**Container name:** `openmetadata-server`

**Ports:**

- `8585:8585`
- `8586:8586`

**Volumes:**

- `./config_files/openmetadata/openmetadata.yaml:/usr/local/openmetadata/conf/openmetadata.yaml:ro,z`
- `./config_files/openmetadata/certs:/opt/om-trust:ro,z`

**Depends on:**

- `om-elasticsearch`
- `mysql`
- `execute-migrate-all`

**Networks:**

- `osss-net`

**Environment:**

- `OPENMETADATA_CLUSTER_NAME=${OPENMETADATA_CLUSTER_NAME:-openmetadata}`
- `SERVER_PORT=${SERVER_PORT:-8585}`
- `SERVER_ADMIN_PORT=${SERVER_ADMIN_PORT:-8586}`
- `LOG_LEVEL=${LOG_LEVEL:-INFO}`
- `AUTHENTICATION_PROVIDER=${OM_AUTHENTICATION_PROVIDER:-basic}`
- `CUSTOM_OIDC_AUTHENTICATION_PROVIDER_NAME=${CUSTOM_OIDC_AUTHENTICATION_PROVIDER_NAME:-"Keycloak"}`
- `AUTHENTICATION_RESPONSE_TYPE=${OM_AUTHENTICATION_RESPONSE_TYPE:-id_token}`
- `AUTHENTICATION_CALLBACK_URL=${OM_AUTHENTICATION_CALLBACK_URL:-http://localhost:8585/callback}`
- `AUTHENTICATION_ENABLE_SELF_SIGNUP=${AUTHENTICATION_ENABLE_SELF_SIGNUP:-true}`
- `AUTHENTICATION_JWT_PRINCIPAL_CLAIMS_MAPPING=${AUTHENTICATION_JWT_PRINCIPAL_CLAIMS_MAPPING:-[]}`
- `OIDC_DISCOVERY_URI=${OM_OIDC_DISCOVERY_URI:-""}`
- `OIDC_CLIENT_ID=${OM_OIDC_CLIENT_ID:-""}`
- `OIDC_CLIENT_SECRET=${OM_OIDC_CLIENT_SECRET:-""}`
- `OIDC_SCOPES=openid profile email`
- `AUTHORIZER_CLASS_NAME=${AUTHORIZER_CLASS_NAME:-org.openmetadata.service.security.DefaultAuthorizer}`
- `AUTHORIZER_REQUEST_FILTER=${AUTHORIZER_REQUEST_FILTER:-org.openmetadata.service.security.JwtFilter}`
- `AUTHORIZER_ADMIN_PRINCIPALS=${AUTHORIZER_ADMIN_PRINCIPALS:-[a2a]}`
- `AUTHORIZER_ALLOWED_REGISTRATION_DOMAIN=${AUTHORIZER_ALLOWED_REGISTRATION_DOMAIN:-["all"]}`
- `AUTHORIZER_INGESTION_PRINCIPALS=${AUTHORIZER_INGESTION_PRINCIPALS:-[ingestion-bot]}`
- `AUTHORIZER_PRINCIPAL_DOMAIN=${AUTHORIZER_PRINCIPAL_DOMAIN:-"open-metadata.org"}`
- `AUTHORIZER_ALLOWED_DOMAINS=${AUTHORIZER_ALLOWED_DOMAINS:-[]}`
- `AUTHORIZER_ENFORCE_PRINCIPAL_DOMAIN=${AUTHORIZER_ENFORCE_PRINCIPAL_DOMAIN:-false}`
- `AUTHORIZER_ENABLE_SECURE_SOCKET=${AUTHORIZER_ENABLE_SECURE_SOCKET:-false}`
- `AUTHENTICATION_OIDC_DISCOVERY_URI=${OM_AUTHENTICATION_OIDC_DISCOVERY_URI:-https://keycloak.local:8443/realms/OSSS/.well-known/openid-configuration}`
- `AUTHENTICATION_AUTHORITY=${OM_AUTHENTICATION_AUTHORITY:-https://accounts.google.com}`
- `AUTHENTICATION_CLIENT_ID=${OM_AUTHENTICATION_CLIENT_ID:-""}`
- `AUTHENTICATION_CLIENT_SECRET=${OM_AUTHENTICATION_CLIENT_SECRET:-password}`
- `AUTHENTICATION_SCOPE=${OM_AUTHENTICATION_SCOPE:-"openid profile email groups"}`
- `AUTHENTICATION_JWT_PRINCIPAL_CLAIMS=${AUTHENTICATION_JWT_PRINCIPAL_CLAIMS:-[email,preferred_username,sub]}`
- `AUTHENTICATION_CLIENT_TYPE=${OM_AUTHENTICATION_CLIENT_TYPE:-public}`
- `OIDC_TYPE=${OIDC_TYPE:-""}`
- `OIDC_SCOPE=${OIDC_SCOPE:-"openid email profile"}`
- `OIDC_USE_NONCE=${OIDC_USE_NONCE:-true}`
- `OIDC_PREFERRED_JWS=${OIDC_PREFERRED_JWS:-"RS256"}`
- `OIDC_RESPONSE_TYPE=${OIDC_RESPONSE_TYPE:-"code"}`
- `OIDC_DISABLE_PKCE=${OIDC_DISABLE_PKCE:-true}`
- `OIDC_CALLBACK=${OIDC_CALLBACK:-"http://localhost:8585/callback"}`
- `OIDC_SERVER_URL=${OIDC_SERVER_URL:-"http://localhost:8585"}`
- `OIDC_CLIENT_AUTH_METHOD=${OIDC_CLIENT_AUTH_METHOD:-"client_secret_post"}`
- `OIDC_TENANT=${OIDC_TENANT:-""}`
- `OIDC_MAX_CLOCK_SKEW=${OIDC_MAX_CLOCK_SKEW:-""}`
- `OIDC_CUSTOM_PARAMS=${OIDC_CUSTOM_PARAMS:-}`
- `OIDC_MAX_AGE=${OIDC_MAX_AGE:-"0"}`
- `OIDC_PROMPT_TYPE=${OIDC_PROMPT_TYPE:-"consent"}`
- `OIDC_SESSION_EXPIRY=${OIDC_SESSION_EXPIRY:-"604800"}`
- `RSA_PUBLIC_KEY_FILE_PATH=${RSA_PUBLIC_KEY_FILE_PATH:-"./conf/public_key.der"}`
- `RSA_PRIVATE_KEY_FILE_PATH=${RSA_PRIVATE_KEY_FILE_PATH:-"./conf/private_key.der"}`
- `JWT_ISSUER=${JWT_ISSUER:-"open-metadata.org"}`
- `JWT_KEY_ID=${JWT_KEY_ID:-"Gb389a-9f76-gdjs-a92j-0242bk94356"}`
- `PIPELINE_SERVICE_CLIENT_ENDPOINT=${PIPELINE_SERVICE_CLIENT_ENDPOINT:-http://ingestion:8082}`
- `PIPELINE_SERVICE_CLIENT_HEALTH_CHECK_INTERVAL=${PIPELINE_SERVICE_CLIENT_HEALTH_CHECK_INTERVAL:-300}`
- `SERVER_HOST_API_URL=${SERVER_HOST_API_URL:-http://openmetadata-server:8585/api}`
- `PIPELINE_SERVICE_CLIENT_VERIFY_SSL=${PIPELINE_SERVICE_CLIENT_VERIFY_SSL:-"no-ssl"}`
- `PIPELINE_SERVICE_CLIENT_SSL_CERT_PATH=${PIPELINE_SERVICE_CLIENT_SSL_CERT_PATH:-""}`
- `DB_DRIVER_CLASS=${DB_DRIVER_CLASS:-com.mysql.cj.jdbc.Driver}`
- `DB_SCHEME=${DB_SCHEME:-mysql}`
- `DB_PARAMS=${DB_PARAMS:-allowPublicKeyRetrieval=true&useSSL=false&serverTimezone=UTC}`
- `DB_USER=${DB_USER:-openmetadata_user}`
- `DB_USER_PASSWORD=${DB_USER_PASSWORD:-openmetadata_password}`
- `DB_HOST=${DB_HOST:-mysql}`
- `DB_PORT=${DB_PORT:-3306}`
- `OM_DATABASE=${OM_DATABASE:-openmetadata}`
- `ELASTICSEARCH_HOST=${OM_ELASTICSEARCH_HOST:-om-elasticsearch}`
- `ELASTICSEARCH_PORT=${OM_ELASTICSEARCH_PORT:-9201}`
- `ELASTICSEARCH_SCHEME=${ELASTICSEARCH_SCHEME:-http}`
- `ELASTICSEARCH_USER=${ELASTICSEARCH_USER:-""}`
- `ELASTICSEARCH_PASSWORD=${ELASTICSEARCH_PASSWORD:-""}`
- `SEARCH_TYPE=${SEARCH_TYPE:- "elasticsearch"}`
- `ELASTICSEARCH_TRUST_STORE_PATH=${ELASTICSEARCH_TRUST_STORE_PATH:-""}`
- `ELASTICSEARCH_TRUST_STORE_PASSWORD=${ELASTICSEARCH_TRUST_STORE_PASSWORD:-""}`
- `ELASTICSEARCH_CONNECTION_TIMEOUT_SECS=${ELASTICSEARCH_CONNECTION_TIMEOUT_SECS:-5}`
- `ELASTICSEARCH_SOCKET_TIMEOUT_SECS=${ELASTICSEARCH_SOCKET_TIMEOUT_SECS:-60}`
- `ELASTICSEARCH_KEEP_ALIVE_TIMEOUT_SECS=${ELASTICSEARCH_KEEP_ALIVE_TIMEOUT_SECS:-600}`
- `ELASTICSEARCH_BATCH_SIZE=${ELASTICSEARCH_BATCH_SIZE:-100}`
- `ELASTICSEARCH_PAYLOAD_BYTES_SIZE=${ELASTICSEARCH_PAYLOAD_BYTES_SIZE:-10485760}`
- `ELASTICSEARCH_INDEX_MAPPING_LANG=${ELASTICSEARCH_INDEX_MAPPING_LANG:-EN}`
- `EVENT_MONITOR=${EVENT_MONITOR:-prometheus}`
- `EVENT_MONITOR_BATCH_SIZE=${EVENT_MONITOR_BATCH_SIZE:-10}`
- `EVENT_MONITOR_PATH_PATTERN=${EVENT_MONITOR_PATH_PATTERN:-["/api/v1/tables/*", "/api/v1/health-check"]}`
- `EVENT_MONITOR_LATENCY=${EVENT_MONITOR_LATENCY:-[]}`
- `PIPELINE_SERVICE_CLIENT_ENABLED=${PIPELINE_SERVICE_CLIENT_ENABLED:-true}`
- `PIPELINE_SERVICE_CLIENT_CLASS_NAME=${PIPELINE_SERVICE_CLIENT_CLASS_NAME:-"org.openmetadata.service.clients.pipeline.airflow.AirflowRESTClient"}`
- `PIPELINE_SERVICE_IP_INFO_ENABLED=${PIPELINE_SERVICE_IP_INFO_ENABLED:-false}`
- `PIPELINE_SERVICE_CLIENT_HOST_IP=${PIPELINE_SERVICE_CLIENT_HOST_IP:-""}`
- `PIPELINE_SERVICE_CLIENT_SECRETS_MANAGER_LOADER=${PIPELINE_SERVICE_CLIENT_SECRETS_MANAGER_LOADER:-"noop"}`
- `AIRFLOW_USERNAME=${AIRFLOW_USERNAME:-a2a}`
- `AIRFLOW_PASSWORD=${AIRFLOW_PASSWORD:-a2a}`
- `AIRFLOW_TIMEOUT=${AIRFLOW_TIMEOUT:-10}`
- `AIRFLOW_TRUST_STORE_PATH=${AIRFLOW_TRUST_STORE_PATH:-""}`
- `AIRFLOW_TRUST_STORE_PASSWORD=${AIRFLOW_TRUST_STORE_PASSWORD:-""}`
- `FERNET_KEY=${FERNET_KEY:-jJ/9sz0g0OHxsfxOoSfdFdmk3ysNmPRnH3TUAbz3IHA=}`
- `SECRET_MANAGER=${SECRET_MANAGER:-db}`
- `OM_SM_REGION=${OM_SM_REGION:-""}`
- `OM_SM_ACCESS_KEY_ID=${OM_SM_ACCESS_KEY_ID:-""}`
- `OM_SM_ACCESS_KEY=${OM_SM_ACCESS_KEY:-""}`
- `OM_EMAIL_ENTITY=${OM_EMAIL_ENTITY:-"OpenMetadata"}`
- `OM_SUPPORT_URL=${OM_SUPPORT_URL:-"https://slack.open-metadata.org"}`
- `AUTHORIZER_ENABLE_SMTP=${AUTHORIZER_ENABLE_SMTP:-false}`
- `OPENMETADATA_SERVER_URL=${OPENMETADATA_SERVER_URL:-""}`
- `OPENMETADATA_SMTP_SENDER_MAIL=${OPENMETADATA_SMTP_SENDER_MAIL:-""}`
- `SMTP_SERVER_ENDPOINT=${SMTP_SERVER_ENDPOINT:-""}`
- `SMTP_SERVER_PORT=${SMTP_SERVER_PORT:-""}`
- `SMTP_SERVER_USERNAME=${SMTP_SERVER_USERNAME:-""}`
- `SMTP_SERVER_PWD=${SMTP_SERVER_PWD:-""}`
- `SMTP_SERVER_STRATEGY=${SMTP_SERVER_STRATEGY:-"SMTP_TLS"}`
- `OPENMETADATA_HEAP_OPTS=${OPENMETADATA_HEAP_OPTS:--Xmx1G -Xms1G}`
- `MASK_PASSWORDS_API=${MASK_PASSWORDS_API:-false}`
- `WEB_CONF_URI_PATH=${WEB_CONF_URI_PATH:-"/api"}`
- `WEB_CONF_HSTS_ENABLED=${WEB_CONF_HSTS_ENABLED:-false}`
- `WEB_CONF_HSTS_MAX_AGE=${WEB_CONF_HSTS_MAX_AGE:-"365 days"}`
- `WEB_CONF_HSTS_INCLUDE_SUBDOMAINS=${WEB_CONF_HSTS_INCLUDE_SUBDOMAINS:-"true"}`
- `WEB_CONF_HSTS_PRELOAD=${WEB_CONF_HSTS_PRELOAD:-"true"}`
- `WEB_CONF_FRAME_OPTION_ENABLED=${WEB_CONF_FRAME_OPTION_ENABLED:-false}`
- `WEB_CONF_FRAME_OPTION=${WEB_CONF_FRAME_OPTION:-"SAMEORIGIN"}`
- `WEB_CONF_FRAME_ORIGIN=${WEB_CONF_FRAME_ORIGIN:-""}`
- `WEB_CONF_CONTENT_TYPE_OPTIONS_ENABLED=${WEB_CONF_CONTENT_TYPE_OPTIONS_ENABLED:-false}`
- `WEB_CONF_XSS_PROTECTION_ENABLED=${WEB_CONF_XSS_PROTECTION_ENABLED:-false}`
- `WEB_CONF_XSS_PROTECTION_ON=${WEB_CONF_XSS_PROTECTION_ON:-true}`
- `WEB_CONF_XSS_PROTECTION_BLOCK=${WEB_CONF_XSS_PROTECTION_BLOCK:-true}`
- `WEB_CONF_XSS_CSP_ENABLED=${WEB_CONF_XSS_CSP_ENABLED:-false}`
- `WEB_CONF_XSS_CSP_POLICY=${WEB_CONF_XSS_CSP_POLICY:-"default-src 'self'"}`
- `WEB_CONF_XSS_CSP_REPORT_ONLY_POLICY=${WEB_CONF_XSS_CSP_REPORT_ONLY_POLICY:-""}`
- `WEB_CONF_CACHE_CONTROL=${WEB_CONF_CACHE_CONTROL:-""}`
- `WEB_CONF_PRAGMA=${WEB_CONF_PRAGMA:-""}`
- `JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=/opt/om-trust/om-truststore.p12 -Djavax.net.ssl.trustStorePassword=changeit -Djavax.net.ssl.trustStoreType=PKCS12`


### `mysql`

**Image:** `docker.getcollate.io/openmetadata/db:1.9.12`
**Container name:** `mysql`

**Ports:**

- `3306:3306`

**Volumes:**

- `mysql_data:/var/lib/mysql:z`

**Networks:**

- `osss-net`

**Environment:**

- `MYSQL_ROOT_PASSWORD=password`
- `MYSQL_DATABASE=openmetadata`
- `MYSQL_USER=openmetadata_user`
- `MYSQL_PASSWORD=openmetadata_password`

**Command:**

```bash
--sort_buffer_size=10M
```


### `om-elasticsearch`

**Image:** `docker.elastic.co/elasticsearch/elasticsearch:8.11.4`
**Container name:** `om-elasticsearch`

**Ports:**

- `9201:9200`
- `9301:9300`

**Volumes:**

- `om-es-data:/usr/share/elasticsearch/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `discovery.type=single-node`
- `ES_JAVA_OPTS=-Xms1024m -Xmx1024m`
- `xpack.security.enabled=false`


### `ingestion`

**Image:** `docker.getcollate.io/openmetadata/ingestion:1.9.12`
**Container name:** `openmetadata-ingestion`

**Ports:**

- `8082:8080`

**Volumes:**

- `ingestion-volume-dag-airflow:/opt/airflow/dag_generated_configs:z`
- `ingestion-volume-dags:/opt/airflow/dags:z`
- `ingestion-volume-tmp:/tmp:z`

**Depends on:**

- `om-elasticsearch`
- `mysql`
- `openmetadata-server`

**Networks:**

- `osss-net`

**Environment:**

- `AIRFLOW__API__AUTH_BACKENDS=airflow.api.auth.backend.basic_auth,airflow.api.auth.backend.session`
- `AIRFLOW__CORE__EXECUTOR=LocalExecutor`
- `AIRFLOW__OPENMETADATA_AIRFLOW_APIS__DAG_GENERATED_CONFIGS=/opt/airflow/dag_generated_configs`
- `DB_HOST=${AIRFLOW_DB_HOST:-mysql}`
- `DB_PORT=${AIRFLOW_DB_PORT:-3306}`
- `AIRFLOW_DB=${AIRFLOW_DB:-airflow_db}`
- `DB_SCHEME=${AIRFLOW_DB_SCHEME:-mysql+mysqldb}`
- `DB_USER=${AIRFLOW_DB_USER:-airflow_user}`
- `DB_PASSWORD=${AIRFLOW_DB_PASSWORD:-airflow_pass}`
- `DB_PROPERTIES=${AIRFLOW_DB_PROPERTIES:-}`

**Command:**

```bash
/opt/airflow/ingestion_dependency.sh
```


### `qdrant`

**Build context:** `.`
**Dockerfile:** `docker/qdrant/Dockerfile`
**Container name:** `qdrant`

**Ports:**

- `6333:6333`

**Volumes:**

- `qdrant_data:/qdrant/storage:z`

**Networks:**

- `osss-net`


### `minio`

**Image:** `minio/minio:latest`
**Container name:** `minio`

**Ports:**

- `9000:9000`
- `9001:9001`

**Volumes:**

- `minio_data:/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `MINIO_ROOT_USER=${AI_MINIO_ROOT_USER}`
- `MINIO_ROOT_PASSWORD=${AI_MINIO_ROOT_PASSWORD}`

**Command:**

```bash
server /data --console-address ":9001"
```


### `ai-redis`

**Image:** `redis:7`
**Container name:** `ai-redis`

**Ports:**

- `6382:6379`

**Volumes:**

- `ai_redis_data:/data:z`

**Networks:**

- `osss-net`

**Command:**

```bash
redis-server --save  --appendonly no
```


### `ai-postgres`

**Image:** `postgres:15`
**Container name:** `ai-postgres`

**Ports:**

- `5436:5432`

**Volumes:**

- `ai_pg_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_DB=${AI_POSTGRES_DB}`
- `POSTGRES_USER=${AI_POSTGRES_USER}`
- `POSTGRES_PASSWORD=${AI_POSTGRES_PASSWORD}`


### `dvc`

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


### `rasa-mentor`

**Image:** `rasa/rasa:3.6.20`
**Container name:** `rasa-mentor`

**Ports:**

- `5005:5005`

**Volumes:**

- `./rasa:/app`

**Networks:**

- `osss-net`

**Environment:**

- `TZ=America/Chicago`
- `RASA_TELEMETRY_ENABLED=false`
- `SQLALCHEMY_SILENCE_UBER_WARNING=1`
- `SANIC_REQUEST_MAX_SIZE=104857600`
- `SANIC_REQUEST_MAX_HEADER_SIZE=65536`

**Command:**

```bash
bash -lc "set -euo pipefail;
    mkdir -p models;
    exec rasa run --enable-api --cors '*' --model models/current.tar.gz --port 5005 --debug"

```


### `a2a`

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


### `metagpt`

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


### `a2a-agent`

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


### `zulip`

**Build context:** `.`
**Dockerfile:** `docker/zulip/Dockerfile`
**Container name:** `zulip`

**Ports:**

- `8111:80`

**Volumes:**

- `./zulip/zulip-data:/data:rw,z`
- `./docker/zulip/entrypoint.sh:/sbin/entrypoint.sh:ro,z`
- `./docker/zulip/certbot-deploy-hook:/sbin/certbot-deploy-hook:ro,z`
- `./docker/zulip/settings.py:/etc/zulip/settings.py:z`

**Depends on:**

- `zulip-db`
- `zulip-memcached`
- `zulip-redis`

**Networks:**

- `osss-net`

**Environment:**

- `DB_HOST=zulip-db`
- `DB_USER=zulip`
- `DB_PASS=zulip`
- `DB_NAME=zulip`
- `SECRETS_postgres_password=zulip`
- `SETTING_MEMCACHED_LOCATION=zulip-memcached:11211`
- `SETTING_REDIS_HOST=zulip-redis`
- `SETTING_REDIS_PORT=6379`
- `SECRETS_redis_password=super-secret-redis-pass`
- `SETTING_RATE_LIMITING=False`
- `SETTING_ZULIP_ADMINISTRATOR=admin@localhost`
- `SETTING_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`
- `DISABLE_HTTPS=true`
- `SSL_CERTIFICATE_GENERATION=self-signed`
- `SETTING_EXTERNAL_HOST=localhost:8111`
- `SETTING_EXTERNAL_URI_SCHEME=http://`
- `SETTING_EXTERNAL_PORT=8111`
- `SECRETS_secret_key=dev-change-me-secret`
- `SETTING_RABBITMQ_HOST=zulip-rabbitmq`
- `SECRETS_rabbitmq_password=zulip`
- `SETTING_EMAIL_HOST=`


### `zulip-db`

**Image:** `zulip/zulip-postgresql:14`
**Container name:** `zulip-db`

**Ports:**

- `5438:5432`

**Volumes:**

- `zulip_postgres_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_DB=zulip`
- `POSTGRES_USER=zulip`
- `POSTGRES_PASSWORD=zulip`


### `zulip-memcached`

**Image:** `memcached:1.6-alpine`
**Container name:** `zulip-memcached`

**Networks:**

- `osss-net`

**Command:**

```bash
memcached -m 256
```


### `zulip-redis`

**Image:** `redis:7-alpine`
**Container name:** `zulip-redis`

**Ports:**

- `6383:6379`

**Volumes:**

- `zulip_redis_data:/data:z`

**Networks:**

- `osss-net`

**Command:**

```bash
redis-server --requirepass super-secret-redis-pass --appendonly yes
```


### `zulip-rabbitmq`

**Image:** `rabbitmq:3.13-management-alpine`
**Container name:** `zulip-rabbitmq`

**Ports:**

- `15672:15672`
- `5672:5672`

**Volumes:**

- `./zulip/rabbitmq/data:/var/lib/rabbitmq`
- `./zulip/rabbitmq/logs:/var/log/rabbitmq`

**Networks:**

- `osss-net`

**Environment:**

- `RABBITMQ_DEFAULT_USER=zulip`
- `RABBITMQ_DEFAULT_PASS=zulip`
- `RABBITMQ_LOGS=/var/log/rabbitmq/rabbit.log`
- `RABBITMQ_SASL_LOGS=/var/log/rabbitmq/rabbit-sasl.log`


### `taiga-db`

**Image:** `postgres:16`
**Container name:** `taiga-db`

**Ports:**

- `5439:5432`

**Volumes:**

- `taiga_db_data:/var/lib/postgresql/data:z`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_DB=taiga`
- `POSTGRES_USER=${TAIGA_DB_USER:-taiga}`
- `POSTGRES_PASSWORD=${TAIGA_DB_PASSWORD:-taiga}`


### `taiga-rabbitmq`

**Image:** `rabbitmq:3.13-management`
**Container name:** `taiga-rabbitmq`

**Ports:**

- `8161:15672`
- `8162:5672`

**Volumes:**

- `taiga_rabbitmq_data:/var/lib/rabbitmq:z`

**Networks:**

- `osss-net`

**Environment:**

- `RABBITMQ_DEFAULT_USER=${TAIGA_RABBITMQ_USER:-taiga}`
- `RABBITMQ_DEFAULT_PASS=${TAIGA_RABBITMQ_PASS:-taiga}`
- `RABBITMQ_DEFAULT_VHOST=${TAIGA_RABBITMQ_VHOST:-taiga}`
- `RABBITMQ_ERLANG_COOKIE=${TAIGA_RABBITMQ_ERLANG_COOKIE:-changeme-cookie}`


### `taiga-back`

**Image:** `taigaio/taiga-back:latest`
**Container name:** `taiga-back`

**Volumes:**

- `taiga_static_data:/taiga-back/static`
- `taiga_media_data:/taiga-back/media`

**Depends on:**

- `taiga-db`
- `taiga-rabbitmq`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_HOST=taiga-db`
- `POSTGRES_DB=taiga`
- `POSTGRES_USER=${TAIGA_DB_USER:-taiga}`
- `POSTGRES_PASSWORD=${TAIGA_DB_PASSWORD:-taiga}`
- `RABBITMQ_HOST=taiga-rabbitmq`
- `RABBITMQ_USER=${TAIGA_RABBITMQ_USER:-taiga}`
- `RABBITMQ_PASSWORD=${TAIGA_RABBITMQ_PASS:-taiga}`
- `TAIGA_SECRET_KEY=${TAIGA_SECRET_KEY:-changeme-super-secret}`


### `taiga-async`

**Image:** `taigaio/taiga-back:latest`
**Container name:** `taiga-async`

**Volumes:**

- `taiga_static_data:/taiga-back/static`
- `taiga_media_data:/taiga-back/media`

**Depends on:**

- `taiga-db`
- `taiga-rabbitmq`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_HOST=taiga-db`
- `POSTGRES_DB=taiga`
- `POSTGRES_USER=${TAIGA_DB_USER:-taiga}`
- `POSTGRES_PASSWORD=${TAIGA_DB_PASSWORD:-taiga}`
- `RABBITMQ_HOST=taiga-rabbitmq`
- `RABBITMQ_USER=${TAIGA_RABBITMQ_USER:-taiga}`
- `RABBITMQ_PASSWORD=${TAIGA_RABBITMQ_PASS:-taiga}`

**Command:**

```bash
/taiga-back/docker/async_entrypoint.sh
```


### `taiga-events`

**Image:** `taigaio/taiga-events:latest`
**Container name:** `taiga-events`

**Ports:**

- `8188:8888`

**Depends on:**

- `taiga-rabbitmq`

**Networks:**

- `osss-net`

**Environment:**

- `RABBITMQ_USER=${TAIGA_RABBITMQ_USER:-taiga}`
- `RABBITMQ_PASSWORD=${TAIGA_RABBITMQ_PASS:-taiga}`
- `RABBITMQ_HOST=taiga-rabbitmq`
- `TAIGA_SECRET_KEY=${TAIGA_SECRET_KEY:-changeme-super-secret}`


### `taiga-protected`

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


### `taiga-front`

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


### `taiga-gateway`

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


### `taiga-init-admin`

**Image:** `taigaio/taiga-back:latest`
**Container name:** `taiga-init-admin`

**Depends on:**

- `taiga-db`
- `taiga-rabbitmq`

**Networks:**

- `osss-net`

**Environment:**

- `POSTGRES_HOST=taiga-db`
- `POSTGRES_DB=taiga`
- `POSTGRES_USER=${TAIGA_DB_USER:-taiga}`
- `POSTGRES_PASSWORD=${TAIGA_DB_PASSWORD:-taiga}`
- `RABBITMQ_HOST=taiga-rabbitmq`
- `RABBITMQ_USER=${TAIGA_RABBITMQ_USER:-taiga}`
- `RABBITMQ_PASSWORD=${TAIGA_RABBITMQ_PASS:-taiga}`
- `TAIGA_SECRET_KEY=${TAIGA_SECRET_KEY:-changeme-super-secret}`
- `DJANGO_SUPERUSER_USERNAME=admin`
- `DJANGO_SUPERUSER_EMAIL=admin@example.com`
- `DJANGO_SUPERUSER_PASSWORD=admin`

**Command:**

```bash
cd /taiga-back && /opt/venv/bin/python manage.py createsuperuser --noinput || true

```

