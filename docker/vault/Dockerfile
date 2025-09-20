# ---- Stage 1: fetch tools ---------------------------------------
FROM alpine:3.20 AS tools
RUN apk add --no-cache curl jq ca-certificates

# ---- Stage 2: extend Vault with the tools -----------------------
FROM hashicorp/vault:1.20.3

# Become root just for file copy; we'll drop back to 'vault'
USER root

# Copy the binaries and certs into the Vault image
# (choose a dir on PATH; /usr/local/bin is a safe bet)
COPY --from=tools /usr/bin/curl /usr/local/bin/curl
COPY --from=tools /usr/bin/jq   /usr/local/bin/jq
COPY --from=tools /etc/ssl/certs/ /etc/ssl/certs/

# Permissions (sometimes not needed, but safe)
RUN chmod +x /usr/local/bin/curl /usr/local/bin/jq

# Back to the default user used by the upstream image
USER vault
