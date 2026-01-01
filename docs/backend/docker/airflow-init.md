# `airflow-init` service

This page documents the configuration for the `airflow-init` service from `docker-compose.yml`.

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
