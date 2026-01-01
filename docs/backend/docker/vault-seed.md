# `vault-seed` service

This page documents the configuration for the `vault-seed` service from `docker-compose.yml`.

**Image:** `alpine:3.20`
**Container name:** `vault-seed`

**Volumes:**

- `./scripts/seed-vault.sh:/usr/local/bin/seed-vault:ro,z`

**Depends on:**

- `vault`

**Networks:**

- `osss-net`

**Environment:**

- `VAULT_ADDR=http://vault:8200`
- `VAULT_TOKEN=${VAULT_TOKEN:-root}`
- `VAULT_KV_PATH=${VAULT_KV_PATH:-app}`
- `SEED_VAULT_TOKEN=${VAULT_TOKEN:-root}`
- `VERBOSE=1`
- `DEBUG=1`
