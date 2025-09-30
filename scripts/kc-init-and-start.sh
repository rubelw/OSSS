#!/bin/sh
set -eu

# --- choose an import source safely -----------------------------------------
# Original export (read-only)
IMPORT_DIR_ORIG="${IMPORT_DIR:-/opt/keycloak/data/import}"
IMPORT_FILE_ORIG="${IMPORT_FILE:-$IMPORT_DIR_ORIG/10-OSSS.json}"
# Sanitized copy (may not exist yet)
SANITIZED_DIR="/opt/keycloak/data/tmp"
mkdir -p "$SANITIZED_DIR"
SANITIZED_IMPORT="${SANITIZED_DIR}/realm-import.json"
# Use sanitized file if it exists and is non-empty, else fall back to original
if [ -s "$SANITIZED_IMPORT" ]; then
  SRC_FILE="$SANITIZED_IMPORT"
else
  SRC_FILE="$IMPORT_FILE_ORIG"
fi

# --- simple logger to stderr to keep stdout clean for command substitutions ---
# (define BEFORE any use)
if ! command -v log >/dev/null 2>&1; then
  log() { printf "%s\n" "$*" >&2; }
fi

# ---------- Group helpers (define BEFORE first use) ----------
group_id_by_name_under() {
  # $1 realm, $2 parent_id (or empty for root), $3 name
  _realm="$1"; _parent="$2"; _name="$3"

  if [ -z "${_parent:-}" ]; then
    # ROOT LOOKUP: use search + path match to avoid pagination issues.
    # Return the id of the root group whose path is exactly "/<name>"
    /opt/keycloak/bin/kcadm.sh get "realms/$_realm/groups" \
      --server "$KC_BOOT_URL" --insecure \
      --fields id,name,path \
      -q "search=${_name}" -q first=0 -q max=2000 2>/dev/null \
    | jq -r '.[]? | select(.path=="/'"$_name"'") | .id' \
    | head -n1
  else
    # CHILD LOOKUP: fetch children with a large page to avoid pagination misses.
    /opt/keycloak/bin/kcadm.sh get "groups/$_parent/children" -r "$_realm" \
      --server "$KC_BOOT_URL" --insecure \
      --fields id,name \
      -q first=0 -q max=2000 2>/dev/null \
    | jq -r '.[]? | select(.name=="'"$_name"'") | .id' \
    | head -n1
  fi
}

ensure_group_path() {
  # $1 realm, $2 full path like /a/b/c (leading slash optional)
  realm="$1"; path="${2#/}"
  [ -z "$path" ] && { log "⚠️ Skipping empty group path"; return 0; }
  oldIFS=$IFS; IFS='/'; set -- $path; IFS=$oldIFS
  parent=""
  for seg in "$@"; do
    [ -z "$seg" ] && continue
    gid="$(group_id_by_name_under "$realm" "$parent" "$seg" || true)"
    if [ -z "${gid:-}" ]; then
      if [ -z "${parent:-}" ]; then
        /opt/keycloak/bin/kcadm.sh create "realms/$realm/groups" --server "$KC_BOOT_URL" --insecure -s "name=$seg" >/dev/null 2>&1 || true
        gid="$(group_id_by_name_under "$realm" "" "$seg" || true)"
      else
        /opt/keycloak/bin/kcadm.sh create "groups/$parent/children" -r "$realm" --server "$KC_BOOT_URL" --insecure -s "name=$seg" >/dev/null 2>&1 || true
        gid="$(group_id_by_name_under "$realm" "$parent" "$seg" || true)"
      fi
      [ -n "$gid" ] && log "   + ensured group '${seg}' (parentId=${parent:-root})"
    fi
    parent="$gid"
  done
}


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


REALM="${REALM:-OSSS}"

# kcadm config, URLs, origin …
export KCADM_CONFIG="${KCADM_CONFIG:-/tmp/kcadm.config}"
KC_BOOT_URL="http://127.0.0.1:${KC_HTTP_PORT}"
BASE_URL="${KC_HOSTNAME_URL:-https://${KC_HOSTNAME}:${KC_HTTPS_PORT}}"
ORIGIN="$(printf %s "$BASE_URL" | sed -E 's~/*$~~; s~^((https?)://[^/]+).*$~\1~')"

# --- Start Keycloak (DEV) and login BEFORE any kcadm usage ---
log "▶️  Starting bootstrap Keycloak (DEV)…"
/opt/keycloak/bin/kc.sh start-dev \
  --http-port="$KC_HTTP_PORT" \
  --hostname="$KC_HOSTNAME" \
  --log-level=info \
  >/tmp/kc-dev.log 2>&1 &
BOOT_PID=$!
trap 'kill "$BOOT_PID" 2>/dev/null || true; wait "$BOOT_PID" 2>/dev/null || true' EXIT
log "⏳ Waiting for Keycloak to accept kcadm credentials at $KC_BOOT_URL…"
until /opt/keycloak/bin/kcadm.sh config credentials \
  --server "$KC_BOOT_URL" --realm master \
  --user "$ADMIN_USER" --password "$ADMIN_PWD" --insecure >/dev/null 2>&1
do
  sleep 2
done
log "🔐 Logged into admin CLI."

# --- Ensure realm exists BEFORE any group ops ---
if /opt/keycloak/bin/kcadm.sh get "realms/$REALM" --realm master --server "$KC_BOOT_URL" --insecure >/dev/null 2>&1; then
  log "♻️  Realm '$REALM' exists."
else
  log "🆕 Creating empty realm '$REALM'…"
  /opt/keycloak/bin/kcadm.sh create realms --realm master --server "$KC_BOOT_URL" --insecure \
    -f - <<JSON >/dev/null
{"realm":"$REALM","enabled":true}
JSON
  log "Created new realm with id '$REALM'"
fi

# --- Build canonical group paths (parents-first) and ensure tree (NOW SAFE) ---
GROUP_PATHS_FILE="/tmp/canonical-group-paths.txt"
: > "$GROUP_PATHS_FILE"
# Prefer ORIGINAL export for path discovery if sanitized file not ready yet
SRC_FILE="$SANITIZED_IMPORT"
[ -s "$SRC_FILE" ] || SRC_FILE="$IMPORT_FILE_ORIG"

