#!/usr/bin/env bash
set -Eeuo pipefail
[[ "${DEBUG:-0}" == "1" ]] && set -x
PS4='+ [${BASH_SOURCE##*/}:${LINENO}] '

# --- Config (env-overridable) ---
KCADM="${KCADM:-/opt/keycloak/bin/kcadm.sh}"
IMPORT_FILE="${IMPORT_FILE:-/import/realm-export.json}"
REALM="${KEYCLOAK_REALM:-}"
HOST="${KC_HOST:-keycloak}"
PORT="${KC_PORT:-8080}"
REL_PATH="${KC_HTTP_RELATIVE_PATH:-}"   # e.g. "/auth" or empty

# Build server URL including relative path if provided
if [[ -n "$REL_PATH" ]]; then
  REL_PATH="/${REL_PATH#/}"    # ensure leading slash
  REL_PATH="${REL_PATH%/}"     # strip trailing slash
fi
KC="${KC:-http://${HOST}:${PORT}${REL_PATH}}"

sleep "${START_DELAY_SEC:-15}"

echo "Using Keycloak server: ${KC}"
echo "Using kcadm: ${KCADM}"
echo "Import file: ${IMPORT_FILE}"

if [[ ! -r "$IMPORT_FILE" ]]; then
  echo "FATAL: Import file not readable: ${IMPORT_FILE}" >&2
  exit 1
fi

echo "Waiting for Keycloak to accept admin credentials…"
for i in $(seq 1 120); do
  if "$KCADM" config credentials \
        --server "$KC" \
        --realm master \
        --user "${KEYCLOAK_ADMIN:?missing}" \
        --password "${KEYCLOAK_ADMIN_PASSWORD:?missing}" \
        >/dev/stdout 2>/dev/stderr; then
    echo "Keycloak is ready."
    break
  fi
  echo "[$i] Still waiting…"
  sleep 2
  if [[ "$i" -eq 120 ]]; then
    echo "FATAL: Timed out waiting for Keycloak admin login." >&2
    exit 1
  fi
done

# Resolve realm name
if [[ -z "$REALM" ]]; then
  if command -v jq >/dev/null 2>&1 && [[ -s "$IMPORT_FILE" ]]; then
    REALM="$(jq -r '.realm // .id // .name // empty' "$IMPORT_FILE")"
  fi
  REALM="${REALM:-OSSS}"
fi
echo "Target realm: ${REALM}"

# Always overwrite: delete existing realm if present
if "$KCADM" get "realms/${REALM}" >/dev/null 2>&1; then
  echo "Realm '${REALM}' exists; deleting before import."
  if ! "$KCADM" delete "realms/${REALM}"; then
    echo "WARNING: Failed to delete existing realm '${REALM}'" >&2
  fi
fi

# Create realm from file
echo "Importing realm from ${IMPORT_FILE}…"
if ! OUT=$("$KCADM" create realms -f "$IMPORT_FILE" 2>&1); then
  echo "FATAL: Import failed. kcadm output:" >&2
  echo "$OUT" >&2
  exit 1
fi
echo "Import complete. kcadm says:"
echo "$OUT"

# Sanity check the well-known endpoint
WELL_KNOWN="${KC%/}/realms/${REALM}/.well-known/openid-configuration"
if command -v curl >/dev/null 2>&1; then
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" "$WELL_KNOWN" || true)
  echo "Well-known endpoint: ${WELL_KNOWN} (HTTP ${HTTP})"
fi

# Keep container running for log inspection unless disabled
if [[ "${HOLD_OPEN:-1}" == "1" ]]; then
  echo "Importer finished; holding container open."
  tail -f /dev/null
else
  echo "Importer finished; exiting."
fi
