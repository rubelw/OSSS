# `vault` service

This page documents the configuration for the `vault` service from `docker-compose.yml`.

**Image:** `hashicorp/vault:1.20.3`
**Container name:** `vault`

**Ports:**

- `8200:8200`

**Networks:**

- `osss-net`

**Environment:**

- `VAULT_DEV_ROOT_TOKEN_ID=${VAULT_DEV_ROOT_TOKEN_ID}`
- `VAULT_DEV_LISTEN_ADDRESS=${VAULT_DEV_LISTEN_ADDRESS}`
- `VAULT_UI=${VAULT_UI}`
- `VAULT_API_ADDR=${VAULT_API_ADDR}`

**Command:**

```bash
server -dev -dev-root-token-id=root -dev-listen-address=0.0.0.0:8200
```