jq -r '
  def walkg($p):
    . as $g
    | select(type=="object")
    | (if ($g.path? and ($g.path|type)=="string" and ($g.path|length)>0)
         then $g.path
         else ($p + (if $p=="" then "" else "/" end) + ($g.name // ""))
       end) as $q
    | select($q != "")
    | $q,
      ( ($g.subGroups // [])[] | walkg($q) );
  (.groups // [])[] | walkg("")
' "$SRC_FILE" \
| sed -E 's#//+#/#g; s#^/+#/#' \
| awk 'NF' \
| awk -F/ '{print NF "\t"$0}' | sort -n | cut -f2- > "$GROUP_PATHS_FILE"
log "📚 Built canonical group path list ($(wc -l < "$GROUP_PATHS_FILE" | tr -d " ") paths)."
log "🌳 Ensuring group tree from canonical paths (parents first)…"
count=0
while IFS= read -r gp; do
  [ -z "$gp" ] && continue
  ensure_group_path "$REALM" "$gp"
  count=$((count+1))
  [ $((count % 25)) -eq 0 ] && log "   …created/verified $count group paths so far"
done < "$GROUP_PATHS_FILE"
log "✅ Group tree ensured."

# --- Remove stray root leaves when a canonical parent exists ---
log "🧹 Removing stray root groups that have a canonical parent in the export…"
# Build leaf -> canonical path map
awk -F/ '{print $NF "\t"$0}' "$GROUP_PATHS_FILE" | sort -u > /tmp/leaf2canon.tsv

# List root groups once
/opt/keycloak/bin/kcadm.sh get "realms/$REALM/groups" \
  --server "$KC_BOOT_URL" --insecure --fields id,name > /tmp/root-groups.json 2>/dev/null || true

jq -c '.[]? | {id, name}' /tmp/root-groups.json | while read -r row; do
  gid="$(printf '%s' "$row" | jq -r '.id')"
  gname="$(printf '%s' "$row" | jq -r '.name')"
  canon="$(awk -v n="$gname" -F"\t" '$1==n{print $2}' /tmp/leaf2canon.tsv | head -n1)"

  # Only act if the canonical path is NOT /<leaf> (i.e., it belongs under a parent)
  if [ -n "$canon" ] && [ "$canon" != "/$gname" ]; then
    parent="${canon%/*}"; parent="${parent:-/}"

    # Ensure parent chain exists
    ensure_group_path "$REALM" "$parent"

    # Resolve parent id by walking segments
    p="$parent"; p="${p#/}"
    pid=""
    oldIFS=$IFS; IFS='/' ; set -- $p ; IFS=$oldIFS
    for s in "$@"; do
      [ -z "$s" ] && continue
      pid="$(group_id_by_name_under "$REALM" "$pid" "$s" || true)"
    done

    if [ -n "$pid" ]; then
      # Check if the leaf exists under that parent
      existing="$(group_id_by_name_under "$REALM" "$pid" "$gname" || true)"
      if [ -z "$existing" ]; then
        # Create missing canonical leaf
        /opt/keycloak/bin/kcadm.sh create "groups/$pid/children" -r "$REALM" \
          --server "$KC_BOOT_URL" --insecure -s "name=$gname" >/dev/null 2>&1 || true
        log "   ➕ Created canonical '$canon'"
      fi
      # Now delete root stray
      /opt/keycloak/bin/kcadm.sh delete "groups/$gid" -r "$REALM" --server "$KC_BOOT_URL" --insecure >/dev/null 2>&1 || true
      log "   🗑️  Deleted stray root group '$gname' (moved to '$canon')"
    fi
  fi
done
log "✅ Root cleanup complete."


# --- Proceed with partialImport for non-group sections only (optional) ---
# If you still do sectioned imports, skip 'groups' section entirely.
section_import() {
  key="$1"
  [ "$key" = "groups" ] && { log "⏭️  Skipping groups section (handled manually)"; return 0; }
  body="/tmp/partial-${key}.json"
  jq -c --arg k "$key" '{ ifResourceExists:"SKIP", ($k):(.[$k] // []) }' "$SRC_FILE" > "$body"
  /opt/keycloak/bin/kcadm.sh create "realms/$REALM/partialImport" \
    --realm master --server "$KC_BOOT_URL" --insecure -f "$body" 2>"/tmp/partial-${key}.err" \
    || { log "  ⚠️  ${key} import failed:"; sed 's/^/    │ /' "/tmp/partial-${key}.err" >&2; }
}

# Example call order (without groups):
section_import clientScopes
section_import clients
section_import roles
# section_import groups  # intentionally skipped (groups handled above)
section_import users




# ---------- JSON helpers (jq-based) ----------

# json_first_id:
#   Reads JSON from stdin and extracts the first string value found for any "id" field,
#   regardless of its nesting level. This is useful when kcadm responses contain arrays
#   or nested objects and you just need the first matching id.
#   - Input: JSON from stdin
#   - Output: first id string found (one line), or nothing if no "id" field exists
#   Example:
#     echo '[{"id":"123"},{"id":"456"}]' | json_first_id
#     -> 123
json_first_id() {
  jq -r '..|objects|select(has("id"))|.id|strings' | head -n1
}

# scope_id_by_name:
#   Look up the ID of a client scope in a given realm by its name.
#
#   Arguments:
#     $1 – Realm name
#     $2 – Client scope name
#
#   Behavior:
#     • Queries Keycloak (via kcadm) for client scopes in the specified realm.
#     • Filters results with jq to match the exact scope name.
#     • Returns the first matching scope ID if found, or an empty string otherwise.
#     • Emits verbose log messages showing whether the scope was found or missing.
#
#   Example:
#     scope_id_by_name "OSSS" "roles"
#     -> 3c826b40-5b6b-49df-a73b-efb6b2ed0553
scope_id_by_name() {
  # $1 = realm, $2 = scope name
  local _realm="$1"
  local _scope_name="$2"
  local _id

  log "🔎 Looking up client scope '$_scope_name' in realm '$_realm'…"

  _id="$(/opt/keycloak/bin/kcadm.sh get client-scopes -r "$_realm" --server "$KC_BOOT_URL" --insecure \
           -q "name=$_scope_name" --fields id,name 2>/dev/null \
         | jq -r '.[]? | select(.name=="'"$_scope_name"'") | .id' \
         | head -n1 || true)"

  if [ -n "${_id:-}" ]; then
    log "✅ Found client scope '$_scope_name' in realm '$_realm' (id=$_id)"
  else
    log "⚠️  No client scope found with name '$_scope_name' in realm '$_realm'."
  fi

  printf %s "$_id"
}


# ensure_client_scope:
#   Ensure a client scope with the given name exists in a Keycloak realm.
#
#   Arguments:
#     $1 – Realm name
#     $2 – Client scope name
#
#   Behavior:
#     • Uses scope_id_by_name() to check if the client scope already exists.
#     • If the scope does not exist:
#         - Creates it with protocol "openid-connect" using kcadm.
#         - Re-checks to confirm successful creation and logs the new scope ID.
#         - Fails with error logging if creation was unsuccessful.
#     • If the scope already exists, logs and skips creation.
#     • Always returns the scope ID (stdout) on success, or exits with error code if creation fails.
#
#   Example:
#     ensure_client_scope "OSSS" "roles"
#     -> 3c826b40-5b6b-49df-a73b-efb6b2ed0553
ensure_client_scope() {
  local _realm="$1"
  local _scope_name="$2"
  local _id

  log "🔎 Checking if client scope '$_scope_name' exists in realm '$_realm'…"
  _id="$(scope_id_by_name "$_realm" "$_scope_name" || true)"

  if [ -z "${_id:-}" ]; then
    log "➕ Client scope '$_scope_name' does not exist. Creating…"
    if /opt/keycloak/bin/kcadm.sh create client-scopes -r "$_realm" --server "$KC_BOOT_URL" --insecure \
        -s "name=$_scope_name" -s protocol=openid-connect >/dev/null 2>&1
    then
      _id="$(scope_id_by_name "$_realm" "$_scope_name" || true)"
      if [ -n "${_id:-}" ]; then
        log "✅ Successfully created client scope '$_scope_name' (id=$_id)"
      else
        log "❌ Attempted to create client scope '$_scope_name' but could not retrieve its id."
        return 1
      fi
    else
      log "❌ Failed to create client scope '$_scope_name' in realm '$_realm'."
      return 1
    fi
  else
    log "ℹ️  Client scope '$_scope_name' already exists (id=$_id). Skipping create."
  fi

  printf %s "$_id"
}


# protocol_mapper_exists:
#   Check if a protocol mapper with a specific name exists in a given client scope.
#
#   Arguments:
#     $1 – Realm name
#     $2 – Client scope ID
#     $3 – Protocol mapper name (string to match by "name" field)
#
#   Behavior:
#     • Queries Keycloak for all protocol mappers attached to the client scope ID.
#     • Uses jq to search for a mapper object whose "name" matches the given name.
#     • Exits with success (0) if found, failure (non-zero) if not.
#     • Produces no stdout output, only a success/fail return code.
#
#   Example:
#     if protocol_mapper_exists "OSSS" "1234-5678-90" "realm roles"; then
#       echo "Mapper exists"
#     fi
protocol_mapper_exists() {
  /opt/keycloak/bin/kcadm.sh get "client-scopes/$2/protocol-mappers/models" -r "$1" --server "$KC_BOOT_URL" --insecure 2>/dev/null \
    | jq -e '.[]? | select(.name=="'"$3"'")' >/dev/null 2>&1
}

ensure_audience_mapper() {
  local _realm="$1"
  local _scope_id="$2"
  local _aud_client="$3"
  local _mapper_name="$4"

  log "🔎 Ensuring audience mapper '$_mapper_name' exists in client-scope id=$_scope_id (realm=$_realm, audience=$_aud_client)…"

  # First, check if it already exists
  if protocol_mapper_exists "$_realm" "$_scope_id" "$_mapper_name"; then
    log "✅ Audience mapper '$_mapper_name' already exists in scope id=$_scope_id. Skipping."
  else
    log "➕ Creating new audience mapper '$_mapper_name' in scope id=$_scope_id for audience client '$_aud_client'…"
    if /opt/keycloak/bin/kcadm.sh create "client-scopes/$_scope_id/protocol-mappers/models" \
         -r "$_realm" --server "$KC_BOOT_URL" --insecure -f - <<JSON >/dev/null 2>&1
{ "name":"$_mapper_name", "protocol":"openid-connect", "protocolMapper":"oidc-audience-mapper",
  "config":{
    "included.client.audience":"$_aud_client",
    "access.token.claim":"true",
    "id.token.claim":"false",
    "userinfo.token.claim":"false"
  }}
JSON
    then
      log "✅ Successfully created audience mapper '$_mapper_name' (scope id=$_scope_id, audience=$_aud_client)"
    else
      log "❌ Failed to create audience mapper '$_mapper_name' in scope id=$_scope_id (realm=$_realm)"
      return 1
    fi
  fi
}

# ensure_audience_mapper:
#   Ensure that a given audience protocol mapper exists in a client scope.
#   Audience mappers add a specific client as an "aud" (audience) claim in tokens issued under the scope.
#
#   Arguments:
#     $1 – Realm name (the Keycloak realm to target)
#     $2 – Client scope ID where the mapper should reside
#     $3 – Audience client ID (the client that will be included in the token's audience claim)
#     $4 – Mapper name (the identifier for this mapper inside the scope)
#
#   Behavior:
#     • Logs the operation being attempted.
#     • Calls `protocol_mapper_exists` to check if a mapper with the given name already exists in the client scope.
#     • If the mapper exists, logs and skips creation.
#     • If the mapper does not exist, creates a new OIDC audience protocol mapper (`oidc-audience-mapper`) with the
#       provided audience client, configured to include the audience in access tokens only.
#     • Logs success or failure of the creation attempt.
#     • Returns non-zero if the creation fails, so calling code can handle the error.
#
#   Example:
#     ensure_audience_mapper "OSSS" "1234-abcd" "osss-api" "audience: osss-api"
#
#   This ensures the scope with id `1234-abcd` has a mapper named "audience: osss-api" that injects
#   the `osss-api` client into the token's `aud` claim.
ensure_client_role_mapper_scope() {
  local _realm="$1"
  local _scope_name="$2"
  local _client_id="$3"
  local _mapper_name="$4"

  log "🔎 Ensuring client-role mapper '$_mapper_name' exists in scope '$_scope_name' (client=$_client_id, realm=$_realm)…"

  # Resolve (or create) the client scope ID
  sid="$(ensure_client_scope "$_realm" "$_scope_name")"
  if [ -z "${sid:-}" ]; then
    log "❌ Could not resolve or create client scope '$_scope_name' in realm '$_realm'"
    return 1
  fi
  log "ℹ️ Using client-scope id=$sid for '$_scope_name'"

  # Check if the mapper already exists
  if protocol_mapper_exists "$_realm" "$sid" "$_mapper_name"; then
    log "✅ Protocol mapper '$_mapper_name' already exists in scope '$_scope_name' (id=$sid). Skipping."
    return 0
  fi

  log "➕ Creating new protocol mapper '$_mapper_name' for client '$_client_id' in scope '$_scope_name'…"

  if /opt/keycloak/bin/kcadm.sh create "client-scopes/$sid/protocol-mappers/models" \
       -r "$_realm" --server "$KC_BOOT_URL" --insecure -f - \
       >/tmp/create-protocol-mapper.log 2>&1 <<JSON
{ "name":"$_mapper_name", "protocol":"openid-connect", "protocolMapper":"oidc-usermodel-client-role-mapper",
  "config":{
    "multivalued":"true",
    "access.token.claim":"true",
    "id.token.claim":"false",
    "userinfo.token.claim":"false",
    "usermodel.clientRoleMapping.clientId":"$_client_id",
    "claim.name":"resource_access.$_client_id.roles",
    "jsonType.label":"String"
  }}
JSON
  then
    log "✅ Successfully created protocol mapper '$_mapper_name' in scope '$_scope_name' (id=$sid)"
  else
    log "❌ Failed to create protocol mapper '$_mapper_name' in scope '$_scope_name' (realm=$_realm)"
    log "── kcadm stderr/stdout ──"
    sed 's/^/  │ /' /tmp/create-protocol-mapper.log >&2 || true
    log "── end ──"
    return 1
  fi
}


# ensure_default_scope_attached:
#   Ensures that a given client scope is included in the realm’s default default client scopes.
#
#   Arguments:
#     $1 – Realm name (the Keycloak realm to update)
#     $2 – Client scope name to attach (e.g., "roles", "profile", "email")
#
#   Behavior:
#     • Executes a `kcadm.sh update` against the realm to add the specified scope into
#       the `defaultDefaultClientScopes` array.
#     • The `+=$2` syntax appends the scope if it isn’t already attached.
#     • Redirects stdout and stderr to `/dev/null` to suppress normal command output.
#     • The `|| true` ensures the script continues even if the operation fails (e.g., scope already attached).
#
#   Purpose:
#     This guarantees that tokens issued in the realm always include claims from the specified scope by default,
#     unless explicitly overridden by a client configuration.
#
#   Example:
#     ensure_default_scope_attached "OSSS" "roles"
#     → Ensures the `roles` client scope is part of the default token scopes for the OSSS realm.
ensure_default_scope_attached() {
  /opt/keycloak/bin/kcadm.sh update "realms/$1" --server "$KC_BOOT_URL" --insecure \
    -s "defaultDefaultClientScopes+=$2" >/dev/null 2>&1 || true
}

# is_uuid36:
#   Checks whether a given string is a valid 36-character UUID in the canonical format.
#
#   Arguments:
#     $1 – The string to validate.
#
#   Behavior:
#     • Uses a shell case pattern to match the form:
#         8 hex chars - 4 hex chars - 4 hex chars - 4 hex chars - 12 hex chars
#       (total 36 characters, with 4 dashes in standard positions).
#     • If the string matches this UUID pattern, the function returns 0 (success).
#     • Otherwise, it returns 1 (failure).
#
#   Purpose:
#     Provides a lightweight check to distinguish real UUIDs from other identifiers
#     (e.g., names, nulls, or bad values) before using them in Keycloak commands.
#
#   Example:
#     is_uuid36 "123e4567-e89b-12d3-a456-426614174000" && echo "valid" || echo "invalid"
#     → prints "valid"
is_uuid36() {
  case "$1" in
    (????????-????-????-????-????????????) return 0 ;;
    (*) return 1 ;;
  esac
}


# ==================== Manual user import fallback ====================
# If users weren't created by partial import, create from JSON
log "🔍 Verifying that users exist; adding missing users if needed…"

# user_exists:
#   Checks whether a user with a given username exists in a specified Keycloak realm.
#
#   Arguments:
#     $1 – The realm name.
#     $2 – The username to check.
#
#   Behavior:
#     • Logs that it is checking for the user’s existence.
#     • Runs a Keycloak Admin CLI (`kcadm.sh`) query against the specified realm, filtering
#       by `username`.
#     • Requests only the `id` and `username` fields for efficiency.
#     • If the query returns a valid user object with a non-empty `id`, the function logs
#       success (✅) and returns **0** (true).
#     • If no valid `id` is found, the function logs failure (❌) and returns **1** (false).
#
#   Logging:
#     • Always logs the check attempt.
#     • On success, logs the realm, username, and user ID.
#     • On failure, logs that the user does not exist in the realm.
#
#   Purpose:
#     Provides a reliable way to check for user existence before attempting creation or
#     updates. This prevents duplicate accounts or unnecessary failures when bootstrapping
#     Keycloak with scripted imports.
#
#   Example:
#     user_exists OSSS "chief_technology_officer@osss.local"
#     → Logs whether this user exists in the "OSSS" realm and returns success/failure.
user_exists() {
  # $1 realm, $2 username
  _realm="$1"
  _user="$2"

  log "🔎 Checking if user '$_user' exists in realm '$_realm'…"

  # Query Keycloak for user
  raw_json="$(/opt/keycloak/bin/kcadm.sh get users -r "$_realm" --server "$KC_BOOT_URL" --insecure \
                -q "username=$_user" --fields id,username 2>/dev/null || true)"

  if printf '%s' "$raw_json" | jq -e '.[0]?.id? | strings' >/dev/null 2>&1; then
    uid="$(printf '%s' "$raw_json" | jq -r '.[0].id // empty')"
    log "✅ User '$_user' exists in realm '$_realm' (id=$uid)"
    return 0
  else
    log "❌ User '$_user' not found in realm '$_realm'"
    return 1
  fi
}


# Create users from JSON one-by-one
if [ -s /tmp/users-to-create.json ]; then
  while IFS= read -r ujson; do
    [ -z "$ujson" ] && continue
    uname="$(printf '%s' "$ujson" | jq -r '.username')"
    [ -z "$uname" ] && continue

    if user_exists "$REALM" "$uname"; then
      log "ℹ️  User '$uname' already exists. Skipping create."
      uid="$(/opt/keycloak/bin/kcadm.sh get users -r "$REALM" --server "$KC_BOOT_URL" --insecure -q "username=$uname" --fields id 2>/dev/null | json_first_id || true)"
    else
      # create without credentials/groups (kcadm supports JSON via -f -)
      printf '%s' "$ujson" | jq 'del(.credentials, .groups, .requiredActions)' \
        | /opt/keycloak/bin/kcadm.sh create users -r "$REALM" --server "$KC_BOOT_URL" --insecure -f - >/tmp/create-user.out 2>/dev/null || true
      # fetch id
      uid="$(/opt/keycloak/bin/kcadm.sh get users -r "$REALM" --server "$KC_BOOT_URL" --insecure -q "username=$uname" --fields id 2>/dev/null | json_first_id || true)"
      [ -n "$uid" ] && log "✅ Created user '$uname' (id=$uid)"
    fi

    [ -z "${uid:-}" ] && continue

    # set requiredActions if any
    req_json="$(printf '%s' "$ujson" | jq -c '.requiredActions | select(length>0)')"
    if [ -n "${req_json:-}" ]; then
      /opt/keycloak/bin/kcadm.sh update "users/$uid" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
        -s "requiredActions+=$(printf '%s' "$req_json")" >/dev/null 2>&1 || true
    fi

    # set password from first credential if present
    pass_val="$(printf '%s' "$ujson" | jq -r '.credentials[0]?.value // empty')"
    temp_flag="$(printf '%s' "$ujson" | jq -r '.credentials[0]?.temporary // false')"
    if [ -n "$pass_val" ] && [ "$pass_val" != "null" ]; then
      /opt/keycloak/bin/kcadm.sh set-password -r "$REALM" --server "$KC_BOOT_URL" --insecure \
        --userid "$uid" --new-password "$pass_val" $( [ "$temp_flag" = "true" ] && printf -- --temporary ) >/dev/null 2>&1 || true
    fi

    # join resolved canonical groups
    if [ -s "/tmp/user-groups/$uname.txt" ]; then
      sort -u "/tmp/user-groups/$uname.txt" | while IFS= read -r gpath; do
        [ -z "$gpath" ] && continue
        # resolve last segment id by walking path
        gpath_trim="${gpath#/}"
        oldIFS=$IFS; IFS='/'; set -- $gpath_trim; IFS=$oldIFS
        parent=""
        for seg in "$@"; do
          [ -z "$seg" ] && continue
          gid="$(group_id_by_name_under "$REALM" "$parent" "$seg" || true)"
          parent="$gid"
        done
        gid="$parent"
        if [ -n "${gid:-}" ]; then
          /opt/keycloak/bin/kcadm.sh update "users/$uid/groups/$gid" -r "$REALM" --server "$KC_BOOT_URL" --insecure -n >/dev/null 2>&1 || true
        fi
      done
    fi

  done < /tmp/users-to-create.json
else
  log "ℹ️  No users present in import JSON; skipping manual user creation."
fi
# =====================================================================

# ---------- Ensure 'roles' client scope + mappers ----------
CS_ROLES_ID="$(ensure_client_scope "$REALM" "roles")"
if ! protocol_mapper_exists "$REALM" "$CS_ROLES_ID" "realm roles"; then
  /opt/keycloak/bin/kcadm.sh create "client-scopes/$CS_ROLES_ID/protocol-mappers/models" -r "$REALM" --server "$KC_BOOT_URL" --insecure -f - <<'JSON' >/dev/null 2>&1 || true
{ "name":"realm roles","protocol":"openid-connect","protocolMapper":"oidc-usermodel-realm-role-mapper",
  "config":{"multivalued":"true","userinfo.token.claim":"true","id.token.claim":"true","access.token.claim":"true",
            "claim.name":"realm_access.roles","jsonType.label":"String"}}
JSON
fi
if ! protocol_mapper_exists "$REALM" "$CS_ROLES_ID" "client roles"; then
  /opt/keycloak/bin/kcadm.sh create "client-scopes/$CS_ROLES_ID/protocol-mappers/models" -r "$REALM" --server "$KC_BOOT_URL" --insecure -f - <<'JSON' >/dev/null 2>&1 || true
{ "name":"client roles","protocol":"openid-connect","protocolMapper":"oidc-usermodel-client-role-mapper",
  "config":{"multivalued":"true","userinfo.token.claim":"true","id.token.claim":"true","access.token.claim":"true",
            "usermodel.clientRoleMapping.clientId":"*",
            "claim.name":"resource_access.${client_id}.roles","jsonType.label":"String"}}
JSON
fi
ensure_default_scope_attached "$REALM" "roles"
ensure_default_scope_attached "$REALM" "profile"
ensure_default_scope_attached "$REALM" "email"

# ---------- Ensure 'account-audience' scope + audience mapper -> account ----------
CS_ACC_AUD_ID="$(ensure_client_scope "$REALM" "account-audience")"
if is_uuid36 "$CS_ACC_AUD_ID"; then
  /opt/keycloak/bin/kcadm.sh update "client-scopes/$CS_ACC_AUD_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s 'attributes."display.on.consent.screen"=false' \
    -s 'attributes."consent.screen.text"=' \
    -s 'attributes."include.in.token.scope"=true' >/dev/null 2>&1 || true
  ensure_audience_mapper "$REALM" "$CS_ACC_AUD_ID" "account" "audience account"
  ensure_default_scope_attached "$REALM" "account-audience"
else
  log "❌ Bad client-scope id for 'account-audience': $CS_ACC_AUD_ID"
fi

# ---------- OSSS custom scopes ----------
ensure_client_role_mapper_scope "$REALM" "osss-api-roles" "osss-api" "osss-api client roles"
CS_API_AUD_ID="$(ensure_client_scope "$REALM" "osss-api-audience")"
if is_uuid36 "$CS_API_AUD_ID"; then
  /opt/keycloak/bin/kcadm.sh update "client-scopes/$CS_API_AUD_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s 'attributes."include.in.token.scope"=true' >/dev/null 2>&1 || true
  ensure_audience_mapper "$REALM" "$CS_API_AUD_ID" "osss-api" "audience: osss-api"
fi

# ---------- Configure built-in account-console as SPA ----------
ACC_CONSOLE_ID=$(/opt/keycloak/bin/kcadm.sh get clients -r "$REALM" --server "$KC_BOOT_URL" --insecure -q clientId=account-console --fields id | json_first_id || true)
if [ -n "${ACC_CONSOLE_ID:-}" ]; then
  log "🛠  Configuring 'account-console' as public SPA…"
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

# ---------- CORS/webOrigins for security-admin-console + account ----------
# set_weborigins:
#   Normalizes the allowed CORS origins (`webOrigins`) for a specific Keycloak client.
#
#   Arguments:
#     $1 – The clientId of the target client (e.g., "account", "security-admin-console").
#
#   Behavior:
#     • Looks up the internal ID of the client in the current realm (`$REALM`) using
#       `kcadm.sh get`.
#     • If the client is not found, logs an informational message and skips.
#     • If found, updates the client’s `webOrigins` property in two steps:
#         1. Resets `webOrigins` to `["+"]` – allowing all origins (the Keycloak wildcard).
#         2. Adds the configured `$ORIGIN` (canonical realm hostname) as an explicit
#            additional allowed origin.
#
#   Logging:
#     • Logs if the client cannot be found.
#     • Does not explicitly log successful updates, but failures are silently tolerated with `|| true`.
#
#   Purpose:
#     Ensures that critical Keycloak clients (like the security admin console and account console)
#     have proper `webOrigins` set for cross-origin requests. This prevents CORS errors when the
#     realm’s UI or APIs are accessed from browsers.
#
#   Example:
#     set_weborigins "security-admin-console"
#     → Ensures that the `security-admin-console` client in `$REALM` accepts requests from `+` and `$ORIGIN`.
set_weborigins() {
  _CID="$(/opt/keycloak/bin/kcadm.sh get clients -r "$REALM" --server "$KC_BOOT_URL" --insecure -q clientId="$1" --fields id 2>/dev/null | json_first_id || true)"
  [ -z "$_CID" ] && { log "ℹ️  Client '$1' not found in realm '$REALM' (skipping)"; return 0; }
  /opt/keycloak/bin/kcadm.sh update "clients/$_CID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s 'webOrigins=["+"]' >/dev/null 2>&1 || true
  /opt/keycloak/bin/kcadm.sh update "clients/$_CID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s "webOrigins+=$ORIGIN" >/dev/null 2>&1 || true
}
set_weborigins "security-admin-console"
ACC_ID=$(/opt/keycloak/bin/kcadm.sh get clients -r "$REALM" --server "$KC_BOOT_URL" --insecure -q clientId=account --fields id | json_first_id || true)
if [ -n "${ACC_ID:-}" ]; then
  log "🔧 Normalizing webOrigins for 'account' client..."
  set +e
  /opt/keycloak/bin/kcadm.sh update "clients/$ACC_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure -s 'webOrigins=["+"]' >/dev/null 2>&1
  /opt/keycloak/bin/kcadm.sh update "clients/$ACC_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure -s "webOrigins+=$ORIGIN" >/dev/null 2>&1
  set -e
fi

# ---------- Fallback: ensure critical OSSS clients exist ----------
# ensure_client:
#   Ensures that a Keycloak client with the given clientId exists in the specified realm.
#
#   Arguments:
#     $1 – Realm name (e.g., "OSSS")
#     $2 – ClientId (the technical identifier for the client, e.g., "osss-api")
#     $3 – Client display name (friendly name for UI, e.g., "OSSS API")
#
#   Behavior:
#     • Looks up the client by its `clientId` using `kcadm.sh get`.
#     • If the client already exists:
#         - Logs that it was found and prints its ID.
#     • If the client does not exist:
#         - Logs a warning and attempts to create the client with default settings:
#             - protocol = `openid-connect`
#             - publicClient = false (confidential client)
#             - standardFlowEnabled = true (authorization code flow)
#             - directAccessGrantsEnabled = false
#             - serviceAccountsEnabled = false
#             - attributes."post.logout.redirect.uris" = `+` (allow any logout redirect)
#         - On success, logs confirmation and re-fetches the client’s internal ID.
#         - On failure, logs an error message.
#
#   Logging:
#     • Provides detailed info at every step:
#         - When checking existence.
#         - When creating a missing client.
#         - When confirming success/failure.
#         - When reporting the client’s internal ID.
#
#   Purpose:
#     Guarantees that critical OSSS clients (like `osss-api`, `osss-web`) exist in the realm,
#     even if the realm import or partial import skipped them. This ensures downstream services
#     always have required Keycloak clients available.
#
#   Example:
#     ensure_client "OSSS" "osss-api" "OSSS API"
#     → Creates or confirms the `osss-api` client in the OSSS realm, printing/logging its ID.
ensure_client() {
  _realm="$1"
  _clientId="$2"
  _name="$3"

  log "🔎 Ensuring client '$_clientId' exists in realm '$_realm'…"

  # Try to look up client ID
  cid="$(/opt/keycloak/bin/kcadm.sh get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
          -q clientId="$_clientId" --fields id | json_first_id || true)"

  if [ -z "${cid:-}" ]; then
    log "⚠️  Client '$_clientId' not found. Creating new client with name='$_name'…"
    if /opt/keycloak/bin/kcadm.sh create clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
         -s clientId="$_clientId" -s name="$_name" -s protocol=openid-connect \
         -s publicClient=false -s standardFlowEnabled=true -s directAccessGrantsEnabled=false \
         -s serviceAccountsEnabled=false -s 'attributes."post.logout.redirect.uris"=+' >/dev/null 2>&1; then
      log "✅ Successfully created client '$_clientId'"
      # Fetch id again
      cid="$(/opt/keycloak/bin/kcadm.sh get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
              -q clientId="$_clientId" --fields id | json_first_id || true)"
      [ -n "${cid:-}" ] && log "🔑 Client '$_clientId' has id=$cid"
    else
      log "❌ Failed to create client '$_clientId' in realm '$_realm'"
    fi
  else
    log "ℹ️  Client '$_clientId' already exists (id=$cid)."
  fi

  printf %s "$cid"
}

# --- Helper: assign ALL roles from one client to a user (id,name,clientRole,containerId) ---
assign_all_client_roles () {
  local _realm="$1" _uid="$2" _clientId="$3"

  # Resolve client UUID
  local _cid
  _cid="$(/opt/keycloak/bin/kcadm.sh get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
            -q clientId="$_clientId" --fields id 2>/dev/null | jq -r '.[0].id // empty')"
  if [ -z "${_cid:-}" ]; then
    log "⚠️  Client '$_clientId' not found in realm '$_realm'; skipping."
    return 0
  fi
  log "🔗 Found client '$_clientId' (id=$_cid)"

  # Build payload: id,name,clientRole,containerId required for client-role mapping
  local _roles_json _count
  _roles_json="$(/opt/keycloak/bin/kcadm.sh get "clients/$_cid/roles" -r "$_realm" --server "$KC_BOOT_URL" --insecure 2>/dev/null \
                  | jq -c '[.[]? | {id:.id,name:.name,clientRole:true,containerId:"'"$_cid"'"}]')"
  _count="$(printf '%s' "$_roles_json" | jq 'length')"
  if [ "${_count:-0}" -gt 0 ]; then
    log "➕ Assigning ${_count} roles from client '$_clientId'…"
    if printf '%s' "$_roles_json" \
       | /opt/keycloak/bin/kcadm.sh create "users/$_uid/role-mappings/clients/$_cid" \
           -r "$_realm" --server "$KC_BOOT_URL" --insecure -f - >/dev/null 2>&1; then
      log "✅ Assigned ${_count} roles from '$_clientId'"
    else
      log "⚠️ Failed assigning roles from client '$_clientId'"
    fi
  else
    log "⚠️ No roles found in client '$_clientId'"
  fi
}

# --- Helper: assign ALL REALM roles to a user (id,name) ---
assign_all_realm_roles () {
  local _realm="$1" _uid="$2"

  # Build payload: id + name is sufficient for realm-role mapping
  local _roles_json _count
  _roles_json="$(/opt/keycloak/bin/kcadm.sh get roles -r "$_realm" --server "$KC_BOOT_URL" --insecure 2>/dev/null \
                  | jq -c '[.[]? | {id:.id,name:.name}]')"
  _count="$(printf '%s' "$_roles_json" | jq 'length')"
  if [ "${_count:-0}" -gt 0 ]; then
    log "➕ Assigning ${_count} REALM roles in '$_realm'…"
    if printf '%s' "$_roles_json" \
       | /opt/keycloak/bin/kcadm.sh create "users/$_uid/role-mappings/realm" \
           -r "$_realm" --server "$KC_BOOT_URL" --insecure -f - >/dev/null 2>&1; then
      log "✅ Assigned ${_count} REALM roles"
    else
      log "⚠️ Failed assigning REALM roles"
    fi
  else
    log "⚠️ No REALM roles found in '$_realm'"
  fi
}

# Make sure osss-api and osss-web exist (import sometimes fails)
ensure_client "$REALM" "osss-api" "osss-api" >/dev/null
ensure_client "$REALM" "osss-web" "osss-web" >/dev/null

# Attach their audience/role scopes if present
# attach_scope_to_client:
#   Ensures that a specified client scope is attached to a given client in a Keycloak realm.
#
#   Arguments:
#     $1 – Realm name (e.g., "OSSS")
#     $2 – ClientId (technical identifier of the client, e.g., "osss-api")
#     $3 – Scope name (e.g., "osss-api-roles" or "account-audience")
#
#   Behavior:
#     • Looks up the client by its `clientId` in the specified realm:
#         - If found, logs the client’s ID.
#         - If not found, logs a warning and skips attaching the scope.
#     • Looks up the scope by name:
#         - If found, logs the scope’s ID.
#         - If not found, logs a warning and skips attaching the scope.
#     • If both client and scope exist:
#         - Updates the client, adding the scope to its `defaultClientScopes`.
#         - Logs success or failure depending on the outcome.
#
#   Logging:
#     • Provides detailed messages at each step:
#         - When searching for the client and whether it was found.
#         - When searching for the scope and whether it was found.
#         - Whether the scope was successfully attached to the client or not.
#
#   Purpose:
#     Guarantees that important client scopes (e.g., roles, audiences, API access scopes)
#     are correctly linked to Keycloak clients, ensuring tokens issued to those clients
#     include the required claims.
#
#   Example:
#     attach_scope_to_client "OSSS" "osss-api" "osss-api-roles"
#     → Ensures the `osss-api-roles` scope is attached to the `osss-api` client in realm OSSS.
attach_scope_to_client() {
  _realm="$1"
  _clientId="$2"
  _scope="$3"

  log "🔎 Attaching scope '$_scope' to client '$_clientId' in realm '$_realm'…"

  # Lookup client id
  cid="$(/opt/keycloak/bin/kcadm.sh get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
          -q clientId="$_clientId" --fields id | json_first_id || true)"

  if [ -z "${cid:-}" ]; then
    log "⚠️  Client '$_clientId' not found in realm '$_realm'. Skipping scope attach."
    return 0
  else
    log "✅ Found client '$_clientId' (id=$cid)"
  fi

  # Lookup scope id
  scope_id="$(scope_id_by_name "$_realm" "$_scope" || true)"
  if [ -z "${scope_id:-}" ]; then
    log "⚠️  Scope '$_scope' not found in realm '$_realm'. Skipping scope attach."
    return 0
  else
    log "✅ Found scope '$_scope' (id=$scope_id)"
  fi

  # Attach scope
  if /opt/keycloak/bin/kcadm.sh update "clients/$cid" -r "$_realm" --server "$KC_BOOT_URL" --insecure \
       -s "defaultClientScopes+=$_scope" >/dev/null 2>&1; then
    log "🎯 Successfully attached scope '$_scope' to client '$_clientId' (id=$cid)"
  else
    log "❌ Failed to attach scope '$_scope' to client '$_clientId' (id=$cid)"
  fi
}


attach_scope_to_client "$REALM" "osss-api" "osss-api-roles" || true
attach_scope_to_client "$REALM" "osss-api" "osss-api-audience" || true
attach_scope_to_client "$REALM" "osss-web" "osss-api-roles" || true
attach_scope_to_client "$REALM" "osss-web" "osss-api-audience" || true

# ===================== Ensure CTO user and full admin mappings in BOTH realms =====================
CTO_USER="chief_technology_officer@osss.local"
CTO_PASS="${CTO_PASSWORD:-password}"  # override with env if desired

# user_id_by_username:
#   Looks up a Keycloak user by their username within a given realm and returns the user’s ID.
#
#   Arguments:
#     $1 – Realm name (e.g., "OSSS" or "master")
#     $2 – Username to look up (e.g., "admin@osss.local")
#
#   Behavior:
#     • Sends a query to the Keycloak Admin REST API via `kcadm.sh`:
#         - Filters users by the exact username provided.
#         - Requests only the `id` and `username` fields.
#     • Pipes the result through the helper `json_first_id` to extract the first valid user ID.
#     • Provides verbose logging:
#         - Logs when lookup begins.
#         - Logs success if a user is found, including the resolved ID.
#         - Logs a warning if no user is found.
#
#   Output:
#     • On success: Prints the user’s Keycloak ID (UUID string) to stdout.
#     • On failure: Returns exit code `1` and logs a warning message.
#
#   Logging Examples:
#     🔎 Looking up user 'chief_technology_officer@osss.local' in realm 'OSSS'…
#     ✅ Found user 'chief_technology_officer@osss.local' in realm 'OSSS' (id=abc123-uuid-456)
#
#     🔎 Looking up user 'nonexistent' in realm 'OSSS'…
#     ⚠️  User 'nonexistent' not found in realm 'OSSS'
#
#   Purpose:
#     • Utility function used by higher-level scripts to reliably fetch user IDs by username.
#     • Required for user management tasks such as role assignment, password resets, or group membership updates.
#
#   Example Usage:
#     uid="$(user_id_by_username "OSSS" "chief_technology_officer@osss.local")"
#     if [ -n "$uid" ]; then
#       echo "User exists with id=$uid"
#     fi
user_id_by_username() {
  _realm="$1"
  _username="$2"

  log "🔎 Looking up user '$_username' in realm '$_realm'…"
  _id="$(/opt/keycloak/bin/kcadm.sh get users -r "$_realm" --server "$KC_BOOT_URL" --insecure \
          -q "username=$_username" --fields id,username 2>/dev/null | json_first_id || true)"

  if [ -n "${_id:-}" ]; then
    log "✅ Found user '$_username' in realm '$_realm' (id=$_id)"
    printf '%s\n' "$_id"
  else
    log "⚠️  User '$_username' not found in realm '$_realm'"
    return 1
  fi
}

# grant_admin_mappings:
#   Ensures a specific user (default: CTO_USER) exists in a Keycloak realm and has full
#   administrative privileges. This includes creating the user if necessary, setting their
#   password, and assigning all roles from critical admin-related clients.
#
#   Arguments:
#     $1 – Realm name (e.g., "OSSS" or "master")
#
#   Behavior:
#     • User existence:
#         - Checks if the target user exists in the realm.
#         - If missing, creates the user with username/email set to $CTO_USER.
#         - Logs whether the user was found, created, or if creation failed.
#
#     • Password management:
#         - Sets the user’s password using the $CTO_PASS environment variable.
#         - Logs success or failure of password assignment.
#
#     • Role assignment – realm-management:
#         - Looks up the `realm-management` client.
#         - Fetches all available roles from this client.
#         - Assigns every role to the user, granting them full realm administration rights.
#         - Logs the number of roles assigned or warns if none found.
#
#     • Role assignment – account and account-console:
#         - Looks up the `account` and `account-console` clients.
#         - Fetches all roles from each.
#         - Assigns them to the user so they can access administrative consoles cleanly.
#         - Logs whether roles were successfully assigned or skipped if clients/roles were missing.
#
#   Logging:
#     • Very verbose – traces each step:
#         - Checking/creating user
#         - Setting password
#         - Discovering clients (realm-management, account, account-console)
#         - Counting and assigning roles
#         - Completion or failure messages
#
#   Purpose:
#     Guarantees that a critical administrative user (e.g., a Chief Technology Officer account)
#     always exists with full privileges in both the `master` realm and the custom realm (like `OSSS`).
#     This is essential for bootstrap and emergency access to Keycloak admin features.
#
#   Example:
#     grant_admin_mappings "OSSS"
#     → Ensures CTO_USER exists in OSSS realm with all admin and console roles assigned.
#
#     grant_admin_mappings "master"
#     → Ensures CTO_USER exists in master realm with full admin access.
grant_admin_mappings () {
  _realm="$1"
  _user="${2:-$CTO_USER}"

  log "🔎 Checking for user $_user in realm $_realm…"
  _uid="$(user_id_by_username "$_realm" "$_user" || true)"
  if [ -z "${_uid:-}" ]; then
    log "➕ Creating user $_user in realm $_realm…"
    /opt/keycloak/bin/kcadm.sh create users -r "$_realm" --server "$KC_BOOT_URL" --insecure \
      -s "username=$_user" -s "email=$_user" -s enabled=true -s emailVerified=true \
      >/dev/null 2>&1 || log "⚠️ Failed to create user $_user"
    _uid="$(user_id_by_username "$_realm" "$_user" || true)"
    [ -n "${_uid:-}" ] && log "✅ Created user $_user with id $_uid" || :
  else
    log "ℹ️ User $_user already exists in $_realm with id $_uid"
  fi

  if [ -n "${_uid:-}" ]; then
    log "🔑 Setting password for user $_user in realm $_realm…"
    /opt/keycloak/bin/kcadm.sh set-password -r "$_realm" --server "$KC_BOOT_URL" --insecure \
      --userid "$_uid" --new-password "$CTO_PASS" --temporary=false >/dev/null 2>&1 \
      && log "✅ Password set for $_user" || log "⚠️ Failed to set password for $_user"

    # 1) Grant ALL REALM roles
    assign_all_realm_roles "$_realm" "$_uid"

    # 2) Grant ALL client roles from EVERY client in the realm
    client_count="$(/opt/keycloak/bin/kcadm.sh get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure 2>/dev/null | jq 'length')"
    log "🔎 Enumerating ${client_count:-0} clients in realm '$_realm' for role assignment…"
    /opt/keycloak/bin/kcadm.sh get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure 2>/dev/null \
      | jq -r '.[].clientId' \
      | sort -u \
      | while IFS= read -r _clientId; do
          [ -n "${_clientId:-}" ] || continue
          assign_all_client_roles "$_realm" "$_uid" "$_clientId"
        done

    log "🏁 Completed ALL role mappings for $_user in $_realm"
  else
    log "❌ Could not create/find user $_user in $_realm"
  fi
}

grant_admin_mappings master
# ==========================================================================

log "🛑 Stopping bootstrap Keycloak…"
kill "$BOOT_PID" || true
wait "$BOOT_PID" 2>/dev/null || true
trap - EXIT

# --- Build (once) with DB provider; runtime flags are ignored here by design ---
log "🔧 Building Keycloak with Postgres provider…"
/opt/keycloak/bin/kc.sh build --db=postgres

# --- Final prod server (PID 1). NOTE: no --import-realm (we already imported) ---
log "🚀 Starting Keycloak (prod)…"
exec /opt/keycloak/bin/kc.sh start \
  --http-enabled="$KC_HTTP_ENABLED" \
  --http-port="$KC_HTTP_PORT" \
  --https-port="$KC_HTTPS_PORT" \
  --https-certificate-file="$CERT" \
  --https-certificate-key-file="$KEYF" \
  --hostname-strict="$KC_HOSTNAME_STRICT" \
  --hostname="$KC_HOSTNAME" \
  --log-level=info
