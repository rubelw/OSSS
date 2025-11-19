#!/bin/sh
set -Eeuo pipefail

# -------- verbosity knobs --------
: "${VERBOSE:=1}"   # 1=on, 0=quiet
: "${DEBUG:=0}"     # 1=shell trace (set -x)

if [ "$DEBUG" = "1" ]; then
  export PS4='+ [vault-oidc-setup] ${0##*/}:${LINENO}: '
  set -x
fi

# -------- scope knobs (NEW) --------
# Comma-separated list of scopes Vault should request.
# Default: request only built-ins that Keycloak always provides.
: "${VAULT_OIDC_SCOPES:=openid,profile,email}"

# If set to 1, also include "microprofile-jwt" in the scopes list (recommended when you need groups/roles).
# IMPORTANT: In Keycloak, attach client scope "microprofile-jwt" to the 'vault' client (Default or Optional).
: "${INCLUDE_MICROPROFILE_JWT:=0}"

# If you insist on a custom scope name (e.g., groups-claim), set it here and make sure it exists
# in Keycloak and is attached to the 'vault' client.
: "${CUSTOM_SCOPE_NAME:=}"

# -------- small utils --------
now() { date -Iseconds; }
log() { printf '%s %s\n' "$(now)" "$*"; }

# mask secrets in log lines
mask() {
  s=${1-}
  [ -z "$s" ] && { printf '\n'; return; }
  n=${#s}
  if [ "$n" -le 8 ]; then printf '******\n'
  else printf '****%s\n' "$(printf '%s' "$s" | tail -c 5)"
  fi
}

# pretty curl wrapper with request/response logging
# usage: req METHOD URL [JSON_BODY]
req() {
  _m=$1; _u=$2; _b=${3-}

  _body_file=$(mktemp); _hdr_file=$(mktemp)
  if [ -n "${_b}" ]; then
    code="$(printf '%s' "$_b" | curl -sS -D "$_hdr_file" -o "$_body_file" -w '%{http_code}' \
      -H "X-Vault-Token: ${VAULT_TOKEN}" -H "Content-Type: application/json" \
      -X "$_m" "$_u" -d @-)"
  else
    code="$(curl -sS -D "$_hdr_file" -o "$_body_file" -w '%{http_code}' \
      -H "X-Vault-Token: ${VAULT_TOKEN}" -X "$_m" "$_u")"
  fi

  if [ "${VERBOSE}" = "1" ]; then
    log "➡️  ${_m} ${_u}"
    if [ -n "${_b:-}" ]; then
      short="$(printf '%s' "$_b" | tr -d '\n' | sed 's/[[:space:]]\{1,\}/ /g')"
      log "   ├─ body: ${short}"
    fi
    log "   ├─ status: ${code}"
    log "   └─ resp: $(tr -d '\n' < "$_body_file" | cut -c1-400)"
  fi

  if [ "$code" -ge 200 ] && [ "$code" -lt 300 ]; then
    rm -f "$_body_file" "$_hdr_file"
    return 0
  fi

  printf '%s ❌ %s %s -> HTTP %s\n' "$(now)" "$_m" "$_u" "$code" >&2
  cat "$_hdr_file" >&2
  cat "$_body_file" >&2
  rm -f "$_body_file" "$_hdr_file"
  exit 1
}

# Build a JSON array from non-empty env vars (Option 2)
json_array_from_envs() {
  vals=""
  for v in "$@"; do
    eval "x=\${$v:-}"
    [ -n "$x" ] && vals="${vals:+$vals, }\"$x\""
  done
  printf '[%s]' "$vals"
}

# Convert a comma-separated list to a JSON array of strings
json_array_from_csv() {
  IFS=','
  set -- $1
  unset IFS
  out="["
  first=1
  for item in "$@"; do
    item_tr="$(printf '%s' "$item" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    [ -z "$item_tr" ] && continue
    if [ $first -eq 1 ]; then
      out="${out}\"${item_tr}\""
      first=0
    else
      out="${out}, \"${item_tr}\""
    fi
  done
  out="${out}]"
  printf '%s' "$out"
}

# -------- env summary (with masking) --------
log "🔧 VAULT_ADDR=${VAULT_ADDR-}"
log "🔧 OIDC_DISCOVERY_URL=${OIDC_DISCOVERY_URL-}"
log "🔧 VAULT_OIDC_CLIENT_ID=${VAULT_OIDC_CLIENT_ID-}"
log "🔧 VAULT_OIDC_CLIENT_SECRET=$(mask "${VAULT_OIDC_CLIENT_SECRET-}")"
log "🔧 VAULT_OIDC_ROLE=${VAULT_OIDC_ROLE-}"
log "🔧 VAULT_TOKEN=$(mask "${VAULT_TOKEN-}")"
log "🔧 UI redirects:"
log "    • ${VAULT_UI_REDIRECT_1-}"
log "    • ${VAULT_UI_REDIRECT_2-}"
log "    • ${VAULT_UI_REDIRECT_3-}"
log "🔧 CLI redirects:"
log "    • ${VAULT_CLI_REDIRECT_1-}"
log "    • ${VAULT_CLI_REDIRECT_2-}"
log "    • ${VAULT_CLI_REDIRECT_3-}"

# Build the allowed_redirect_uris JSON array, skipping empties (Option 2)
ALLOWED_REDIRECTS="$(json_array_from_envs \
  VAULT_UI_REDIRECT_1 VAULT_UI_REDIRECT_2 VAULT_UI_REDIRECT_3 \
  VAULT_CLI_REDIRECT_1 VAULT_CLI_REDIRECT_2 VAULT_CLI_REDIRECT_3)"
[ "${VERBOSE}" = "1" ] && log "🔧 Computed allowed_redirect_uris=${ALLOWED_REDIRECTS}"

# Compose final scopes list (string, comma-separated)
SCOPES_LIST="${VAULT_OIDC_SCOPES}"
if [ "${INCLUDE_MICROPROFILE_JWT}" = "1" ]; then
  case ",${SCOPES_LIST}," in
    *,microprofile-jwt,*) : ;; # already present
    *) SCOPES_LIST="${SCOPES_LIST},microprofile-jwt" ;;
  esac
