# `superset` service

This page documents the configuration for the `superset` service from `docker-compose.yml`.

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
