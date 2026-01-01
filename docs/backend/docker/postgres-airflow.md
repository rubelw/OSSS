# `postgres-airflow` service

This page documents the configuration for the `postgres-airflow` service from `docker-compose.yml`.

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
