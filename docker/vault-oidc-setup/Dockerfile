# docker/vault-oidc-setup/Dockerfile
FROM hashicorp/vault:1.20.3

USER root
RUN set -eux; \
  if command -v apk >/dev/null 2>&1; then \
    apk add --no-cache curl jq ca-certificates; \
  elif command -v microdnf >/dev/null 2>&1; then \
    microdnf install -y curl jq ca-certificates && microdnf clean all; \
  elif command -v yum >/dev/null 2>&1; then \
    yum install -y curl jq ca-certificates && yum clean all; \
  elif command -v apt-get >/dev/null 2>&1; then \
    apt-get update && DEBIAN_FRONTEND=noninteractive \
      apt-get install -y --no-install-recommends curl jq ca-certificates && \
    rm -rf /var/lib/apt/lists/*; \
  else \
    echo "No supported package manager found in base image"; exit 1; \
  fi

COPY scripts/vault-oidc-setup.sh /setup.sh
RUN chmod +x /setup.sh
USER vault
ENTRYPOINT ["/bin/sh","-lc","/setup.sh"]

