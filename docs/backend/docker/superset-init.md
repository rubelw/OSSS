# `superset-init` service

This page documents the configuration for the `superset-init` service from `docker-compose.yml`.

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
