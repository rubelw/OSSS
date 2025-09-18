#!/usr/bin/env bash
# kc-verify.sh : verify OSSS realm + users, roles, groups via DB + Admin API

unset POSIXLY_CORRECT
set -Eeuo pipefail

REALM="${REALM:-OSSS}"
KC_URL="${KC_URL:-http://localhost:8080}"
TOKEN="${TOKEN:-}"
DEFAULT_MAX="${MAX:-50}"

echo "==== kc-verify starting ===="
echo "PGHOST=${PGHOST:-<unset>} PGPORT=${PGPORT:-<unset>} PGUSER=${PGUSER:-<unset>} PGDATABASE=${PGDATABASE:-<unset>}"
echo "KC_URL=$KC_URL REALM=$REALM"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }
}
need psql
need curl
need jq

if [[ -z "$TOKEN" ]]; then
  echo "TOKEN env var not set; cannot call Keycloak Admin API." >&2
  exit 1
fi

kc_get() {
  local path="$1"
  # use --fail-with-body so HTTP errors print the server response
  curl -sS --fail-with-body \
    -H "Authorization: Bearer $TOKEN" \
    -H "Accept: application/json" \
    "$KC_URL$path"
}

echo "==== Checking Postgres connection ===="
psql -lqt | cut -d '|' -f1 | tr -d ' ' | grep -x "${PGDATABASE:-}" >/dev/null && \
  echo "Database ${PGDATABASE:-<unset>} is reachable ✅" || \
  echo "WARNING: Database ${PGDATABASE:-<unset>} not listed (continuing)."

echo "==== realm table (id,name) ===="
psql -c "SELECT id, name FROM realm;" || echo "NOTE: could not query realm table."

echo "==== Checking for $REALM realm in DB ===="
realm_name=$(psql -t -A -c "SELECT name FROM realm WHERE name = '${REALM}'" 2>/dev/null || true)
echo "DB realm query result: '[$realm_name]'"
if [[ "$realm_name" != "$REALM" ]]; then
  echo "$REALM realm NOT found in DB ❌" >&2
  exit 1
fi
echo "Found realm $REALM in DB ✅"

echo "==== Checking realm exists via Admin API ===="
kc_get "/admin/realms/${REALM}" >/dev/null
echo "Realm $REALM exists (API) ✅"

echo "==== Checking USERS ===="
# total user count
user_count=$(kc_get "/admin/realms/${REALM}/users/count" | jq -r '.')
if [[ -z "$user_count" || "$user_count" == "null" ]]; then
  echo "Could not read users count ❌" >&2
  exit 1
fi
echo "Total users: $user_count"
if (( user_count < 1 )); then
  echo "No users present in realm $REALM ❌" >&2
  exit 1
fi
# show a few usernames
kc_get "/admin/realms/${REALM}/users?max=${DEFAULT_MAX}" | jq -r '.[].username' | head -n 10 | sed 's/^/  - /'
echo "Users check ✅"

echo "==== Checking REALM ROLES ===="
# get realm roles (not client roles)
roles_json=$(kc_get "/admin/realms/${REALM}/roles?first=0&max=${DEFAULT_MAX}")
roles_count=$(echo "$roles_json" | jq 'length')
echo "Realm roles found: $roles_count"
if (( roles_count < 1 )); then
  echo "No realm roles present in $REALM ❌" >&2
  exit 1
fi
echo "$roles_json" | jq -r '.[].name' | head -n 15 | sed 's/^/  - /'
# quick presence check for standard roles
for must in offline_access uma_authorization; do
  if ! echo "$roles_json" | jq -e --arg n "$must" '.[] | select(.name==$n)' >/dev/null; then
    echo "WARNING: expected built-in role not found: $must"
  fi
done
echo "Realm roles check ✅"

echo "==== Checking GROUPS ===="
groups_json=$(kc_get "/admin/realms/${REALM}/groups?max=${DEFAULT_MAX}")
groups_count=$(echo "$groups_json" | jq 'length')
echo "Groups found: $groups_count"
if (( groups_count < 1 )); then
  echo "No groups present in $REALM ❌" >&2
  exit 1
fi
# show group paths/names
echo "$groups_json" | jq -r '.[] | (.path // ("/"+.name))' | head -n 15 | sed 's/^/  - /'
echo "Groups check ✅"

echo "==== (Optional) Checking CLIENT roles for osss-api, if client exists ===="
client_id=$(kc_get "/admin/realms/${REALM}/clients?clientId=osss-api" | jq -r '.[0].id // empty')
if [[ -n "$client_id" ]]; then
  client_roles=$(kc_get "/admin/realms/${REALM}/clients/${client_id}/roles?first=0&max=${DEFAULT_MAX}")
  client_roles_count=$(echo "$client_roles" | jq 'length')
  echo "osss-api client roles: $client_roles_count"
  if (( client_roles_count > 0 )); then
    echo "$client_roles" | jq -r '.[].name' | head -n 15 | sed 's/^/  - /'
  else
    echo "WARNING: osss-api present but has no roles."
  fi
else
  echo "Note: client 'osss-api' not found (skipping client role check)."
fi

echo "==== All checks passed ✅ ===="
