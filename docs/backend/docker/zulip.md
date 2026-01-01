# `zulip` service

This page documents the configuration for the `zulip` service from `docker-compose.yml`.

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
