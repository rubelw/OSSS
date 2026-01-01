# `airflow-scheduler` service

This page documents the configuration for the `airflow-scheduler` service from `docker-compose.yml`.

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
