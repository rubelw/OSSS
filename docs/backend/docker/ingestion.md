# `ingestion` service

This page documents the configuration for the `ingestion` service from `docker-compose.yml`.

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
