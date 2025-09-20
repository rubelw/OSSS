#!/bin/sh
set -eu

# configurable basics
ADMIN_USER="${KEYCLOAK_ADMIN}"
ADMIN_PWD="${KEYCLOAK_ADMIN_PASSWORD}"
KC_URL="${KC_URL}"

echo "▶️  Starting bootstrap Keycloak..."
/opt/keycloak/bin/kc.sh start-dev --http-enabled=true --hostname-strict=false &
BOOT_PID=$!

# Wait until kcadm can authenticate (no curl needed)
echo "⏳ Waiting for Keycloak to accept kcadm credentials..."
until /opt/keycloak/bin/kcadm.sh config credentials \
  --server "$KC_URL" --realm master \
  --user "$ADMIN_USER" --password "$ADMIN_PWD" >/dev/null 2>&1
do
  sleep 2
done
echo "🔐 Logged into admin CLI."

# Delete realm if it exists
if /opt/keycloak/bin/kcadm.sh get realms/OSSS >/dev/null 2>&1; then
  echo "🧹 Deleting existing realm 'OSSS'..."
  /opt/keycloak/bin/kcadm.sh delete realms/OSSS
else
  echo "ℹ️ Realm 'OSSS' not found. Nothing to delete."
fi

echo "🛑 Stopping bootstrap Keycloak..."
kill "$BOOT_PID" || true
wait "$BOOT_PID" 2>/dev/null || true

# Start for real with import + overwrite
echo "🚀 Starting Keycloak with import (OVERWRITE_EXISTING)..."
exec /opt/keycloak/bin/kc.sh start-dev \
  --import-realm \
  --spi-export-import-single-file.strategy=OVERWRITE_EXISTING

REALM="OSSS"

# Create 'roles' client scope if missing
CS_ID=$(/opt/keycloak/bin/kcadm.sh get client-scopes -r "$REALM" | jq -r '.[] | select(.name=="roles") | .id')
if [ -z "$CS_ID" ] || [ "$CS_ID" = "null" ]; then
  /opt/keycloak/bin/kcadm.sh create client-scopes -r "$REALM" \
    -s name=roles -s protocol=openid-connect
  CS_ID=$(/opt/keycloak/bin/kcadm.sh get client-scopes -r "$REALM" | jq -r '.[] | select(.name=="roles") | .id')

  # mapper: realm roles -> realm_access.roles
  /opt/keycloak/bin/kcadm.sh create "client-scopes/$CS_ID/protocol-mappers/models" -r "$REALM" -f - <<'JSON'
{ "name":"realm roles", "protocol":"openid-connect", "protocolMapper":"oidc-usermodel-realm-role-mapper",
  "config":{ "multivalued":"true","userinfo.token.claim":"true","id.token.claim":"true","access.token.claim":"true",
             "claim.name":"realm_access.roles","jsonType.label":"String" } }
JSON

  # mapper: client roles -> resource_access.${client_id}.roles
  /opt/keycloak/bin/kcadm.sh create "client-scopes/$CS_ID/protocol-mappers/models" -r "$REALM" -f - <<'JSON'
{ "name":"client roles", "protocol":"openid-connect", "protocolMapper":"oidc-usermodel-client-role-mapper",
  "config":{ "multivalued":"true","userinfo.token.claim":"true","id.token.claim":"true","access.token.claim":"true",
             "usermodel.clientRoleMapping.clientId":"*",
             "claim.name":"resource_access.${client_id}.roles","jsonType.label":"String" } }
JSON
fi

# Ensure 'roles' is a default realm scope
/opt/keycloak/bin/kcadm.sh update "realms/$REALM" -s 'defaultDefaultClientScopes+=roles'

CLIENT_ID="osss-api"
CID=$(/opt/keycloak/bin/kcadm.sh get "clients?clientId=$CLIENT_ID" -r "$REALM" | jq -r '.[0].id')
SVC_UID=$(/opt/keycloak/bin/kcadm.sh get "clients/$CID/service-account-user" -r "$REALM" | jq -r '.id')

/opt/keycloak/bin/kcadm.sh add-roles -r "$REALM" --uusername "$SVC_UID" \
  --cclientid realm-management \
  --rolename manage-clients --rolename manage-users --rolename manage-realm \
  --rolename view-users --rolename view-realm --rolename query-users \
  --rolename query-clients --rolename query-groups --rolename view-events \
  --rolename view-clients --rolename view-authorization \
  --rolename manage-authorization --rolename impersonation

/opt/keycloak/bin/kcadm.sh add-roles -r "$REALM" --uusername "$SVC_UID" \
  --cclientid account --rolename manage-account --rolename delete-account