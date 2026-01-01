# `keycloak` service

This page documents the configuration for the `keycloak` service from `docker-compose.yml`.

**Build context:** `.`
**Dockerfile:** `docker/keycloak/Dockerfile`
**Container name:** `keycloak`

**Ports:**

- `8443:8443`

**Volumes:**

- `./realm-export.json:/opt/keycloak/data/import/10-OSSS.json:ro,z`
- `./docker/keycloak/quarkus.properties:/opt/keycloak/conf/quarkus.properties:ro,z`
- `./config_files/keycloak/secrets/keycloak:/opt/keycloak/conf/tls:ro,z`

**Depends on:**

- `kc_postgres`

**Networks:**

- `osss-net`

**Environment:**

- `KC_HTTP_MANAGEMENT_PORT=9000`
- `KC_HTTP_MANAGEMENT_SCHEME=http`
- `KC_HTTP_PORT=8080`
- `KC_DB=${KC_DB}`
- `KC_DB_URL=jdbc:postgresql://${KC_DB_HOST}:${KC_DB_PORT}/${KC_DB_NAME}`
- `KC_DB_USERNAME=${KC_DB_USERNAME}`
- `KC_DB_PASSWORD=${KC_DB_PASSWORD}`
- `KEYCLOAK_ADMIN=${KEYCLOAK_ADMIN}`
- `KEYCLOAK_ADMIN_PASSWORD=${KEYCLOAK_ADMIN_PASSWORD}`
- `KC_HTTPS_CERTIFICATE_FILE=/opt/keycloak/conf/tls/server.crt`
- `KC_HTTPS_CERTIFICATE_KEY_FILE=/opt/keycloak/conf/tls/server.key`
- `KC_HEALTH_ENABLED=true`
- `KC_HOSTNAME=${KC_HOSTNAME}`
- `KC_DB_SCHEMA=${KC_DB_SCHEMA}`
- `QUARKUS_HIBERNATE_ORM_PERSISTENCE_XML_IGNORE=true`
- `JAVA_OPTS=${JAVA_OPTS}`
- `KC_DB_POOL_INITIAL_SIZE=20`
- `KC_DB_POOL_MIN_SIZE=20`
- `KC_DB_POOL_MAX_SIZE=50`
- `KC_LOG_LEVEL=${KC_LOG_LEVEL}`
- `KC_PROXY=${KC_PROXY}`
- `KC_HTTP_ENABLED=${KC_HTTP_ENABLED}`
- `KC_HOSTNAME_STRICT=${KC_HOSTNAME_STRICT}`
- `ADMIN_USER=${KEYCLOAK_ADMIN}`
- `ADMIN_PWD=${KEYCLOAK_ADMIN_PASSWORD}`
- `KC_URL=${KC_URL}`
- `QUARKUS_MANAGEMENT_HOST=0.0.0.0`
- `QUARKUS_MANAGEMENT_ENABLED=true`
- `QUARKUS_MANAGEMENT_PORT=9000`
- `QUARKUS_HTTP_HOST=0.0.0.0`
