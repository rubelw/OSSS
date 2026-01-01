# `airflow-webserver` service

This page documents the configuration for the `airflow-webserver` service from `docker-compose.yml`.

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
