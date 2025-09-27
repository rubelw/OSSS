#!/bin/sh
set -eu

# --- Config (required envs) ---
ADMIN_USER="${KEYCLOAK_ADMIN:?KEYCLOAK_ADMIN is required}"
ADMIN_PWD="${KEYCLOAK_ADMIN_PASSWORD:?KEYCLOAK_ADMIN_PASSWORD is required}"

# TLS files (must be mounted by compose to these paths)
CERT="${KC_HTTPS_CERTIFICATE_FILE:-/opt/keycloak/conf/tls/server.crt}"
KEYF="${KC_HTTPS_CERTIFICATE_KEY_FILE:-/opt/keycloak/conf/tls/server.key}"

# Key options
KC_HTTP_ENABLED="${KC_HTTP_ENABLED:-false}"
KC_HTTP_PORT="${KC_HTTP_PORT:-8080}"
KC_HOSTNAME="${KC_HOSTNAME:-keycloak.local}"
KC_HOSTNAME_STRICT="${KC_HOSTNAME_STRICT:-false}"
KC_HTTPS_PORT="${KC_HTTPS_PORT:-8443}"

# Import locations (read-only safe)
IMPORT_DIR_ORIG="${IMPORT_DIR:-/opt/keycloak/data/import}"
IMPORT_FILE_ORIG="${IMPORT_FILE:-$IMPORT_DIR_ORIG/10-OSSS.json}"
SANITIZED_IMPORT="/tmp/realm-import.json"

REALM="${REALM:-OSSS}"

# Resolve the URL kcadm should hit during bootstrap (HTTP; dev mode)
KC_BOOT_URL="http://$KC_HOSTNAME:${KC_HTTP_PORT}"
# Resolve canonical origin for webOrigins/front-end URL
BASE_URL="${KC_HOSTNAME_URL:-https://${KC_HOSTNAME}:${KC_HTTPS_PORT}}"
# ORIGIN like "https://keycloak.local:8443" (no trailing slash)
ORIGIN="$(printf %s "$BASE_URL" | sed -E 's~/*$~~; s~^((https?)://[^/]+).*$~\1~')"

# Basic checks
if [ ! -s "$CERT" ] || [ ! -s "$KEYF" ]; then
  echo "❌ TLS files not found. Expected:"
  echo "   CERT=$CERT"
  echo "   KEYF=$KEYF"
  exit 1
fi

# --- Prepare import file in /tmp (optionally sanitize) ---
if [ -f "$IMPORT_FILE_ORIG" ]; then
  cp "$IMPORT_FILE_ORIG" "$SANITIZED_IMPORT"
  # If your export still references deleted built-ins, you can scrub them:
  # sed -i 's/"web-origins"//g; s/"address"//g; s/"phone"//g' "$SANITIZED_IMPORT" || true
  # sed -i 's/,,/,/g; s/\[,/[/g; s/,]/]/g' "$SANITIZED_IMPORT" || true
else
  echo "❌ Import file not found: $IMPORT_FILE_ORIG"
  exit 1
fi

echo "▶️  Starting bootstrap Keycloak (DEV)…"
/opt/keycloak/bin/kc.sh start-dev \
  --http-port="$KC_HTTP_PORT" \
  --hostname="$KC_HOSTNAME" \
  --log-level=info \
  &
BOOT_PID=$!

# Ensure we clean up the bootstrap server on exit
trap 'kill "$BOOT_PID" 2>/dev/null || true; wait "$BOOT_PID" 2>/dev/null || true' EXIT

# Wait for admin CLI login
echo "⏳ Waiting for Keycloak to accept kcadm credentials at $KC_BOOT_URL…"
until /opt/keycloak/bin/kcadm.sh config credentials \
  --server "$KC_BOOT_URL" --realm master \
  --user "$ADMIN_USER" --password "$ADMIN_PWD" --insecure >/dev/null 2>&1
do
  sleep 2
done
echo "🔐 Logged into admin CLI."

# Realm import (idempotent)
if /opt/keycloak/bin/kcadm.sh get "realms/$REALM" --server "$KC_BOOT_URL" --realm master --insecure >/dev/null 2>&1; then
  echo "♻️  Realm '$REALM' exists. Applying partial import (OVERWRITE)…"
  /opt/keycloak/bin/kcadm.sh create "realms/$REALM/partialImport" \
    --server "$KC_BOOT_URL" --realm "$REALM" --insecure \
    -s ifResourceExists=OVERWRITE -f "$SANITIZED_IMPORT" >/dev/null
else
  echo "📦 Creating realm '$REALM' from export…"
  /opt/keycloak/bin/kcadm.sh create realms \
    --server "$KC_BOOT_URL" --realm master --insecure \
    -f "$SANITIZED_IMPORT" >/dev/null
fi

# ---------- Helpers (jq-free) ----------
extract_first_id() {
  # Extracts the first "id" value from JSON
  sed -n 's/.*\"id\"[[:space:]]*:[[:space:]]*\"\([^\"]\+\)\".*/\1/p' | head -n1
}

