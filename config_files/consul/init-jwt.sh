#!/bin/sh
set -euo pipefail
export PS4='+ [consul-jwt-init:${LINENO}] '
echo "== ENV =="; env | sort

: "${CONSUL_HTTP_ADDR:=http://consul:8500}"
: "${CONSUL_HTTP_TOKEN:?CONSUL_HTTP_TOKEN is required}"

ADDR="$CONSUL_HTTP_ADDR"

echo "ADDR=$ADDR"
[ -f /cfg/jwt.json ] && echo "JWT config present at /cfg/jwt.json" || echo "WARN: /cfg/jwt.json missing"

# --- wait for Consul leader & ACLs (be tolerant of 403s while ACLs settle) ---
tries=60
until curl -fsS "$ADDR/v1/status/leader" >/dev/null 2>&1 || [ $((tries-=1)) -le 0 ]; do sleep 1; done
[ $tries -le 0 ] && { echo "ERROR: Consul leader not ready"; exit 1; }

tries=60
until curl -fsS -H "X-Consul-Token: $CONSUL_HTTP_TOKEN" "$ADDR/v1/agent/self" >/dev/null 2>&1 \
  || [ $((tries-=1)) -le 0 ]; do sleep 1; done
[ $tries -le 0 ] && echo "WARN: agent/self still 403; continuing (server ACLs likely up)"

# --- ensure auth method exists (already created in your flow) ---
if consul acl auth-method read -name keycloak-jwt >/dev/null 2>&1; then
  echo "✅ Auth method keycloak-jwt exists"
else
  consul acl auth-method create -name keycloak-jwt -type jwt -max-token-ttl 24h -config @/cfg/jwt.json
fi

# --- ensure policies ---
ADMIN_RULES='node_prefix "" { policy = "write" }
service_prefix "" { policy = "write" }
key_prefix "" { policy = "write" }
agent_prefix "" { policy = "write" }
session_prefix "" { policy = "write" }
event_prefix "" { policy = "write" }
query_prefix "" { policy = "write" }'

USER_RULES='node_prefix "" { policy = "read" }
service_prefix "" { policy = "read" }
key_prefix "" { policy = "read" }
agent_prefix "" { policy = "read" }
session_prefix "" { policy = "read" }
event_prefix "" { policy = "read" }
query_prefix "" { policy = "read" }'

if ! consul acl policy read -name consul-admin >/dev/null 2>&1; then
  printf '%s\n' "$ADMIN_RULES" | consul acl policy create -name consul-admin -description "Full admin via Keycloak group" -rules -
else
  printf '%s\n' "$ADMIN_RULES" | consul acl policy update -name consul-admin -rules -
fi

if ! consul acl policy read -name consul-user >/dev/null 2>&1; then
  printf '%s\n' "$USER_RULES" | consul acl policy create -name consul-user -description "Read-only via Keycloak group" -rules -
else
  printf '%s\n' "$USER_RULES" | consul acl policy update -name consul-user -rules -
fi

# --- ensure roles (attach policies) ---
ensure_role() {
  role="$1"; policy="$2"; desc="$3"
  if consul acl role read -name "$role" >/dev/null 2>&1; then
    # idempotently ensure the policy is attached
    if ! consul acl role read -name "$role" -format=json | jq -e --arg p "$policy" '.Policies[]?.Name == $p' >/dev/null; then
      consul acl role update -name "$role" -policy-name "$policy" -description "$desc"
    fi
  else
    consul acl role create -name "$role" -policy-name "$policy" -description "$desc"
  fi
}

ensure_role "consul-admin" "consul-admin" "Consul admin via Keycloak"
ensure_role "consul-user"  "consul-user"  "Consul user via Keycloak"

# --- helper: try a selector and return 0 on success ---
try_selector() {
  sel="$1"; role="$2"
  # already present?
  if consul acl binding-rule list -method keycloak-jwt -format=json 2>/dev/null \
      | jq -e --arg s "$sel" --arg r "$role" 'map(select(.Selector==$s and .BindName==$r))|length>0' >/dev/null; then
    echo "✔ binding already exists: [$sel] -> $role"
    return 0
  fi
  if consul acl binding-rule create -method keycloak-jwt -selector "$sel" -bind-type role -bind-name "$role" >/dev/null 2>&1; then
    echo "✅ created binding: [$sel] -> $role"
    return 0
  else
    echo "… failed selector: $sel"
    return 1
  fi
}

# --- probe possible selector spellings (varies by Consul build/config) ---
# Most common first:
ADMIN_GROUP="consul-admins"
USER_GROUP="consul-users"

ADMIN_SELECTORS='
groups contains "consul-admins"
jwt.groups contains "consul-admins"
oidc.groups contains "consul-admins"
claims.groups contains "consul-admins"
'

USER_SELECTORS='
groups contains "consul-users"
jwt.groups contains "consul-users"
oidc.groups contains "consul-users"
claims.groups contains "consul-users"
'

ok=false
for s in $ADMIN_SELECTORS; do
  # join two tokens into one selector line when we split above
  sel="$s"
  # rebuild full line if it broke (best-effort)
  case "$sel" in
    groups) read nxt; sel="groups $nxt" ;;
    jwt.groups) read nxt; sel="jwt.groups $nxt" ;;
    oidc.groups) read nxt; sel="oidc.groups $nxt" ;;
    claims.groups) read nxt; sel="claims.groups $nxt" ;;
  esac
  if try_selector "$sel" "consul-admin"; then ok=true; break; fi
done
$ok || echo "WARN: no admin binding created; check attribute keys via /v1/acl/token/self"

ok=false
for s in $USER_SELECTORS; do
  sel="$s"
  case "$sel" in
    groups) read nxt; sel="groups $nxt" ;;
    jwt.groups) read nxt; sel="jwt.groups $nxt" ;;
    oidc.groups) read nxt; sel="oidc.groups $nxt" ;;
    claims.groups) read nxt; sel="claims.groups $nxt" ;;
  esac
  if try_selector "$sel" "consul-user"; then ok=true; break; fi
done
$ok || echo "WARN: no user binding created; check attribute keys via /v1/acl/token/self"

echo "== Final binding rules =="
consul acl binding-rule list -method keycloak-jwt
