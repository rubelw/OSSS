# `vault-oidc-setup` service

This page documents the configuration for the `vault-oidc-setup` service from `docker-compose.yml`.

**Build context:** `.`
**Dockerfile:** `docker/vault-oidc-setup/Dockerfile`
**Container name:** `vault-oidc-setup`

**Volumes:**

- `./scripts/vault-oidc-setup.sh:/setup.sh:ro,z`
- `~/.vault-token:/root/.vault-token:ro,z`
- `./config_files/keycloak/secrets/ca/ca.crt:/etc/ssl/certs/keycloak-ca.crt:ro,z`

**Depends on:**

- `vault`

**Networks:**

- `osss-net`

**Environment:**

- `VERBOSE=1`
- `DEBUG=1`
- `VAULT_LOG_LEVEL=debug`
- `GODEBUG=http2debug=2`
- `VAULT_ADDR=${VAULT_ADDR}`
- `VAULT_TOKEN=${VAULT_TOKEN}`
- `OIDC_DISCOVERY_URL=${OIDC_DISCOVERY_URL}`
- `VAULT_OIDC_DISCOVERY_URL=${VAULT_OIDC_DISCOVERY_URL}`
- `VAULT_OIDC_CLIENT_ID=${VAULT_OIDC_CLIENT_ID}`
- `VAULT_OIDC_CLIENT_SECRET=${VAULT_OIDC_CLIENT_SECRET}`
- `VAULT_OIDC_ROLE=${VAULT_OIDC_ROLE}`
- `VAULT_TOKEN_FILE=/root/.vault-token`
- `OIDC_ADMIN_GROUP=/vault-a2a`
- `VAULT_UI_REDIRECT_1=http://127.0.0.1:8200/ui/vault/auth/oidc/oidc/callback`
- `VAULT_UI_REDIRECT_2=http://localhost:8200/ui/vault/auth/oidc/oidc/callback`
- `VAULT_UI_REDIRECT_3=http://vault:8200/ui/vault/auth/oidc/oidc/callback`
- `VAULT_CLI_REDIRECT_1=http://127.0.0.1:8250/oidc/callback`
- `VAULT_CLI_REDIRECT_2=http://localhost:8250/oidc/callback`
- `VAULT_CLI_REDIRECT_3=http://vault:8250/oidc/callback`
- `CURL_CA_BUNDLE=/etc/ssl/certs/keycloak-ca.crt`
- `SSL_CERT_FILE=/etc/ssl/certs/keycloak-ca.crt`
