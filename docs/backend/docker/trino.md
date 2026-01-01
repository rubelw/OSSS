# `trino` service

This page documents the configuration for the `trino` service from `docker-compose.yml`.

**Image:** `trinodb/trino:latest`
**Container name:** `trino`

**Ports:**

- `8444:8443`

**Volumes:**

- `./config_files/trino_data:/var/trino:z`
- `./config_files/trino/etc:/etc/trino:ro,z`
- `./config_files/trino/opt/osss-truststore.p12:/opt/trust/osss-truststore.p12:ro,z`

**Networks:**

- `osss-net`

**Environment:**

- `JAVA_TOOL_OPTIONS=-Djavax.net.ssl.trustStore=/opt/trust/osss-truststore.p12 -Djavax.net.ssl.trustStorePassword=changeit -Djavax.net.ssl.trustStoreType=PKCS12
`
