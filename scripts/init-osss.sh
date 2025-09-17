#!/usr/bin/env sh
set -e

# ---------------------------
# Postgres bootstrap (unchanged)
# ---------------------------
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
DECLARE
  v_user text := current_setting('server_version'); -- dummy read to ensure DO works
BEGIN
  -- Ensure role
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${OSSS_DB_USER}') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '${OSSS_DB_USER}', '${OSSS_DB_PASSWORD}');
  ELSE
    EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', '${OSSS_DB_USER}', '${OSSS_DB_PASSWORD}');
  END IF;
END
\$\$;
SQL

# Create DB (will error if it already exists; harmless on first init)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE DATABASE "${OSSS_DB_NAME}" OWNER "${OSSS_DB_USER}";
SQL

# ---------------------------
# Keycloak partial import (only if realm exists)
# ---------------------------

log() { printf '%s %s\n' "[$(date '+%Y-%m-%dT%H:%M:%S%z')]" "$*" >&2; }

KC_URL="${KEYCLOAK_URL:-http://keycloak:8080}"
REALM="${KEYCLOAK_REALM:-OSSS}"
ADMIN="${KEYCLOAK_ADMIN:-admin}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-admin}"
POLICY="${KEYCLOAK_IMPORT_POLICY:-OVERWRITE}"  # OVERWRITE|SKIP|FAIL

# Where to look for files like *-OSSS-roles.json, *-OSSS-clients.json, etc.
IMPORT_DIRS="${KEYCLOAK_IMPORT_DIRS:-/opt/keycloak/data/import:/opt/keycloak/import:/seed/keycloak:/docker-entrypoint-initdb.d}"

find_one() {
  pattern="$1"
  OLDIFS=$IFS; IFS=":"
  for d in $IMPORT_DIRS; do
    [ -d "$d" ] || continue
    # shellcheck disable=SC2231
    for f in $d/$pattern; do
      [ -f "$f" ] && { IFS=$OLDIFS; echo "$f"; return 0; }
    done
  done
  IFS=$OLDIFS
  return 1
}

REALM_FILE="$(find_one "*-${REALM}-realm.json" || true)"
ROLES_FILE="$(find_one "*-${REALM}-roles.json" || true)"
CLIENTS_FILE="$(find_one "*-${REALM}-clients.json" || true)"
GROUPS_FILE="$(find_one "*-${REALM}-groups.json" || true)"
USERS_FILE="$(find_one "*-${REALM}-users.json" || true)"

wait_for_kc() {
  url="$KC_URL/realms/master/.well-known/openid-configuration"
  end=$(( $(date +%s) + ${KC_WAIT_SECS:-60} ))
  while [ "$(date +%s)" -lt "$end" ]; do
    if curl -fsS "$url" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  return 1
}

get_admin_token() {
  curl -fsS -X POST "$KC_URL/realms/master/protocol/openid-connect/token" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode "grant_type=password" \
    --data-urlencode "client_id=admin-cli" \
    --data-urlencode "username=$ADMIN" \
    --data-urlencode "password=$ADMIN_PASS" \
  | awk -F'"' '/access_token/ {getline; print $4}' 2>/dev/null
}

realm_exists() {
  tok="$1"
  curl -fsS -H "Authorization: Bearer $tok" \
    "$KC_URL/admin/realms/$REALM" >/dev/null 2>&1
}

# Inject ifResourceExists into a top-level JSON object without jq
# Assumes the file is a single JSON object {...}
inject_policy() {
  file="$1"
  policy="$2"
  # strip leading BOM and whitespace, remove first '{' and last '}', then rewrap with ifResourceExists
  content=$(cat "$file" | sed '1s/^\xEF\xBB\xBF//' )
  body=$(printf '{"ifResourceExists":"%s",%s}' "$policy" \
        "$(printf '%s' "$content" | sed -e '1s/^[[:space:]]*{//' -e '$s/}[[:space:]]*$//')")
  printf '%s' "$body"
}

partial_import() {
  file="$1"
  kind="$2"
  [ -f "$file" ] || return 0
  body="$(inject_policy "$file" "$POLICY")"
  curl -fsS -X POST "$KC_URL/admin/realms/$REALM/partialImport" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data-binary "$body" >/dev/null
  log "Keycloak partial import (${kind}) from $(basename "$file") with policy=${POLICY}"
}

# Do the thing
if wait_for_kc; then
  TOKEN="$(get_admin_token || true)"
  if [ -z "$TOKEN" ]; then
    log "Keycloak admin token unavailable; skipping KC import."
    exit 0
  fi

  if realm_exists "$TOKEN"; then
    log "Realm '$REALM' exists — applying partial imports."
    # NOTE: realm file is typically for creation; we skip creating realm here
    # and import fragments (roles/clients/groups/users).
    [ -n "$CLIENTS_FILE" ] && partial_import "$CLIENTS_FILE" "clients"
    [ -n "$ROLES_FILE" ]   && partial_import "$ROLES_FILE"   "roles"
    [ -n "$GROUPS_FILE" ]  && partial_import "$GROUPS_FILE"  "groups"
    [ -n "$USERS_FILE" ]   && partial_import "$USERS_FILE"   "users"
    log "Keycloak partial import completed."
  else
    log "Realm '$REALM' not found — skipping KC import."
  fi
else
  log "Keycloak not reachable — skipping KC import."
fi
