# /opt/keycloak/healthcheck.sh
#!/bin/sh
set -eu

# Try readiness on either mgmt (9000) *or* app (8080), preferring localhost.
ready() {
  curl -fsS http://127.0.0.1:9000/health/ready >/dev/null 2>&1 \
  || curl -fsS https://127.0.0.1:8443/health/ready >/dev/null 2>&1
}

# Wait up to ~2 minutes for readiness
i=0
until ready; do
  i=$((i+1))
  [ "$i" -ge 60 ] && exit 1
  sleep 2
done

# Optional: only require the realm if you *want* the container to be Healthy
# *after* the import has completed. Otherwise, comment this block out.
if [ "${CHECK_REALM:-1}" = "1" ]; then
  # Build a Host header that matches your configured KC_HOSTNAME (if any)
  HOST="$(printf %s "${KC_HOSTNAME_URL:-${KC_HOSTNAME:-localhost}}" \
        | sed -E 's~^https?://~~; s~/.*$~~')"
  curl -fsS -H "Host: ${HOST}" \
    https://127.0.0.1:8443/realms/OSSS/.well-known/openid-configuration >/dev/null
fi

exit 0
