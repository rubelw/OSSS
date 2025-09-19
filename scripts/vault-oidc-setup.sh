#!/bin/sh
set -Eeuo pipefail

# -------- verbosity knobs --------
: "${VERBOSE:=1}"   # 1=on, 0=quiet
: "${DEBUG:=0}"     # 1=shell trace (set -x)

if [ "$DEBUG" = "1" ]; then
  export PS4='+ [vault-oidc-setup] ${0##*/}:${LINENO}: '
  set -x
fi

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

  # curl opts: silent, show errors, write code, separate headers
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
      # Show compact body (avoid huge noise)
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

  # On failure, keep response visible and bail
  printf '%s ❌ %s %s -> HTTP %s\n' "$(now)" "$_m" "$_u" "$code" >&2
  cat "$_hdr_file" >&2
  cat "$_body_file" >&2
  rm -f "$_body_file" "$_hdr_file"
  exit 1
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
log "    • ${VAULT_CLI_REDIRECT_1-}"
log "    • ${VAULT_CLI_REDIRECT_2-}"
log "    • ${VAULT_CLI_REDIRECT_3-}"

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
until curl -fsS "http://keycloak:8080/realms/OSSS/.well-known/openid-configuration" >/dev/null 2>&1; do
  sleep 2
done
log "✅ Keycloak discovery reachable"

# Discover actual issuer from well-known (avoid mismatch errors)
DISCOVERY_JSON="$(curl -fsS "http://keycloak:8080/realms/OSSS/.well-known/openid-configuration")"
ISSUER="$(echo "$DISCOVERY_JSON" | jq -r '.issuer')"
[ -n "$ISSUER" ] || { log "❌ Could not parse issuer from discovery"; exit 1; }
log "📛 Using issuer: ${ISSUER}"

# Choose a discovery **base** URL (realm URL) that **Vault** can reach.
# Vault validates this itself, so the hostname must be resolvable/reachable from the *vault* container.
# 1) Prefer Keycloak's container IP (most reliable for Vault)
# 2) Fall back to provided OIDC_DISCOVERY_URL or keycloak:8080
DISCOVERY_BASE_FALLBACK="http://keycloak:8080/realms/OSSS"
DISC_URL_CANDIDATE="${OIDC_DISCOVERY_URL:-$DISCOVERY_BASE_FALLBACK}"
DISC_URL_BASE="$(printf '%s' "$DISC_URL_CANDIDATE" | sed -E 's#(/\.well-known/.*)$##')"

# Try to resolve the Keycloak service name to an IP and use that for discovery (helps if Vault can't resolve 'keycloak')
KC_IP="$(getent hosts keycloak 2>/dev/null | awk '{print $1}' | head -n1 || true)"
if [ -n "$KC_IP" ]; then
  OIDC_DISCOVERY_URL_RESOLVED="http://${KC_IP}:8080/realms/OSSS"
  # quick sanity: make sure *someone* can fetch the well-known (best-effort)
  if ! curl -fsS "${OIDC_DISCOVERY_URL_RESOLVED}/.well-known/openid-configuration" >/dev/null 2>&1; then
    log "⚠️  ${OIDC_DISCOVERY_URL_RESOLVED} not reachable from setup container; falling back to hostname."
    OIDC_DISCOVERY_URL_RESOLVED="$DISC_URL_BASE"
  fi
else
  OIDC_DISCOVERY_URL_RESOLVED="$DISC_URL_BASE"
fi
log "🔗 Using discovery BASE for Vault: ${OIDC_DISCOVERY_URL_RESOLVED}"


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
  # (no trailing slash)
  req POST "${VAULT_ADDR}/v1/sys/auth/oidc" '{"type":"oidc"}'
  # recheck
  AUTH_JSON="$(curl -fsS -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/sys/auth")"
  echo "$AUTH_JSON" | jq -e '.data."oidc/"' >/dev/null 2>&1 \
    || { log "❌ OIDC mount not present after enable"; exit 1; }
}
log "✅ OIDC auth mount present."

# -------- configure OIDC --------
log "➡️  Writing OIDC config…"
# Use a Vault-reachable discovery BASE, and bind to the issuer Keycloak advertises (may be different host/port).

req POST "${VAULT_ADDR}/v1/auth/oidc/config" \
'{
  "oidc_discovery_url": "'"http://keycloak:8080/realms/OSSS"'",
  "bound_issuer": "'"http://keycloak:8080/realms/OSSS"'",
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
log "➡️  Creating role '"${VAULT_OIDC_ROLE}"'…"
req POST "${VAULT_ADDR}/v1/auth/oidc/role/${VAULT_OIDC_ROLE}" \
'{
  "user_claim": "sub",
  "groups_claim": "groups",
  "bound_audiences": ["'"${VAULT_OIDC_CLIENT_ID}"'"],
  "bound_claims_type": "string",
  "bound_claims": { "groups": ["vault-user","vault-admin"] },
  "oidc_scopes": ["openid","groups-claim"],
  "allowed_redirect_uris": [
    "'"${VAULT_UI_REDIRECT_1}"'",
    "'"${VAULT_UI_REDIRECT_2}"'",
    "'"${VAULT_UI_REDIRECT_3}"'",
    "'"${VAULT_CLI_REDIRECT_1}"'",
    "'"${VAULT_CLI_REDIRECT_2}"'",
    "'"${VAULT_CLI_REDIRECT_3}"'"

  ],
  "policies": ["kv-read"],
  "ttl": "1h",
  "verbose_oidc_logging": true
}'

# -------- identity group mapping for admins --------
# Map the Keycloak group (OIDC_ADMIN_GROUP) to a Vault identity group that has the vault-admin policy.
log "🔎 Finding OIDC mount accessor…"
ACCESSOR="$(echo "$AUTH_JSON" | jq -r '.data["oidc/"].accessor')"
[ -n "$ACCESSOR" ] || ACCESSOR="$(curl -fsS -H "X-Vault-Token: ${VAULT_TOKEN}" "${VAULT_ADDR}/v1/sys/auth" | jq -r '.data["oidc/"].accessor')"
[ -n "$ACCESSOR" ] || { log "❌ Could not determine OIDC mount accessor"; exit 1; }
log "🔗 OIDC accessor: ${ACCESSOR}"

# Create/lookup Vault identity group "vault-admins"
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
  # ensure policy attached (idempotent update)
  curl -sS -H "X-Vault-Token: ${VAULT_TOKEN}" -H "Content-Type: application/json" \
    -X POST "${VAULT_ADDR}/v1/identity/group/id/${GID}" \
    -d '{"policies":["vault-admin"]}' >/dev/null
  log "✅ Using existing identity group id: ${GID}"
fi

# Lookup alias; if missing, create alias binding Keycloak group → Vault identity group
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
  # If creation fails (409 or otherwise), show response then continue
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
fi

log "✅ OIDC setup complete."
