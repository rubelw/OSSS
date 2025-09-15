#!/usr/bin/env bash
set -Eeuo pipefail

MAPS_FILE="${1:-}"
: "${KEYCLOAK_URL:?set KEYCLOAK_URL}"
: "${KEYCLOAK_REALM:?set KEYCLOAK_REALM}"
: "${KEYCLOAK_ADMIN:?set KEYCLOAK_ADMIN}"
: "${KEYCLOAK_ADMIN_PASSWORD:?set KEYCLOAK_ADMIN_PASSWORD}"

if [[ -z "${MAPS_FILE}" || ! -f "${MAPS_FILE}" ]]; then
  echo "Usage: $0 <group-role-mappings.json>"; exit 2
fi

# Small helpers
wait_http() {
  local url="$1" tries="${2:-120}"
  for ((i=1;i<=tries;i++)); do
    if curl -fsS "$url" >/dev/null; then return 0; fi
    sleep 1
  done
  echo "Timeout waiting for $url"; return 1
}

kc_token() {
  curl -fsS -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "grant_type=password&client_id=admin-cli&username=${KEYCLOAK_ADMIN}&password=${KEYCLOAK_ADMIN_PASSWORD}" \
    | jq -r '.access_token'
}

get_group_id() {
  local name="$1" path="${2:-}"
  # Prefer exact by path if provided (unique)
  if [[ -n "$path" ]]; then
    # Keycloak API doesn’t have "by path" directly; filter client-side
    curl -fsS -H "Authorization: Bearer ${TOKEN}" \
      "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/groups?search=$(printf %s "$name" | jq -sRr @uri)" \
      | jq -r --arg p "$path" '.[] | select(.path==$p) | .id' | head -n1
  else
    curl -fsS -H "Authorization: Bearer ${TOKEN}" \
      "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/groups?search=$(printf %s "$name" | jq -sRr @uri)" \
      | jq -r --arg n "$name" '.[] | select(.name==$n) | .id' | head -n1
  fi
}

get_realm_role() {
  local role="$1"
  curl -fsS -H "Authorization: Bearer ${TOKEN}" \
    "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/roles/$(printf %s "$role" | jq -sRr @uri)"
}

get_client_id_uuid() {
  local cid="$1"
  curl -fsS -H "Authorization: Bearer ${TOKEN}" \
    "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/clients?clientId=$(printf %s "$cid" | jq -sRr @uri)" \
    | jq -r '.[0].id'
}

get_client_role() {
  local client_uuid="$1" role="$2"
  curl -fsS -H "Authorization: Bearer ${TOKEN}" \
    "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/clients/${client_uuid}/roles/$(printf %s "$role" | jq -sRr @uri)"
}

assign_realm_roles() {
  local group_uuid="$1" roles_json="$2"
  [[ -z "$roles_json" ]] && return 0
  local payload
  payload="$(jq -c --argjson names "$roles_json" '
      [$names[] | . as $n | {"name":$n}]' <<<"")" || true
  # fetch full reps
  local arr="[]"
  for r in $(jq -r '.[]' <<<"$roles_json"); do
    local rep; rep="$(get_realm_role "$r")" || true
    [[ -n "$rep" && "$rep" != "null" ]] && arr="$(jq -c --argjson one "$rep" '. + [$one]' <<<"$arr")"
  done
  [[ "$arr" = "[]" ]] && return 0
  curl -fsS -X POST -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
    -d "$arr" \
    "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/groups/${group_uuid}/role-mappings/realm" >/dev/null
}

assign_client_roles() {
  local group_uuid="$1" client_roles_obj="$2"
  [[ -z "$client_roles_obj" || "$client_roles_obj" = "null" ]] && return 0
  # iterate clients
  for cid in $(jq -r 'keys[]' <<<"$client_roles_obj"); do
    local client_uuid; client_uuid="$(get_client_id_uuid "$cid")"
    [[ -z "$client_uuid" || "$client_uuid" = "null" ]] && continue
    local names; names="$(jq -c --arg k "$cid" '.[$k]' <<<"$client_roles_obj")"

    # fetch role reps
    local arr="[]"
    for r in $(jq -r '.[]' <<<"$names"); do
      local rep; rep="$(get_client_role "$client_uuid" "$r")" || true
      [[ -n "$rep" && "$rep" != "null" ]] && arr="$(jq -c --argjson one "$rep" '. + [$one]' <<<"$arr")"
    done
    [[ "$arr" = "[]" ]] && continue
    curl -fsS -X POST -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
      -d "$arr" \
      "${KEYCLOAK_URL}/admin/realms/${KEYCLOAK_REALM}/groups/${group_uuid}/role-mappings/clients/${client_uuid}" >/dev/null
  done
}

#echo "Waiting for Keycloak to be ready at ${KEYCLOAK_URL} ..."
#wait_http "http://keycloak:9000/health/ready" 180


echo "Obtaining admin token ..."
TOKEN="$(kc_token)"
if [[ -z "$TOKEN" || "$TOKEN" == "null" ]]; then
  echo "ERROR: Failed to obtain admin token"; exit 1
fi

# list a few users
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://keycloak-seed:8080/admin/realms/OSSS/users?max=5" \
  | jq '.[].username' \
  || curl -v -H "Authorization: Bearer $TOKEN" \
       "http://keycloak-seed:8080/admin/realms/OSSS/users?max=5"

# list a few groups
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://keycloak-seed:8080/admin/realms/OSSS/groups?max=20" \
  | jq '.[].path' \
  || curl -v -H "Authorization: Bearer $TOKEN" \
       "http://keycloak-seed:8080/admin/realms/OSSS/groups?max=20"



echo "Applying group→role mappings from ${MAPS_FILE}"
# { "realm": "OSSS", "groupRoleMappings": [ {name, path?, realmRoles?, clientRoles?}, ... ] }
jq -c '.groupRoleMappings[]' "${MAPS_FILE}" | while read -r item; do
  name="$(jq -r '.name' <<<"$item")"
  path="$(jq -r '.path // empty' <<<"$item")"
  realm_roles="$(jq -c '.realmRoles // []' <<<"$item")"
  client_roles="$(jq -c '.clientRoles // {}' <<<"$item")"

  gid="$(get_group_id "$name" "$path")"
  if [[ -z "$gid" ]]; then
    echo "WARN: group not found: name=${name} path=${path}"
    continue
  fi
  assign_realm_roles "$gid" "$realm_roles"
  assign_client_roles "$gid" "$client_roles"
  echo "OK: mapped roles to group '${name}' (${gid})"
done

echo "Done."