get_client_scope_id() {
  # $1 = realm, $2 = scope name
  /opt/keycloak/bin/kcadm.sh get client-scopes -r "$1" --server "$KC_BOOT_URL" --insecure -q "name=$2" --fields id 2>/dev/null | extract_first_id || true
}

ensure_client_scope() {
  # $1 = realm, $2 = scope name
  local id
  id="$(get_client_scope_id "$1" "$2")"
  if [ -z "${id:-}" ]; then
    echo "➕ Creating client scope '$2'…"
    /opt/keycloak/bin/kcadm.sh create client-scopes -r "$1" --server "$KC_BOOT_URL" --insecure \
      -s "name=$2" -s protocol=openid-connect >/dev/null
    id="$(get_client_scope_id "$1" "$2")"
  fi
  printf %s "$id"
}

protocol_mapper_exists() {
  # $1 = realm, $2 = scope_id, $3 = mapper_name
  /opt/keycloak/bin/kcadm.sh get "client-scopes/$2/protocol-mappers/models" -r "$1" --server "$KC_BOOT_URL" --insecure 2>/dev/null \
    | grep -F "\"name\" : \"$3\"" >/dev/null 2>&1
}

ensure_audience_mapper() {
  # $1 = realm, $2 = scope_id, $3 = target client-id, $4 = mapper display name
  if ! protocol_mapper_exists "$1" "$2" "$4"; then
    echo "➕ Adding audience mapper '$4' to scope id $2…"
    /opt/keycloak/bin/kcadm.sh create "client-scopes/$2/protocol-mappers/models" -r "$1" --server "$KC_BOOT_URL" --insecure -f - <<JSON >/dev/null
{ "name":"$4", "protocol":"openid-connect", "protocolMapper":"oidc-audience-mapper",
  "config":{"included.client.audience":"$3","access.token.claim":"true","id.token.claim":"true","userinfo.token.claim":"false"}}
JSON
  fi
}

ensure_default_scope_attached() {
  # $1 = realm, $2 = scope name
  # Using += is additive and safe even if already present
  /opt/keycloak/bin/kcadm.sh update "realms/$1" --server "$KC_BOOT_URL" --insecure \
    -s "defaultDefaultClientScopes+=$2" >/dev/null 2>&1 || true
}

# ---------- Ensure 'roles' scope + mappers ----------
CS_ROLES_ID=$(
  /opt/keycloak/bin/kcadm.sh get client-scopes -r "$REALM" --server "$KC_BOOT_URL" --insecure -q name=roles --fields id,name 2>/dev/null \
  | extract_first_id || true
)
if [ -z "${CS_ROLES_ID:-}" ]; then
  echo "➕ Creating 'roles' client scope…"
  /opt/keycloak/bin/kcadm.sh create client-scopes -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s name=roles -s protocol=openid-connect >/dev/null
  CS_ROLES_ID=$(
    /opt/keycloak/bin/kcadm.sh get client-scopes -r "$REALM" --server "$KC_BOOT_URL" --insecure -q name=roles --fields id,name \
    | extract_first_id
  )
fi

# Add the two standard role mappers (ignore 409)
cat >/tmp/pm1.json <<'JSON'
{ "name":"realm roles","protocol":"openid-connect","protocolMapper":"oidc-usermodel-realm-role-mapper",
  "config":{"multivalued":"true","userinfo.token.claim":"true","id.token.claim":"true","access.token.claim":"true",
            "claim.name":"realm_access.roles","jsonType.label":"String"}}
JSON
/opt/keycloak/bin/kcadm.sh create "client-scopes/$CS_ROLES_ID/protocol-mappers/models" -r "$REALM" --server "$KC_BOOT_URL" --insecure -f /tmp/pm1.json >/dev/null 2>&1 || true

cat >/tmp/pm2.json <<'JSON'
{ "name":"client roles","protocol":"openid-connect","protocolMapper":"oidc-usermodel-client-role-mapper",
  "config":{"multivalued":"true","userinfo.token.claim":"true","id.token.claim":"true","access.token.claim":"true",
            "usermodel.clientRoleMapping.clientId":"*",
            "claim.name":"resource_access.${client_id}.roles","jsonType.label":"String"}}
JSON
/opt/keycloak/bin/kcadm.sh create "client-scopes/$CS_ROLES_ID/protocol-mappers/models" -r "$REALM" --server "$KC_BOOT_URL" --insecure -f /tmp/pm2.json >/dev/null 2>&1 || true

ensure_default_scope_attached "$REALM" "roles"
ensure_default_scope_attached "$REALM" "profile"
ensure_default_scope_attached "$REALM" "email"

# ---------- Ensure 'account-audience' scope + audience mapper -> account ----------
CS_ACC_AUD_ID="$(ensure_client_scope "$REALM" "account-audience")"

# Nice-to-have attributes
/opt/keycloak/bin/kcadm.sh update "client-scopes/$CS_ACC_AUD_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
  -s 'attributes."display.on.consent.screen"=false' \
  -s 'attributes."consent.screen.text"=' \
  -s 'attributes."include.in.token.scope"=true' >/dev/null 2>&1 || true