fi
if [ -n "${CUSTOM_SCOPE_NAME}" ]; then
  case ",${SCOPES_LIST}," in
    *,"${CUSTOM_SCOPE_NAME}",*) : ;;
    *) SCOPES_LIST="${SCOPES_LIST},${CUSTOM_SCOPE_NAME}" ;;
  esac
fi
SCOPES_JSON="$(json_array_from_csv "${SCOPES_LIST}")"
[ "${VERBOSE}" = "1" ] && log "🔧 Computed oidc_scopes=${SCOPES_JSON}"
if printf '%s' "${SCOPES_LIST}" | grep -q 'microprofile-jwt'; then
  log "ℹ️  Include 'microprofile-jwt' requires that Keycloak client scope 'microprofile-jwt' is attached to the 'vault' client."
fi
if [ -n "${CUSTOM_SCOPE_NAME}" ]; then
  log "ℹ️  Custom scope '${CUSTOM_SCOPE_NAME}' must exist in Keycloak and be attached to the 'vault' client (Default/Optional)."
fi

# -------- readiness waits --------
log "⏳ Waiting for Vault health at ${VAULT_ADDR}…"
i=0
while :; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "${VAULT_ADDR}/v1/sys/health" || echo 000)"
  case "$code" in
    200|429|472|473|501|503) log "✅ Vault reachable (code=${code})"; break ;;
    *) i=$((i+1)); [ "$i" -le 180 ] || { log "❌ Vault not reachable (last code=${code})"; exit 1; }; sleep 1 ;;
  esac
done
log "✅ Vault reachable"

log "⏳ Waiting for Keycloak discovery…"
until curl -fsS "https://keycloak:8443/realms/OSSS/.well-known/openid-configuration" >/dev/null 2>&1; do
  sleep 2
done
log "✅ Keycloak discovery reachable"

# Discover actual issuer from well-known (avoid mismatch errors)
DISCOVERY_JSON="$(curl -fsS "https://keycloak:8443/realms/OSSS/.well-known/openid-configuration")"
ISSUER="$(echo "$DISCOVERY_JSON" | jq -r '.issuer')"
[ -n "$ISSUER" ] || { log "❌ Could not parse issuer from discovery"; exit 1; }
log "📛 Using issuer: ${ISSUER}"

# -------- use issuer as discovery BASE (must match exactly) --------
REALM_BASE="${ISSUER%/}"
OIDC_DISCOVERY_URL_RESOLVED="$REALM_BASE"
log "🔗 Using discovery BASE for Vault: ${OIDC_DISCOVERY_URL_RESOLVED}"

