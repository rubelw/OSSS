# /opt/keycloak/healthcheck.sh
#!/bin/sh
set -eu

# ---- Tunables (env overrides) -----------------------------------------------
MAX_TRIES="${HEALTHCHECK_MAX_TRIES:-90}"      # ~3 minutes @ 2s sleep
SLEEP_SEC="${HEALTHCHECK_SLEEP_SEC:-2}"
CHECK_REALM="${CHECK_REALM:-1}"               # 1=require realm endpoint; 0=skip
REALM_NAME="${HEALTHCHECK_REALM:-OSSS}"

# TLS verification behavior:
# - If HEALTHCHECK_CACERT points to a readable file, use --cacert
# - Else if HEALTHCHECK_INSECURE=1 (default), use -k
# - Else do strict verification (may fail on self-signed)
CACERT_OPT=""
if [ -n "${HEALTHCHECK_CACERT:-}" ] && [ -r "${HEALTHCHECK_CACERT}" ]; then
  CACERT_OPT="--cacert ${HEALTHCHECK_CACERT}"
elif [ "${HEALTHCHECK_INSECURE:-1}" = "1" ]; then
  CACERT_OPT="-k"
fi

# ---- Derive ports/host -------------------------------------------------------
HTTP_PORT="${KC_HTTP_PORT:-8080}"
HTTPS_PORT="${KC_HTTPS_PORT:-8443}"
MGMT_PORT="${KC_MANAGEMENT_HTTP_PORT:-9000}"  # default mgmt port in Quarkus dist

# Build a hostname Keycloak expects. Accept KC_HOSTNAME_URL or KC_HOSTNAME.
HOST_RAW="${KC_HOSTNAME_URL:-${KC_HOSTNAME:-localhost}}"
# Strip scheme & path to get a bare host
HOST="$(printf %s "$HOST_RAW" | sed -E 's~^https?://~~; s~/.*$~~')"

CURL="curl -fsS --max-time 5"

http_ok() {
  # $1 = URL
  $CURL "$1" >/dev/null 2>&1
}

https_ok() {
  # Use Host header + --resolve so requests hit 127.0.0.1 with the expected host
  # $1 = path (starting with /), e.g. "/health/ready"
  # shellcheck disable=SC2086
  $CURL $CACERT_OPT \
    --resolve "${HOST}:${HTTPS_PORT}:127.0.0.1" \
    -H "Host: ${HOST}" \
    "https://${HOST}:${HTTPS_PORT}$1" >/dev/null 2>&1
}

ready_once() {
  # Prefer management port if health is enabled there
  http_ok  "http://127.0.0.1:${MGMT_PORT}/health/ready"
}

# ---- Wait for readiness ------------------------------------------------------
i=0
until ready_once; do
  i=$((i+1))
  [ "$i" -ge "$MAX_TRIES" ] && exit 1
  sleep "$SLEEP_SEC"
done

exit 0