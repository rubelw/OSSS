# `consul` service

This page documents the configuration for the `consul` service from `docker-compose.yml`.

**Image:** `hashicorp/consul:1.18`
**Container name:** `consul`

**Ports:**

- `8500:8500`
- `8600:8600/tcp`
- `8600:8600/udp`

**Volumes:**

- `./config_files/consul_data:/consul/data:z`
- `./config_files/consul/config:/consul/config:rw,z`
- `./config_files/consul/jwt:/consul/jwt:rw,z`
- `./config_files/keycloak/secrets/ca/ca.crt:/usr/local/share/ca-certificates/keycloak-ca.crt:ro`

**Networks:**

- `osss-net`

**Environment:**

- `CONSUL_HTTP_TOKEN=${CONSUL_HTTP_TOKEN:-}`

**Command:**

```bash
/bin/sh -lc update-ca-certificates || true; exec consul agent -server -bootstrap-expect=1 -client=0.0.0.0 -ui -log-level=INFO -config-dir=/consul/config
```
