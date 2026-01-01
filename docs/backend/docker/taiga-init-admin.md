# `taiga-init-admin` service

This page documents the configuration for the `taiga-init-admin` service from `docker-compose.yml`.

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
