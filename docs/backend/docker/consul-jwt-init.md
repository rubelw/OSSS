# `consul-jwt-init` service

This page documents the configuration for the `consul-jwt-init` service from `docker-compose.yml`.

**Image:** `hashicorp/consul:1.18`
**Container name:** `consul-jwt-init`

**Volumes:**

- `./config_files/consul/jwt/jwt.json:/cfg/jwt.json:ro,z`
- `./config_files/consul/init-jwt.sh:/cfg/init-jwt.sh:ro,z`

**Depends on:**

- `consul`

**Networks:**

- `osss-net`

**Environment:**

- `CONSUL_HTTP_ADDR=http://consul:8500`
- `CONSUL_HTTP_TOKEN=${CONSUL_HTTP_TOKEN}`

**Command:**

```bash
/cfg/init-jwt.sh
```
