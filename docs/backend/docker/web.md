# `web` service

This page documents the configuration for the `web` service from `docker-compose.yml`.

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