# Sanity: issuer host must be reachable from THIS container
curl -fsS "${OIDC_DISCOVERY_URL_RESOLVED}/.well-known/openid-configuration" >/dev/null \
  || { log "❌ Issuer host not reachable from setup container: ${OIDC_DISCOVERY_URL_RESOLVED}"; \
       log "   Tip: ensure vault & setup can resolve the issuer host (e.g., add extra_hosts for keycloak.local)"; \
       exit 1; }

# -------- load CA for TLS trust in Vault's OIDC config --------
# JSON-escape the PEM so it's safe to embed in the request body
CA_PEM_JSON="$(jq -Rs . </etc/ssl/certs/keycloak-ca.crt)" || CA_PEM_JSON=""
[ -n "$CA_PEM_JSON" ] || { log "❌ Missing or unreadable /etc/ssl/certs/keycloak-ca.crt"; exit 1; }


# -------- validate token and mounts --------
log "🔍 Validating VAULT_TOKEN…"
curl -fsS -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/auth/token/lookup-self" >/dev/null \
  || { log "❌ VAULT_TOKEN invalid for ${VAULT_ADDR}"; exit 1; }
log "✅ Token valid"

log "🔎 Checking existing auth mounts…"
AUTH_JSON="$(curl -fsS -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/sys/auth")" \
  || { log "❌ cannot read /v1/sys/auth"; exit 1; }
[ "${VERBOSE}" = "1" ] && printf '%s\n' "$AUTH_JSON" | jq -r '.data | keys[]' 2>/dev/null || true

echo "$AUTH_JSON" | jq -e '.data."oidc/"' >/dev/null 2>&1 || {
  log "➡️  Enabling OIDC at auth/oidc…"
  req POST "${VAULT_ADDR}/v1/sys/auth/oidc" '{"type":"oidc"}'
  AUTH_JSON="$(curl -fsS -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/sys/auth")"
  echo "$AUTH_JSON" | jq -e '.data."oidc/"' >/dev/null 2>&1 \
    || { log "❌ OIDC mount not present after enable"; exit 1; }
}
log "✅ OIDC auth mount present."

# -------- configure OIDC (two-phase) --------
log "➡️  Writing OIDC config (phase 1: without bound_issuer)…"
req POST "${VAULT_ADDR}/v1/auth/oidc/config" \
'{
  "oidc_discovery_url": "'"${OIDC_DISCOVERY_URL_RESOLVED}"'",
  "oidc_discovery_ca_pem": '"$CA_PEM_JSON"',
  "oidc_client_id": "'"${VAULT_OIDC_CLIENT_ID}"'",
  "oidc_client_secret": "'"${VAULT_OIDC_CLIENT_SECRET}"'",
  "default_role": "'"${VAULT_OIDC_ROLE}"'"
}'

log "➡️  Updating OIDC config (phase 2: add bound_issuer from discovery)…"
req POST "${VAULT_ADDR}/v1/auth/oidc/config" \
'{
  "oidc_discovery_url": "'"${OIDC_DISCOVERY_URL_RESOLVED}"'",
  "oidc_discovery_ca_pem": '"$CA_PEM_JSON"',
  "bound_issuer": "'"${ISSUER}"'",
  "oidc_client_id": "'"${VAULT_OIDC_CLIENT_ID}"'",
  "oidc_client_secret": "'"${VAULT_OIDC_CLIENT_SECRET}"'",
  "default_role": "'"${VAULT_OIDC_ROLE}"'"
}'

# -------- policies --------
log "➡️  Writing kv-read policy (UI browse + read)…"
req PUT "${VAULT_ADDR}/v1/sys/policies/acl/kv-read" \
'{
  "policy": "path \"secret/metadata/*\" { capabilities = [\"list\",\"read\"] }\npath \"secret/data/*\" { capabilities = [\"read\"] }"
}'

log "➡️  Writing vault-admin policy (full CRUD on secret)…"
req PUT "${VAULT_ADDR}/v1/sys/policies/acl/vault-admin" \
'{
  "policy": "path \"secret/metadata\" { capabilities=[\"list\",\"read\"] }\npath \"secret/metadata/*\" { capabilities=[\"create\",\"read\",\"update\",\"delete\",\"list\"] }\npath \"secret/data/*\" { capabilities=[\"create\",\"read\",\"update\",\"delete\",\"list\"] }"
}'