ensure_audience_mapper "$REALM" "$CS_ACC_AUD_ID" "account" "audience account"
ensure_default_scope_attached "$REALM" "account-audience"

# ---------- Configure built-in account-console as SPA ----------
ACC_CONSOLE_ID=$(/opt/keycloak/bin/kcadm.sh get clients -r "$REALM" --server "$KC_BOOT_URL" --insecure -q clientId=account-console --fields id | extract_first_id || true)
if [ -n "${ACC_CONSOLE_ID:-}" ]; then
  echo "🛠  Configuring 'account-console' as public SPA…"
  /opt/keycloak/bin/kcadm.sh update "clients/$ACC_CONSOLE_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s publicClient=true \
    -s standardFlowEnabled=true \
    -s implicitFlowEnabled=false \
    -s directAccessGrantsEnabled=false \
    -s serviceAccountsEnabled=false \
    -s 'attributes."pkce.code.challenge.method"=S256' \
    -s baseUrl="/realms/$REALM/account/" \
    -s "redirectUris=[\"$ORIGIN/realms/$REALM/account/*\"]" \
    -s "webOrigins=[\"+\",\"$ORIGIN\"]" >/dev/null
fi

# ---------- Realm tweaks: frontendUrl + (re)attach defaults ----------
/opt/keycloak/bin/kcadm.sh update "realms/$REALM" --server "$KC_BOOT_URL" --insecure \
  -s "attributes.frontendUrl=$ORIGIN" \
  -s 'defaultDefaultClientScopes+=profile' \
  -s 'defaultDefaultClientScopes+=email' \
  -s 'defaultDefaultClientScopes+=roles' \
  -s 'defaultDefaultClientScopes+=account-audience' >/dev/null 2>&1 || true

# ---------- CORS/webOrigins for security-admin-console ----------
set_weborigins() {
  _CID="$(/opt/keycloak/bin/kcadm.sh get clients -r "$REALM" --server "$KC_BOOT_URL" --insecure -q clientId="$1" --fields id 2>/dev/null | extract_first_id || true)"
  [ -z "$_CID" ] && { echo "ℹ️  Client '$1' not found in realm '$REALM' (skipping)"; return 0; }
  /opt/keycloak/bin/kcadm.sh update "clients/$_CID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s 'webOrigins=["+"]' >/dev/null 2>&1 || true
  /opt/keycloak/bin/kcadm.sh update "clients/$_CID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s "webOrigins+=$ORIGIN" >/dev/null 2>&1 || true
}
set_weborigins "security-admin-console"

# ---------- Grant realm-management roles to 'osss-api' service account (if present) ----------
CLIENT_ID="osss-api"
CID=$(/opt/keycloak/bin/kcadm.sh get "clients" -r "$REALM" --server "$KC_BOOT_URL" --insecure -q clientId="$CLIENT_ID" --fields id 2>/dev/null | extract_first_id || true)
if [ -n "${CID:-}" ]; then
  SVC_UID=$(/opt/keycloak/bin/kcadm.sh get "clients/$CID/service-account-user" -r "$REALM" --server "$KC_BOOT_URL" --insecure --fields id 2>/dev/null | extract_first_id || true)
  if [ -n "${SVC_UID:-}" ]; then
    /opt/keycloak/bin/kcadm.sh add-roles -r "$REALM" --server "$KC_BOOT_URL" --insecure --uusername "$SVC_UID" \
      --cclientid realm-management \
      --rolename manage-clients --rolename manage-users --rolename manage-realm \
      --rolename view-users --rolename view-realm --rolename query-users \
      --rolename query-clients --rolename query-groups --rolename view-events \
      --rolename view-clients --rolename view-authorization \
      --rolename manage-authorization --rolename impersonation >/dev/null 2>&1 || true
    /opt/keycloak/bin/kcadm.sh add-roles -r "$REALM" --server "$KC_BOOT_URL" --insecure --uusername "$SVC_UID" \
      --cclientid account --rolename manage-account --rolename delete-account >/dev/null 2>&1 || true
  fi
fi

echo "🛑 Stopping bootstrap Keycloak…"
kill "$BOOT_PID" || true
wait "$BOOT_PID" 2>/dev/null || true
trap - EXIT

# --- Build (once) with DB provider; runtime flags are ignored here by design ---
echo "🔧 Building Keycloak with Postgres provider…"
/opt/keycloak/bin/kc.sh build --db=postgres

# --- Final prod server (PID 1). NOTE: no --import-realm (we already imported) ---
echo "🚀 Starting Keycloak (prod)…"
exec /opt/keycloak/bin/kc.sh start \
  --http-enabled="$KC_HTTP_ENABLED" \
  --http-port="$KC_HTTP_PORT" \
  --https-port="$KC_HTTPS_PORT" \
  --https-certificate-file="$CERT" \
  --https-certificate-key-file="$KEYF" \
  --hostname-strict="$KC_HOSTNAME_STRICT" \
  --hostname="$KC_HOSTNAME" \
  --log-level=info