# -------- role --------
log "➡️  Creating role '${VAULT_OIDC_ROLE}'…"
req POST "${VAULT_ADDR}/v1/auth/oidc/role/${VAULT_OIDC_ROLE}" \
'{
  "user_claim": "sub",
  "groups_claim": "groups",
  "bound_audiences": ["'"${VAULT_OIDC_CLIENT_ID}"'"],

  "bound_claims": { "groups": ["vault-users","vault-admins"] },

  "oidc_scopes": '"${SCOPES_JSON}"',
  "allowed_redirect_uris": '"${ALLOWED_REDIRECTS}"',
  "policies": ["kv-read"],
  "ttl": "1h",
  "verbose_oidc_logging": true
}'

# -------- identity group mapping for admins --------
log "🔎 Finding OIDC mount accessor…"
ACCESSOR="$(echo "$AUTH_JSON" | jq -r '.data["oidc/"].accessor')"
[ -n "$ACCESSOR" ] || ACCESSOR="$(curl -fsS -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/sys/auth" | jq -r '.data["oidc/"].accessor')"
[ -n "$ACCESSOR" ] || { log "❌ Could not determine OIDC mount accessor"; exit 1; }
log "🔗 OIDC accessor: ${ACCESSOR}"

log "🔎 Checking/creating identity group 'vault-admins'…"
GID="$(curl -sS -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/identity/group/name/vault-admins" | jq -r '.data.id // empty')"
if [ -z "$GID" ]; then
  GJSON="$(curl -sS -H "X-Vault-Token: ${VAULT_TOKEN}" -H "Content-Type: application/json" \
    -X POST "${VAULT_ADDR}/v1/identity/group" \
    -d "{\"name\":\"vault-admins\",\"policies\":[\"vault-admin\"]}")"
  GID="$(echo "$GJSON" | jq -r '.data.id')"
  [ -n "$GID" ] || { log "❌ Failed to create identity group 'vault-admins'"; echo "$GJSON"; exit 1; }
  log "✅ Created identity group with id: ${GID}"
else
  curl -sS -H "X-Vault-Token: ${VAULT_TOKEN}" -H "Content-Type: application/json" \
    -X POST "${VAULT_ADDR}/v1/identity/group/id/${GID}" \
    -d '{"policies":["vault-a2a"]}' >/dev/null
  log "✅ Using existing identity group id: ${GID}"
fi

log "🔎 Looking up group alias '${OIDC_ADMIN_GROUP}'…"
ALOOKUP="$(curl -sS -H "X-Vault-Token: ${VAULT_TOKEN}" -H "Content-Type: application/json" \
  -X POST "${VAULT_ADDR}/v1/identity/lookup/group" \
  -d "{\"alias_name\":\"${OIDC_ADMIN_GROUP}\",\"alias_mount_accessor\":\"${ACCESSOR}\"}")"
ALIAS_ID="$(echo "$ALOOKUP" | jq -r '.data.id // empty')"

if [ -z "$ALIAS_ID" ]; then
  log "➡️  Creating group alias for '${OIDC_ADMIN_GROUP}'…"
  AJSON="$(curl -sS -H "X-Vault-Token: ${VAULT_TOKEN}" -H "Content-Type: application/json" \
    -X POST "${VAULT_ADDR}/v1/identity/group-alias" \
    -d "{\"name\":\"${OIDC_ADMIN_GROUP}\",\"mount_accessor\":\"${ACCESSOR}\",\"canonical_id\":\"${GID}\"}")"
  echo "$AJSON" | jq . >/dev/null 2>&1 || true
  log "✅ Group alias ensured."
else
  log "✅ Group alias already exists (id: ${ALIAS_ID})."
fi

# -------- final diagnostics --------
if [ "${VERBOSE}" = "1" ]; then
  log "📋 auth list:"
  curl -fsS -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/sys/auth" | jq .
  log "📋 oidc config:"
  curl -fsS -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/auth/oidc/config" | jq .
  log "📋 role '${VAULT_OIDC_ROLE}':"
  curl -fsS -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/auth/oidc/role/${VAULT_OIDC_ROLE}" | jq .
fi

log "✅ OIDC setup complete."