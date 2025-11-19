#!/bin/sh
set -eu

export DEBUG_INIT=1 DEBUG_KC=1 DEBUG_WORKER=1

# ---- debug helpers ----------------------------------------------------------
ts() { date +"%H:%M:%S"; }
dbg() { [ "${DEBUG_INIT:-0}" = 1 ] && printf "%s %s\n" "$(ts)" "$*" >&2; }
dump_head() {  # dump_head <label> <file> [N]
  _lab="$1"; _f="$2"; _n="${3:-20}"
  if [ -s "$_f" ]; then
    printf "%s %s — first %s line(s):\n" "$(ts)" "$_lab" "$_n" >&2
    sed -n "1,${_n}p" "$_f" | sed 's/^/   │ /' >&2
  else
    printf "%s %s — (empty or missing)\n" "$(ts)" "$_lab" >&2
  fi
}

# Pretty jq counts with label
jq_count() {  # jq_count <label> <jqexpr> <file>
  _lab="$1"; _expr="$2"; _f="$3"
  _c="$(jq -r "$_expr" "$_f" 2>/dev/null || printf 0)"
  printf "%s %s: %s\n" "$(ts)" "$_lab" "$_c" >&2
}

# Limit very chatty worker logs
DEBUG_WORKER="${DEBUG_WORKER:-1}"          # 1 = child processes log details
DEBUG_BATCH="${DEBUG_BATCH:-1}"            # 1 = print batch directory samples
DEBUG_INIT="${DEBUG_INIT:-1}"              # 1 = print high-level debug in parent
DRY_RUN="${DRY_RUN:-0}"                    # 1 = don’t POST mappings, just log

# Build a mapping source that definitely contains groups[].clientRoles.
# If _src already has clientRoles, use it as-is.
# Otherwise, overlay clientRoles from the original export by matching group .path.
_prepare_mapping_source() {
  _src="$1"
  _orig="${2:-$IMPORT_FILE_ORIG}"

  # Fast path: _src already has clientRoles
  if jq -e '(.groups // []) | .. | objects | .clientRoles? | type=="object" and (length>0)' "$_src" >/dev/null 2>&1; then
    printf '%s\n' "$_src"; return 0
  fi

  # If no original, nothing we can do
  [ -s "$_orig" ] || { printf '%s\n' "$_src"; return 0; }

  tmp_map="/tmp/orig-cr-map.json"
  jq -c '
    def walkg($p):
      . as $g
      | (if ($g.path? and ($g.path|type)=="string" and ($g.path|length)>0)
           then $g.path
           else ($p + (if $p=="" then "" else "/" end) + ($g.name // ""))
         end) as $q
      | {path:$q, cr: ($g.clientRoles // {})}
      , ( ($g.subGroups // [])[] | walkg($q) );
    [ (.groups // [])[] | walkg("")
      | select((.cr|type)=="object" and (.cr|length)>0 and (.path|length)>0) ]
    | map({key:.path, value:.cr})
    | from_entries
  ' "$_orig" > "$tmp_map"

  tmp_out="/tmp/mapping-src.json"
  jq --slurpfile M "$tmp_map" '
    def path_of($g; $p):
      if ($g.path? | type)=="string" and ($g.path|length)>0
        then $g.path
        else $p + (if $p=="" then "" else "/" end) + ($g.name // "")
      end;

    def patch($p):
      . as $g
      | (path_of($g; $p)) as $q
      | (if ($M[0][$q]? | type)=="object" then (.clientRoles = $M[0][$q]) else . end)
      | ( .subGroups |= ( ( . // [] ) | map( patch($q) ) ) );

    (.groups |= ( ( . // [] ) | map( patch("") ) ))
  ' "$_src" > "$tmp_out"

  # inside _prepare_mapping_source(), right before: printf '%s\n' "$tmp_out"
  if [ "${DEBUG_INIT:-0}" = 1 ]; then
    jq_count "[map-src] objects with clientRoles" \
             '[..|objects|.clientRoles?|select(type=="object")]|length' "$tmp_out"
    # Top 10 clientIds referenced by clientRoles
    printf "%s [map-src] top clientIds:\n" "$(ts)" >&2
    jq -r '
      [..|objects|.clientRoles?|keys[]] | group_by(.) | map({k:.[0], n:length})
      | sort_by(-.n) | .[0:10][] | "\(.k)\t(\(.n))"
    ' "$tmp_out" 2>/dev/null | sed 's/^/   • /' >&2 || true
  fi

  printf '%s\n' "$tmp_out"
}


# === worker subcommand for parallel batch role mapping ===
if [ "${1:-}" = "__apply_one_batch__" ]; then
  shift
  command -v log >/dev/null 2>&1 || log() { printf "%s\n" "$*" >&2; }
  command -v _kc  >/dev/null 2>&1 || _kc() { /opt/keycloak/bin/kcadm.sh "$@" --config "$KCADM_BASE_CONFIG"; }
  [ "${DEBUG_WORKER:-0}" = 1 ] && log "[child] ok: SELF=$0 args=$*"

  # 👇 add this tiny helper so the worker doesn’t depend on later definitions
  _group_id_from_cache() {
    _cache="$1"; _path="$2"
    jq -r --arg p "$_path" '.[] | select(.path==$p) | .id' "$_cache"
  }

  # Worker-local helpers (independent from the rest of the file)

  _group_id_by_name_under() {
    _realm="$1"; _parent="$2"; _name="$3"
    if [ -z "${_parent:-}" ]; then
      _kc get groups -r "$_realm" --server "$KC_BOOT_URL" --insecure \
        --fields id,name,path -q "search=${_name}" -q first=0 -q max=2000 2>/dev/null \
      | jq -r '.[]? | select(.path=="/'"$_name"'") | .id' | head -n1
    else
      _kc get "groups/$_parent/children" -r "$_realm" --server "$KC_BOOT_URL" --insecure \
        --fields id,name -q first=0 -q max=2000 2>/dev/null \
      | jq -r '.[]? | select(.name=="'"$_name"'") | .id' | head -n1
    fi
  }

  _resolve_gid_by_path() {
    _realm="$1"; _path="${2#/}"
    [ -z "$_path" ] && { echo ""; return 1; }
    parent=""
    oldIFS=$IFS; IFS='/' ; set -- $_path ; IFS=$oldIFS
    for seg in "$@"; do
      [ -z "$seg" ] && continue
      parent="$(_group_id_by_name_under "$_realm" "$parent" "$seg" || true)"
      [ -z "$parent" ] && { echo ""; return 1; }
    done
    printf '%s\n' "$parent"
  }

  __worker_apply_one_batch() {
    _realm="$1"; _group_cache="$2"; _cache_dir="$3"; _batch_dir="$4"

    roles_file="$_batch_dir/roles.txt"
    if [ ! -f "$_batch_dir/path" ]; then log "⚠️  [child] batch dir missing path file: $_batch_dir"; return 0; fi
    if [ ! -f "$roles_file" ]; then log "⚠️  [child] batch dir missing roles.txt: $_batch_dir"; return 0; fi

    gpath="$(cat "$_batch_dir/path")"
    cid="$(cat "$_batch_dir/clientId")"

    [ -s "$roles_file" ] || return 0

    # New: try cache (with/without leading slash), then live walk
    gid="$(_group_id_from_cache "$_group_cache" "$gpath")"
    [ -z "$gid" ] && gid="$(_group_id_from_cache "$_group_cache" "${gpath#/}")"
    if [ -z "$gid" ]; then
      gid="$(_resolve_gid_by_path "$_realm" "$gpath")"
    fi
    if [ -z "$gid" ]; then
      [ "${DEBUG_WORKER:-0}" = 1 ] && {
        log "❌ [child] Cache+fallback miss for '$gpath' — sampling available paths:"
        _kc get groups -r "$_realm" --server "$KC_BOOT_URL" --insecure --fields path,id 2>/dev/null \
          | jq -r '.[].path' \
          | grep -F "$(printf '%s' "$gpath" | awk -F/ '{print $2}')" \
          | head -n 5 | sed 's/^/   • /' >&2 || true
      }
      return 0
    fi

    cuuid="$(awk -F'\t' -v C="$cid" '$1==C{print $2}' "$_cache_dir/client_map.tsv" | head -n1)"
    if [ -z "$cuuid" ]; then
      log "❌ [child] Unknown clientId '$cid' (skipping $gpath)"
      return 0
    fi

    roles_json="$_cache_dir/roles-$cuuid.json"
    if [ ! -s "$roles_json" ]; then
      log "❌ [child] No roles cache for client '$cid' ($cuuid) (skipping $gpath)"
      return 0
    fi

    wanted="$(sort -u "$roles_file" | jq -R -s 'split("\n") | map(select(length>0))')"

    body="$_batch_dir/body.json"
    jq -c --argjson wanted "$wanted" '
      [ .[] | select(.name as $n | $wanted | index($n)) | {id,name} ]
    ' "$roles_json" >"$body"

    # --- DEBUG/DRY-RUN (worker) ---
    command -v ts  >/dev/null 2>&1 || ts(){ date +"%H:%M:%S"; }
    command -v log >/dev/null 2>&1 || log(){ printf "%s\n" "$*" >&2; }

    [ "${DEBUG_WORKER:-0}" = 1 ] && {
      cnt="$(jq 'length' "$body")"
      printf "%s [child] POST groups/%s/role-mappings/clients/%s  roles=%s  path=%s  clientId=%s\n" \
        "$(ts)" "$gid" "$cuuid" "$cnt" "$gpath" "$cid" >&2
      jq -r '.[].name' "$body" | head -n 10 | sed 's/^/   • /' >&2
    }

    if [ "${DRY_RUN:-0}" = "1" ]; then
      log "👟 [child] DRY_RUN=1 — skipping POST for group '$gpath' client '$cid'"
      return 0
    fi



    if [ "$(jq 'length' "$body")" -eq 0 ]; then
      log "⚠️  [child] No matching roles under client '$cid' for group '$gpath' (skip)"
      return 0
    fi

    if _kc create "groups/$gid/role-mappings/clients/$cuuid" \
         -r "$_realm" --server "$KC_BOOT_URL" --insecure -f "$body" >/dev/null 2>&1
    then
      cnt="$(jq 'length' "$body")"
      log "🔐 [child] Mapped $cnt role(s) from client '$cid' to group '$gpath'"
    else
      log "❌ [child] Failed batch mapping for client '$cid' to group '$gpath'"
      return 1
    fi
  }

  __worker_apply_one_batch "$@"
  exit 0
fi


# --- early env so KC_BOOT_URL is safe before any kcadm usage -----------------
# (set these BEFORE any call that references KC_* vars)
KC_HTTP_PORT="${KC_HTTP_PORT:-8080}"
KC_HOSTNAME="${KC_HOSTNAME:-keycloak.local}"
KC_HTTPS_PORT="${KC_HTTPS_PORT:-8443}"
KC_BOOT_URL="${KC_BOOT_URL:-http://127.0.0.1:${KC_HTTP_PORT}}"

# --- choose an import source safely -----------------------------------------

# Original export (read-only)
IMPORT_DIR_ORIG="${IMPORT_DIR:-/opt/keycloak/data/import}"
IMPORT_FILE_ORIG="${IMPORT_FILE:-$IMPORT_DIR_ORIG/10-OSSS.json}"
# Sanitized copy (may not exist yet)
SANITIZED_DIR="/opt/keycloak/data/tmp"
KCADM_PARALLEL=8   # try 2–6 depending on Keycloak/server headroom
DEBUG_KC=1          # set to 1 for very verbose
KCADM_PARALLEL_DEEP=16
KCADM_PAGE_SIZE=10000
ROLE_CREATE_PAR=24


# ---- kcadm config isolation ----
KCADM_CONFIG_DIR="$(mktemp -d)"
KCADM_BASE_CONFIG="$KCADM_CONFIG_DIR/base.config"
export KCADM_BASE_CONFIG KCADM_CONFIG_DIR

# NOTE: we will log in to this config *after* Keycloak is up.


_kc() {  # _kc <args...>
  /opt/keycloak/bin/kcadm.sh "$@" --config "$KCADM_BASE_CONFIG"
}


_kc_base() {
  # Wrapper to echo commands when DEBUG_KC=1
  if [ "${DEBUG_KC:-0}" = "1" ]; then
    echo "+ kcadm $*" >&2
  fi
  /opt/keycloak/bin/kcadm.sh "$@" --config "$KCADM_BASE_CONFIG"
}


mkdir -p "$SANITIZED_DIR"
SANITIZED_IMPORT="${SANITIZED_DIR}/realm-import.json"
# Use sanitized file if it exists and is non-empty, else fall back to original
if [ -s "$SANITIZED_IMPORT" ]; then
  SRC_FILE="$SANITIZED_IMPORT"
else
  SRC_FILE="$IMPORT_FILE_ORIG"
fi

# --- robust attach of DEFAULT client-scope, portable across KC versions ---
_attach_default_scope() { # _attach_default_scope <realm> <clientUUID> <scopeId> <scopeName>
  _realm="$1"; _cuid="$2"; _sid="$3"; _sname="$4"

  # 1) Newer kcadm (collection POST w/ id in body)
  if _kc create "clients/${_cuid}/default-client-scopes" -r "$_realm" --server "$KC_BOOT_URL" --insecure \
       -s "id=${_sid}" >/dev/null 2>&1; then
    log "🎯 attached DEFAULT scope '${_sname}' (collection POST)"
    return 0
  fi

  # 2) Older kcadm (subresource POST with scopeId in path)
  if _kc create "clients/${_cuid}/default-client-scopes/${_sid}" -r "$_realm" --server "$KC_BOOT_URL" --insecure \
       >/dev/null 2>&1; then
    log "🎯 attached DEFAULT scope '${_sname}' (subresource POST)"
    return 0
  fi

  # 3) Admin REST fallback: PUT subresource (treat 204/409 as success)
  CURL_INSECURE=""; case "$KC_BOOT_URL" in https://*) CURL_INSECURE="-k" ;; esac
  token="$(curl -sS $CURL_INSECURE -X POST \
            -H 'Content-Type: application/x-www-form-urlencoded' \
            --data "client_id=admin-cli&username=$ADMIN_USER&password=$ADMIN_PWD&grant_type=password" \
            "$KC_BOOT_URL/realms/master/protocol/openid-connect/token" | jq -r '.access_token')"
  [ -z "$token" -o "$token" = "null" ] && { log "⚠️  attach fallback: no admin token"; return 1; }

  http=$(curl -sS $CURL_INSECURE -o /dev/null -w "%{http_code}" \
          -X PUT "$KC_BOOT_URL/admin/realms/${_realm}/clients/${_cuid}/default-client-scopes/${_sid}" \
          -H "Authorization: Bearer $token")
  case "$http" in
    204|409) log "🎯 attached DEFAULT scope '${_sname}' (curl PUT http=$http)"; return 0 ;;
    *)       log "⚠️  attach '${_sname}' failed (curl PUT http=$http)"; return 1 ;;
  esac
}


# === ensure DEFAULT client-scopes from import JSON (camelCase + snake_case) ===
ensure_defaults_from_export_v2() {
  local realm="$REALM" server="$KC_BOOT_URL" src="${SRC_FILE:-}"
  if [ -z "${src:-}" ] || [ ! -f "$src" ]; then
    log "⚠️  ensure_defaults_from_export_v2: SRC_FILE not set or missing"; return 0
  fi
  if ! jq -e . "$src" >/dev/null 2>&1; then
    log "⚠️  ensure_defaults_from_export_v2: SRC_FILE is not valid JSON"; return 0
  fi

  log "🔎 Scanning import JSON for clients with default scopes…"

  # For each client, read defaultClientScopes (camel) OR default_client_scopes (snake)
  jq -r '
    .clients // []
    | map({cid: (.clientId // ""), defs: ((.defaultClientScopes // .default_client_scopes // []) | unique) })
    | map(select(.cid != "" and (.defs | length) > 0))
    | .[] | [.cid, (.defs | join(","))] | @tsv
  ' "$src" 2>/dev/null \
  | while IFS=$'\t' read -r clientId scopes_csv; do
      [ -z "${clientId:-}" ] && continue

      # Resolve client UUID
      local CUID="$(_kc get clients -r "$realm" --server "$server" --insecure -q clientId="$clientId" --fields id | jq -r '.[0].id // empty')"
      if [ -z "${CUID:-}" ]; then
        log "⚠️  client '${clientId}' not found; skipping"; continue
      fi

      # Iterate scopes
      IFS=',' read -ra SCOPES_ARR <<< "${scopes_csv:-}"
      for s in "${SCOPES_ARR[@]}"; do
        s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"  # trim
        [ -z "$s" ] && continue

        # Ensure the scope exists (use ensure_client_scope if present; otherwise resolve)
        local SID=""
        if command -v ensure_client_scope >/dev/null 2>&1; then
          SID="$(ensure_client_scope "$realm" "$s" || true)"
        fi
        if [ -z "${SID:-}" ]; then
          SID="$(
            _kc get client-scopes -r "$realm" --server "$server" --insecure --fields id,name 2>/dev/null \
              | jq -r --arg n "$s" '.[] | select(.name==$n) | .id' | head -n1
          )"
        fi
        if [ -z "${SID:-}" ]; then
          log "⚠️  could not ensure/resolve scope '${s}'; skipping attach for client '${clientId}'"
          continue
        fi

        # Special case: for groups-claim, ensure the group-membership mapper
        if [ "$s" = "groups-claim" ]; then
          if ! _kc get "client-scopes/${SID}/protocol-mappers/models" -r "$realm" --server "$server" --insecure 2>/dev/null \
            | jq -e '[.[]? | select(.protocolMapper=="oidc-group-membership-mapper")] | length>0' >/dev/null; then
            _kc create "client-scopes/${SID}/protocol-mappers/models" -r "$realm" --server "$server" --insecure \
              -s name=groups -s protocol=openid-connect -s protocolMapper=oidc-group-membership-mapper \
              -s 'config."full.path"=false' -s 'config."id.token.claim"=true' \
              -s 'config."access.token.claim"=true' -s 'config."userinfo.token.claim"=true' \
              -s 'config."claim.name"=groups' >/dev/null 2>&1 \
              && log "✅ added group-membership mapper to 'groups-claim'" \
              || log "⚠️  failed to add group-membership mapper to 'groups-claim'"
          fi
        fi

        # Attach as DEFAULT client-scope if missing
        if ! _kc get "clients/${CUID}/default-client-scopes" -r "$realm" --server "$server" --insecure 2>/dev/null \
          | jq -e --arg id "$SID" --arg n "$s" '.[] | select(.id==$id or .name==$n)' >/dev/null; then
          if _attach_default_scope "$realm" "$CUID" "$SID" "$s"; then
            : # success already logged
          else
            log "⚠️  failed to attach DEFAULT scope '${s}' to client '${clientId}'"
          fi
        else
          log "ℹ️  '${s}' already present in DEFAULT client-scopes for '${clientId}'"
        fi
      done
    done
}


# --- early debug helpers (must be defined before first use) ---

# === ensure default client-scopes from import JSON ==============================
# For each client in $SRC_FILE that declares "defaultClientScopes": [...],
# ensure each of those scopes exists and is attached as a DEFAULT client-scope.
ensure_defaults_from_export() {
  local realm="$REALM" server="$KC_BOOT_URL"
  local src="${SRC_FILE:-}"
  if [ -z "${src:-}" ] || [ ! -f "$src" ]; then
    log "⚠️  ensure_defaults_from_export: SRC_FILE not set or missing"; return 0
  fi
  if ! jq -e . "$src" >/dev/null 2>&1; then
    log "⚠️  ensure_defaults_from_export: SRC_FILE is not valid JSON"; return 0
  fi

  log "🔎 Scanning import JSON for clients with defaultClientScopes…"

  # Iterate clients that declare defaultClientScopes
  jq -r '
    .clients // [] | map(select((.defaultClientScopes // []) | length > 0)) |
    .[] | @tsv "\(.clientId)\t\(.defaultClientScopes | join(","))"
  ' "$src" 2>/dev/null \
  | while IFS=$'\t' read -r clientId scopes_csv; do
      [ -z "${clientId:-}" ] && continue
      local CUID="$(_kc get clients -r "$realm" --server "$server" --insecure -q clientId="$clientId" --fields id | jq -r '.[0].id // empty')"
      if [ -z "${CUID:-}" ]; then
        log "⚠️  client '${clientId}' not found; skipping"; continue
      fi

      IFS=',' read -ra SCOPES_ARR <<< "${scopes_csv:-}"
      for s in "${SCOPES_ARR[@]}"; do
        # trim whitespace
        s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"
        [ -z "$s" ] && continue

        # Ensure the scope exists (reuse ensure_client_scope if present)
        local SID=""
        if command -v ensure_client_scope >/dev/null 2>&1; then
          SID="$(ensure_client_scope "$realm" "$s" || true)"
        fi
        if [ -z "${SID:-}" ]; then
          SID="$(
            _kc get client-scopes -r "$realm" --server "$server" --insecure --fields id,name 2>/dev/null \
              | jq -r --arg n "$s" '.[] | select(.name==$n) | .id' | head -n1
          )"
        fi
        if [ -z "${SID:-}" ]; then
          log "⚠️  scope '$s' could not be ensured; skipping attach for client '${clientId}'"
          continue
        fi

        # Attach as DEFAULT client-scope if missing
        if ! _kc get "clients/${CUID}/default-client-scopes" -r "$realm" --server "$server" --insecure 2>/dev/null \
          | jq -e --arg id "$SID" --arg n "$s" '.[] | select(.id==$id or .name==$n)' >/dev/null; then
          if _kc create "clients/${CUID}/default-client-scopes/${SID}" -r "$realm" --server "$server" --insecure >/dev/null 2>&1; then
            log "🎯 attached DEFAULT scope '${s}' to client '${clientId}'"
          else
            log "⚠️  failed to attach DEFAULT scope '${s}' to client '${clientId}'"
          fi
        else
          log "ℹ️  '${s}' already present in DEFAULT client-scopes for '${clientId}'"
        fi

        # Special case: ensure groups-claim has the group-membership mapper
        if [ "$s" = "groups-claim" ]; then
          if ! _kc get "client-scopes/${SID}/protocol-mappers/models" -r "$realm" --server "$server" --insecure 2>/dev/null \
            | jq -e '[.[]? | select(.protocolMapper=="oidc-group-membership-mapper")] | length>0' >/dev/null; then
            _kc create "client-scopes/${SID}/protocol-mappers/models" -r "$realm" --server "$server" --insecure \
              -s name=groups -s protocol=openid-connect -s protocolMapper=oidc-group-membership-mapper \
              -s 'config."full.path"=false' -s 'config."id.token.claim"=true' \
              -s 'config."access.token.claim"=true' -s 'config."userinfo.token.claim"=true' \
              -s 'config."claim.name"=groups' >/dev/null 2>&1 \
              && log "✅ added group-membership mapper to 'groups-claim'" \
              || log "⚠️  failed to add group-membership mapper to 'groups-claim'"
          fi
        fi
      done
    done
}
# ================================================================================
command -v ts  >/dev/null 2>&1 || ts(){ date +"%H:%M:%S"; }
command -v log >/dev/null 2>&1 || log(){ printf "%s %s\n" "$(ts)" "$*" >&2; }
command -v dump_head >/dev/null 2>&1 || dump_head(){
  _label="$1"; _file="$2"; _n="${3:-40}"
  printf "%s %s — first %s line(s):\n" "$(ts)" "$_label" "$_n" >&2
  if [ -s "$_file" ]; then head -n "$_n" "$_file" | sed 's/^/   │ /' >&2; else echo "   │ (missing: $_file)" >&2; fi
}

# --- JSON normalization: strip UTF-8 BOM + CRLF into a clean copy ---
normalize_json(){
  in="$1"; out="$2"
  # strip BOM only on first line; strip CR on all lines
  awk 'NR==1{sub(/^\xef\xbb\xbf/,"")} {sub(/\r$/,""); print}' "$in" > "$out"
}

# --- visibility: which file are we importing from, and does it have groups-claim? ---
echo "$(ts) [import-src] SRC_FILE=$SRC_FILE" >&2
dump_head "[import-src] head of SRC_FILE" "$SRC_FILE" 12

jq '{
      clientScopes_cnt: (.clientScopes // [] | length),
      has_groups_claim: ((.clientScopes // []) | map(.name) | index("groups-claim")) != null,
      groups_claim_mappers: ((.clientScopes // []) | map(select(.name=="groups-claim")) | .[0].protocolMappers // [])
    }' "$SRC_FILE" 2>/dev/null || echo "$(ts) [import-src] jq failed to parse SRC_FILE" >&2

# --- simple logger to stderr to keep stdout clean for command substitutions ---
# (define BEFORE any use)
if ! command -v log >/dev/null 2>&1; then
  log() { printf "%s\n" "$*" >&2; }
fi


# --- Group helpers ---
_group_id_by_name_under() {
  _realm="$1"; _parent="$2"; _name="$3"
  if [ -z "${_parent:-}" ]; then
    _kc get groups -r "$_realm" --server "$KC_BOOT_URL" --insecure \
      --fields id,name,path -q "search=${_name}" -q first=0 -q max=2000 2>/dev/null \
    | jq -r '.[]? | select(.path=="/'"$_name"'") | .id' | head -n1
  else
    _kc get "groups/$_parent/children" -r "$_realm" --server "$KC_BOOT_URL" --insecure \
      --fields id,name -q first=0 -q max=2000 2>/dev/null \
    | jq -r '.[]? | select(.name=="'"$_name"'") | .id' | head -n1
  fi
}

# ✅ Back-compat alias for existing callers:
group_id_by_name_under() { _group_id_by_name_under "$@"; }


# NEW: walk /a/b/c using live lookups (used if cache misses)
_resolve_gid_by_path() {
  _realm="$1"; _path="${2#/}"
  [ -z "$_path" ] && { echo ""; return 1; }
  parent=""
  oldIFS=$IFS; IFS='/' ; set -- $_path ; IFS=$oldIFS
  for seg in "$@"; do
    [ -z "$seg" ] && continue
    parent="$(_group_id_by_name_under "$_realm" "$parent" "$seg" || true)"
    [ -z "$parent" ] && { echo ""; return 1; }
  done
  printf '%s\n' "$parent"
}

# Create any client roles that are referenced in mapping source but missing in KC
_create_missing_client_roles() {
  _realm="$1"; _src="$2"
  log "[create-roles] Ensuring client roles exist for referenced (clientId, role) pairs…"

  # Build unique pairs: clientId \t roleName
  tmp_pairs="/tmp/mapping-role-pairs.tsv"
  jq -r '
    def walkg($p):
      . as $g
      | (if ($g.path? and ($g.path|type)=="string" and ($g.path|length)>0)
           then $g.path
           else ($p + (if $p=="" then "" else "/" end) + ($g.name // ""))
         end) as $q
      | {path:$q, cr: ($g.clientRoles // {})}
      , ( ($g.subGroups // [])[] | walkg($q) );
    (.groups // [])[] | walkg("")
    | select(.cr != null)
    | .cr
    | to_entries[] as $e
    | $e.key as $client
    | $e.value[] as $role
    | [$client, $role] | @tsv
  ' "$_src" | sort -u >"$tmp_pairs"

  # Resolve each clientId -> uuid once, cache roles list once per client
  while IFS=$'\t' read -r cid rname; do
    [ -n "$cid$rname" ] || continue
    cuuid="$(_kc get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
               -q "clientId=$cid" --fields id 2>/dev/null | jq -r '.[0].id // empty')"
    if [ -z "$cuuid" ]; then
      log "[create-roles] ⚠️  clientId '$cid' not found; skipping role '$rname'"
      continue
    fi

    # Check if role exists
    if _kc get "clients/$cuuid/roles-by-name/$rname" -r "$_realm" --server "$KC_BOOT_URL" --insecure >/dev/null 2>&1; then
      [ "${DEBUG_INIT:-0}" = 1 ] && log "[create-roles] exists  cid=$cid  role=$rname"
      continue
    fi

    # Create role
    if _kc create "clients/$cuuid/roles" -r "$_realm" --server "$KC_BOOT_URL" --insecure \
         -s name="$rname" >/dev/null 2>&1; then
      log "[create-roles] ➕ created  cid=$cid  role=$rname"
    else
      log "[create-roles] ❌ failed   cid=$cid  role=$rname"
    fi
  done < "$tmp_pairs"
}

# Fast path: create missing client roles using raw REST API + curl in parallel
ensure_client_roles_from_mapping_curl() {
  _realm="$1"; _cache_dir="$2"; _map_src="$3"
  log "[roles] (curl) Ensuring client roles exist (parallel=${ROLE_CREATE_PAR:-24})…"

  # 0) a2a token once
  CURL_INSECURE=""
  case "$KC_BOOT_URL" in https://*) CURL_INSECURE="-k" ;; esac
  token="$(curl -sS $CURL_INSECURE -X POST \
            -H 'Content-Type: application/x-www-form-urlencoded' \
            --data "client_id=admin-cli&username=$ADMIN_USER&password=$ADMIN_PWD&grant_type=password" \
            "$KC_BOOT_URL/realms/master/protocol/openid-connect/token" | jq -r '.access_token')"
  if [ -z "$token" ] || [ "$token" = "null" ]; then
    log "[roles] ERROR: could not obtain admin token from $KC_BOOT_URL"; return 1
  fi

  # 1) extract wanted pairs: clientId \t roleName
  want="/tmp/wanted-client-roles.tsv"
  jq -r '
    def walkg($p):
      . as $g
      | (if ($g.path? and ($g.path|type)=="string" and ($g.path|length)>0)
           then $g.path
           else ($p + (if $p=="" then "" else "/" end) + ($g.name // ""))
         end) as $q
      | {path:$q, cr: ($g.clientRoles // {})}
      , ( ($g.subGroups // [])[] | walkg($q) );
    (.groups // [])[] | walkg("")
    | .cr | to_entries[] | [.key, (.value[])] | @tsv
  ' "$_map_src" | sort -u >"$want"

  # 2) per client: compute missing roles and create in parallel with curl
  awk -F'\t' '{print $1}' "$want" | sort -u | while read -r cid; do
    [ -z "$cid" ] && continue
    cuuid="$(awk -F'\t' -v C="$cid" '$1==C{print $2}' "$_cache_dir/client_map.tsv" | head -n1)"
    if [ -z "$cuuid" ]; then
      log "[roles] WARN: mapping references clientId '$cid' not present in realm '$_realm' — skipping"
      continue
    fi

    rfile="$_cache_dir/roles-$cuuid.json"
    [ -s "$rfile" ] || printf '[]' > "$rfile"
    have_file="/tmp/have-$cuuid.txt"
    jq -r '.[].name' "$rfile" | sort -u > "$have_file"

    want_file="/tmp/want-$cuuid.txt"
    awk -F'\t' -v C="$cid" '$1==C{print $2}' "$want" | sort -u > "$want_file"

    miss_file="/tmp/miss-$cuuid.txt"
    comm -13 "$have_file" "$want_file" > "$miss_file" || true
    M=$(wc -l < "$miss_file" | tr -d ' ')
    if [ "$M" -eq 0 ]; then
      printf "%s [roles] client %-24s already has all referenced roles\n" "$(ts)" "$cid" >&2
      continue
    fi
    printf "%s [roles] client %-24s create %s missing role(s)\n" "$(ts)" "$cid" "$M" >&2

    export KC_BOOT_URL token CURL_INSECURE
    export REALM="$_realm" CUUID="$cuuid" CID="$cid"
    # Parallel POSTs (one curl per role name)
    xargs -r -n1 -P "${ROLE_CREATE_PAR:-24}" -I@ sh -c '
      rn="$1"
      http=$(curl -sS $CURL_INSECURE -o /dev/null -w "%{http_code}" \
              -X POST "$KC_BOOT_URL/a2a/realms/$REALM/clients/$CUUID/roles" \
              -H "Authorization: Bearer $token" \
              -H "Content-Type: application/json" \
              --data "{\"name\":\"$rn\"}")
      # 201=created, 409=already exists (race)
      if [ "$http" != "201" ] && [ "$http" != "409" ]; then
        echo "$(date +%H:%M:%S) [create-roles] WARN http $http cid=$CID role=$rn" >&2
      else
        [ "$http" = "201" ] && echo "$(date +%H:%M:%S) [create-roles] ➕ created  cid=$CID  role=$rn" >&2
      fi
    ' sh < "$miss_file"

    # refresh cache for this client (so mapping picks up the new IDs)
    curl -sS $CURL_INSECURE -H "Authorization: Bearer $token" \
      "$KC_BOOT_URL/admin/realms/$_realm/clients/$cuuid/roles?first=0&max=5000" \
    | jq -c '[ .[] | {id,name} ]' > "$rfile"
    rc="$(jq 'length' "$rfile" 2>/dev/null || printf 0)"
    printf "%s [cache] client %-24s → %s role(s)\n" "$(ts)" "$cid" "$rc" >&2
  done
}

ensure_group_path() {
  realm="$1"; path="${2#/}"
  [ -z "$path" ] && { log "⚠️ Skipping empty group path"; return 0; }
  oldIFS=$IFS; IFS='/'; set -- $path; IFS=$oldIFS
  parent=""
  for seg in "$@"; do
    [ -z "$seg" ] && continue
    gid="$(group_id_by_name_under "$realm" "$parent" "$seg" || true)"
    if [ -z "${gid:-}" ]; then
      if [ -z "${parent:-}" ]; then
        # create ROOT
        if _kc create groups -r "$realm" --server "$KC_BOOT_URL" --insecure -s "name=$seg" >/dev/null 2>&1; then
          gid="$(group_id_by_name_under "$realm" "" "$seg" || true)"
        else
          log "❌ Failed to create root group '$seg'"; return 1
        fi
      else
        # create CHILD
        if _kc create "groups/$parent/children" -r "$realm" --server "$KC_BOOT_URL" --insecure -s "name=$seg" >/dev/null 2>&1; then
          gid="$(group_id_by_name_under "$realm" "$parent" "$seg" || true)"
        else
          log "❌ Failed to create child '$seg' under '$parent'"; return 1
        fi
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
export KC_BOOT_URL
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
until _kc config credentials \
  --server "$KC_BOOT_URL" --realm master \
  --user "$ADMIN_USER" --password "$ADMIN_PWD" --insecure >/dev/null 2>&1
do
  sleep 2
done
log "🔐 Logged into admin CLI."

# Seed the base kcadm config file now that KC is reachable (avoids file locks in workers)
/opt/keycloak/bin/kcadm.sh config credentials \
  --server "$KC_BOOT_URL" --realm master \
  --user "$ADMIN_USER" --password "$ADMIN_PWD" \
  --insecure --config "$KCADM_BASE_CONFIG" >/dev/null 2>&1 || true


# --- Ensure realm exists BEFORE any group ops ---
if _kc get "realms/$REALM" --realm master --server "$KC_BOOT_URL" --insecure >/dev/null 2>&1; then
  log "♻️  Realm '$REALM' exists."
else
  log "🆕 Creating empty realm '$REALM'…"
  _kc create realms --realm master --server "$KC_BOOT_URL" --insecure \
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
_kc get "realms/$REALM/groups" \
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
        _kc create "groups/$pid/children" -r "$REALM" \
          --server "$KC_BOOT_URL" --insecure -s "name=$gname" >/dev/null 2>&1 || true
        log "   ➕ Created canonical '$canon'"
      fi
      # Now delete root stray
      _kc delete "groups/$gid" -r "$REALM" --server "$KC_BOOT_URL" --insecure >/dev/null 2>&1 || true
      log "   🗑️  Deleted stray root group '$gname' (moved to '$canon')"
    fi
  fi
done
log "✅ Root cleanup complete."


# --- Proceed with partialImport for non-group sections only (optional) ---
# If you still do sectioned imports, skip 'groups' section entirely.
section_import() {
  key="$1"
  src="${2:-$SRC_FILE}"   # allow override

  [ "$key" = "groups" ] && { log "⏭️  Skipping groups section (handled manually)"; return 0; }

  body="/tmp/partial-${key}.json"
  jq -c --arg k "$key" '{ ifResourceExists:"SKIP", ($k):(.[$k] // []) }' "$src" > "$body"
  _kc create "realms/$REALM/partialImport" \
    --realm master --server "$KC_BOOT_URL" --insecure -f "$body" 2>"/tmp/partial-${key}.err" \
    || { log "  ⚠️  ${key} import failed:"; sed 's/^/    │ /' "/tmp/partial-${key}.err" >&2; }
}



# Refresh a2a CLI token before partial imports
_kc config credentials \
  --server "$KC_BOOT_URL" --realm master \
  --user "$ADMIN_USER" --password "$ADMIN_PWD" --insecure >/dev/null 2>&1 || true

echo "$(ts) [kc] listing client-scopes before import…" >&2
_kc get client-scopes -r "$REALM" --server "$KC_BOOT_URL" --insecure --fields name,protocol 2>/dev/null \
  | jq -r '.[]? | "\(.name)\t\(.protocol // "n/a")"' | sed 's/^/   • /' >&2 || true

echo "$(ts) [kc] does groups-claim exist pre-import?" >&2
if _kc get client-scopes -r "$REALM" --server "$KC_BOOT_URL" --insecure -q name=groups-claim >/dev/null 2>&1; then
  echo "   ✅ groups-claim exists (pre-import)" >&2
  _CID="$(_kc get client-scopes -r "$REALM" --server "$KC_BOOT_URL" --insecure -q name=groups-claim --fields id | jq -r '.[0].id')"
  echo "   id=$_CID" >&2
  _kc get "client-scopes/${_CID}/protocol-mappers/models" -r "$REALM" --server "$KC_BOOT_URL" --insecure 2>/dev/null \
    | jq -r '.[]?| "\(.name)\t\(.protocolMapper)"' | sed 's/^/      mapper: /' >&2 || true
else
  echo "   ❌ groups-claim not present (pre-import)" >&2
fi

# Example call order (without groups):
section_import clientScopes

echo "$(ts) [kc] ensuring client-scope 'groups-claim' exists…" >&2
if ! _kc get client-scopes -r "$REALM" --server "$KC_BOOT_URL" --insecure -q name=groups-claim >/dev/null 2>&1; then
  echo "   • creating client-scope 'groups-claim'…" >&2
  if _kc create client-scopes -r "$REALM" --server "$KC_BOOT_URL" --insecure \
       -s name=groups-claim -s protocol=openid-connect >/dev/null 2>&1; then
    echo "   ✅ created 'groups-claim'" >&2
  else
    echo "   ❌ failed creating 'groups-claim'" >&2
  fi

  _CID="$(_kc get client-scopes -r "$REALM" --server "$KC_BOOT_URL" --insecure -q name=groups-claim --fields id | jq -r '.[0].id')"
  if [ -n "$_CID" ] && [ "$_CID" != "null" ]; then
    echo "   • adding oidc-group-membership-mapper…" >&2
    _kc create "client-scopes/${_CID}/protocol-mappers/models" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
      -s name=groups -s protocol=openid-connect -s protocolMapper=oidc-group-membership-mapper \
      -s 'config."full.path"=false' -s 'config."id.token.claim"=true' \
      -s 'config."access.token.claim"=true' -s 'config."userinfo.token.claim"=true' \
      -s 'config."claim.name"=groups' >/dev/null 2>&1 \
      && echo "   ✅ mapper added" >&2 || echo "   ❌ failed to add mapper" >&2
  fi
else
  echo "   ✅ already present (skipping create)" >&2
fi


section_import clients
ensure_defaults_from_export_v2  # ensure DEFAULT client-scopes from import JSON
section_import roles

# Refresh a2a CLI token before partial imports
_kc config credentials \
  --server "$KC_BOOT_URL" --realm master \
  --user "$ADMIN_USER" --password "$ADMIN_PWD" --insecure >/dev/null 2>&1 || true

# --- Faster: Apply clientRoles to groups in batches -------------------------------
client_uuid_by_clientId() {
  # $1 realm, $2 clientId
  _kc get clients -r "$1" --server "$KC_BOOT_URL" --insecure \
    -q "clientId=$2" --fields id,clientId 2>/dev/null \
  | jq -r '.[0]?.id // empty'
}

# Cache all groups once: build path -> id map
_cache_group_paths() {
  _realm="$1"; _out="${2:-/tmp/kc_group_map.json}"

  _kc get groups -r "$_realm" --server "$KC_BOOT_URL" --insecure \
    > /tmp/kc_groups_raw.json 2> /tmp/kc_groups_raw.err || {
      echo "ERR: GET groups failed for realm=$_realm : $(sed -n '1,3p' /tmp/kc_groups_raw.err)" >&2
      return 1
    }

  jq -c '
    def walkg($base):
      . as $g
      | ($g.name // "") as $n
      | ($g.path // ($base + "/" + $n)) as $p
      | {path: $p, id: $g.id}
      , ( ($g.subGroups // [])[] | walkg($p) );
    [ .[] | walkg("") ]
    | map(.path |= ( if startswith("//") then ( .[1:] ) else . end ))  # normalize // -> /
    | unique_by(.path)
  ' /tmp/kc_groups_raw.json > "$_out"

  printf '%s' "$_out"
}


# Lookup group id by path using cache
_group_id_from_cache() {
  _cache="$1"; _path="$2"
  jq -r --arg p "$_path" '.[] | select(.path==$p) | .id' "$_cache"
}

_cache_clients_and_roles() {
  _realm="$1"; _src="$2"; _dir="${3:-/tmp/kc_cache}"
  mkdir -p "$_dir"

  dbg "[cache] extracting clientIds from mapping source: $_src"
  jq -r '
    def walkg($p):
      . as $g
      | (if ($g.path? and ($g.path|type)=="string" and ($g.path|length)>0)
           then $g.path
           else ($p + (if $p=="" then "" else "/" end) + ($g.name // ""))
         end) as $q
      | {path:$q, cr: ($g.clientRoles // {})}
      , ( ($g.subGroups // [])[] | walkg($q) );
    (.groups // [])[] | walkg("")
    | select(.path != null and .path != "")
    | .cr | keys[]' "$_src" \
  | sort -u >"$_dir/clients.txt"

  local N
  N="$(wc -l <"$_dir/clients.txt" | tr -d ' ')"
  printf "%s [cache] %s unique clientId(s) in mapping source\n" "$(ts)" "$N" >&2
  [ "${DEBUG_INIT:-0}" = 1 ] && dump_head "[cache] clients.txt" "$_dir/clients.txt" 15

  : >"$_dir/client_map.tsv"
  ok=0; miss=0
  while IFS= read -r cid; do
    [ -z "$cid" ] && continue
    cuuid="$(client_uuid_by_clientId "$_realm" "$cid" || true)"
    if [ -n "$cuuid" ]; then
      printf '%s\t%s\n' "$cid" "$cuuid" >>"$_dir/client_map.tsv"
      rfile="$_dir/roles-$cuuid.json"
      _kc get "clients/$cuuid/roles" -r "$_realm" --server "$KC_BOOT_URL" --insecure \
        -q first=0 -q max=5000 2>/dev/null \
      | jq -c '[ .[] | {id,name} ]' >"$rfile"
      rc="$(jq 'length' "$rfile" 2>/dev/null || printf 0)"
      printf "%s [cache] client %-24s → %s role(s)\n" "$(ts)" "$cid" "$rc" >&2
      ok=$((ok+1))
    else
      printf "%s [cache] WARN: clientId '%s' not found in realm '%s'\n" "$(ts)" "$cid" "$_realm" >&2
      miss=$((miss+1))
    fi
  done <"$_dir/clients.txt"

  printf "%s [cache] clients resolved: %s ok, %s missing\n" "$(ts)" "$ok" "$miss" >&2
  printf '%s\n' "$_dir"
}

# Ensure all client roles referenced by the mapping source exist in KC
ensure_client_roles_from_mapping() {
  _realm="$1"; _cache_dir="$2"; _map_src="$3"

  log "[roles] Ensuring client roles exist before mapping…"

  # Build "clientId<TAB>roleName" list from mapping source
  want="/tmp/wanted-client-roles.tsv"
  jq -r '
    def walkg($p):
      . as $g
      | (if ($g.path? and ($g.path|type)=="string" and ($g.path|length)>0)
           then $g.path
           else ($p + (if $p=="" then "" else "/" end) + ($g.name // ""))
         end) as $q
      | {path:$q, cr: ($g.clientRoles // {})}
      , ( ($g.subGroups // [])[] | walkg($q) );
    (.groups // [])[] | walkg("")
    | .cr | to_entries[] | [.key, (.value[])] | @tsv
  ' "$_map_src" | sort -u >"$want"

  # For each client, create any missing roles
  awk -F'\t' '{print $1}' "$want" | sort -u | while read -r cid; do
    [ -z "$cid" ] && continue
    cuuid="$(awk -F'\t' -v C="$cid" '$1==C{print $2}' "$_cache_dir/client_map.tsv" | head -n1)"
    if [ -z "$cuuid" ]; then
      log "[roles] WARN: mapping references clientId '$cid' that is not in realm '$_realm' — skipping"
      continue
    fi

    # existing roles (names) for this client
    rfile="$_cache_dir/roles-$cuuid.json"
    [ -s "$rfile" ] || printf '[]' > "$rfile"
    have_names="$(jq -r '.[].name' "$rfile" | sort -u)"

    # wanted names for this client
    grep -F "$cid" "$want" | cut -f2 | sort -u > /tmp/want-"$cuuid".txt

    # existing roles (names) for this client
    rfile="$_cache_dir/roles-$cuuid.json"
    [ -s "$rfile" ] || printf '[]' > "$rfile"

    # prepare sorted lists for comm
    have_names_file="/tmp/have-$cuuid.txt"
    jq -r '.[].name' "$rfile" | sort -u > "$have_names_file"
    want_names_file="/tmp/want-$cuuid.txt"
    grep -F "$cid" "$want" | cut -f2 | sort -u > "$want_names_file"

    # compute missing = wanted - have
    miss_file="/tmp/miss-$cuuid.txt"
    comm -13 "$have_names_file" "$want_names_file" > "$miss_file" || true
    M=$(wc -l < "$miss_file" | tr -d ' ')
    if [ "$M" -gt 0 ]; then
      printf "%s [roles] client %-24s create %s missing role(s)\n" "$(ts)" "$cid" "$M" >&2

      # parallel branch (fallback to serial if xargs absent or ROLE_CREATE_PAR=1)
      if command -v xargs >/dev/null 2>&1 && [ "${ROLE_CREATE_PAR:-1}" -gt 1 ]; then
        # use the binary directly in workers (don’t rely on shell functions)
        export KC_BOOT_URL KCADM_BASE_CONFIG
        xargs -r -n1 -P"${ROLE_CREATE_PAR:-8}" -a "$miss_file" \
          /opt/keycloak/bin/kcadm.sh create "clients/$cuuid/roles" \
            -r "$_realm" --server "$KC_BOOT_URL" --insecure --config "$KCADM_BASE_CONFIG" \
            -s name=@@ >/dev/null 2>&1
        # NOTE: with older xargs that doesn’t support -a or placeholder, use:
        #   cat "$miss_file" | xargs -r -n1 -P"${ROLE_CREATE_PAR:-8}" sh -c '
        #     /opt/keycloak/bin/kcadm.sh create "clients/'"$cuuid"'/roles" \
        #       -r "'"$_realm"'" --server "$KC_BOOT_URL" --insecure --config "$KCADM_BASE_CONFIG" \
        #       -s name="$0" >/dev/null 2>&1
        #   '
      else
        # serial fallback
        while IFS= read -r rn; do
          [ -z "$rn" ] && continue
          /opt/keycloak/bin/kcadm.sh create "clients/$cuuid/roles" \
            -r "$_realm" --server "$KC_BOOT_URL" --insecure --config "$KCADM_BASE_CONFIG" \
            -s name="$rn" >/dev/null 2>&1 || true
        done < "$miss_file"
      fi

      # refresh cache for this client so the mapping step has the IDs immediately
      /opt/keycloak/bin/kcadm.sh get "clients/$cuuid/roles" \
        -r "$_realm" --server "$KC_BOOT_URL" --insecure --config "$KCADM_BASE_CONFIG" \
        -q first=0 -q max=5000 2>/dev/null \
      | jq -c '[ .[] | {id,name} ]' >"$rfile"
    else
      printf "%s [roles] client %-24s already has all referenced roles\n" "$(ts)" "$cid" >&2
    fi
  done
}


_build_batches() {
  _src="$1"; _workdir="${2:-/tmp/kc_batches}"
  rm -rf "$_workdir"; mkdir -p "$_workdir"

  dbg "[batch] building from $_src"
  jq -r '
    def walkg($p):
      . as $g
      | (if ($g.path? and ($g.path|type)=="string" and ($g.path|length)>0)
           then $g.path
           else ($p + (if $p=="" then "" else "/" end) + ($g.name // ""))
         end) as $q
      | {path:$q, cr: ($g.clientRoles // {})}
      , ( ($g.subGroups // [])[] | walkg($q) );
    (.groups // [])[] | walkg("")
    | select(.path != null and .path != "")
    | . as $row
    | $row.cr
    | to_entries[] as $e
    | $e.key as $client
    | $e.value[] as $r
    | [$row.path, $client, $r] | @tsv
  ' "$_src" \
  | sort -u \
  | while IFS=$'\t' read -r gpath client_id role_name; do
      [ -z "$gpath$client_id$role_name" ] && continue
      key="$(printf '%s|%s' "$gpath" "$client_id" | md5sum | awk '{print $1}')"
      d="$_workdir/$key"
      mkdir -p "$d"
      printf '%s\n' "$gpath"       >"$d/path"
      printf '%s\n' "$client_id"   >"$d/clientId"
      printf '%s\n' "$role_name"  >>"$d/roles.txt"
    done

  B="$(find "$_workdir" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
  printf "%s [batch] built %s (group,client) batch dir(s)\n" "$(ts)" "$B" >&2
  if [ "${DEBUG_BATCH:-0}" = 1 ]; then
    # show 5 batches
    for d in $(find "$_workdir" -mindepth 1 -maxdepth 1 -type d | head -n 5); do
      dump_head "[batch] $(basename "$d")/path" "$d/path" 1
      dump_head "[batch] $(basename "$d")/clientId" "$d/clientId" 1
      dump_head "[batch] $(basename "$d")/roles.txt" "$d/roles.txt" 10
    done
  fi

  printf '%s\n' "$_workdir"
}


# Single batch apply for one (group, client): builds a single JSON array for all roles in that batch
_apply_one_batch() {
  _realm="$1"; _group_cache="$2"; _cache_dir="$3"; _batch_dir="$4"

  gpath="$(cat "$_batch_dir/path")"
  cid="$(cat "$_batch_dir/clientId")"
  roles_file="$_batch_dir/roles.txt"

  [ -s "$roles_file" ] || return 0

  # New: try cache (with/without leading slash), then live walk
    gid="$(_group_id_from_cache "$_group_cache" "$gpath")"
    [ -z "$gid" ] && gid="$(_group_id_from_cache "$_group_cache" "${gpath#/}")"
    if [ -z "$gid" ]; then
      gid="$(_resolve_gid_by_path "$_realm" "$gpath")"
    fi
    if [ -z "$gid" ]; then
      [ "${DEBUG_WORKER:-0}" = 1 ] && {
        log "❌ [child] Cache+fallback miss for '$gpath' — sampling available paths:"
        _kc get groups -r "$_realm" --server "$KC_BOOT_URL" --insecure --fields path,id 2>/dev/null \
          | jq -r '.[].path' \
          | grep -F "$(printf '%s' "$gpath" | awk -F/ '{print $2}')" \
          | head -n 5 | sed 's/^/   • /' >&2 || true
      }
      return 0
    fi

  cuuid="$(awk -F'\t' -v C="$cid" '$1==C{print $2}' "$_cache_dir/client_map.tsv" | head -n1)"
  if [ -z "$cuuid" ]; then
    log "❌ Unknown clientId '$cid' (skipping $gpath)"
    return 0
  fi

  roles_json="$_cache_dir/roles-$cuuid.json"
  if [ ! -s "$roles_json" ]; then
    log "❌ No roles cache for client '$cid' ($cuuid) (skipping $gpath)"
    return 0
  fi

  # Build wanted list (unique)
  wanted="$(sort -u "$roles_file" | jq -R -s 'split("\n") | map(select(length>0))')"

  body="$_batch_dir/body.json"
  jq -c --argjson wanted "$wanted" '
    [ .[]
      | select(.name as $n | $wanted | index($n))
      | {id,name}
    ]
  ' "$roles_json" >"$body"

  # Empty? nothing to map.
  if [ "$(jq 'length' "$body")" -eq 0 ]; then
    log "⚠️  No matching roles under client '$cid' for group '$gpath' (skip)"
    return 0
  fi

  if _kc create "groups/$gid/role-mappings/clients/$cuuid" \
       -r "$_realm" --server "$KC_BOOT_URL" --insecure -f "$body" >/dev/null 2>&1
  then
    cnt="$(jq 'length' "$body")"
    log "🔐 Mapped $cnt role(s) from client '$cid' to group '$gpath' (batched)"
  else
    log "❌ Failed batch mapping for client '$cid' to group '$gpath'"
    return 1
  fi
}

# Public entry: batched + cached role mappings
apply_group_client_roles() {
  _realm="$1"; _src="$2"
  log "🔗 Applying group clientRoles (batched)…"

  # 0) Pick a source that *has* clientRoles (overlay from original if needed)
  MAPPING_SRC="$(_prepare_mapping_source "$_src" "$IMPORT_FILE_ORIG")"
  [ "${DEBUG_WORKER:-0}" = "1" ] && log "[debug] mapping src: $MAPPING_SRC"
  GROUP_CACHE="$(_cache_group_paths "$_realm")" || { log "❌ Failed to cache groups"; return 1; }
  CACHED_DIR="$(_cache_clients_and_roles "$_realm" "$MAPPING_SRC")" || { log "❌ Failed to cache clients/roles"; return 1; }

  # 🚀 NEW: fast, parallel role creation via curl (creates ONLY missing roles)
  ensure_client_roles_from_mapping_curl "$_realm" "$CACHED_DIR" "$MAPPING_SRC"

  # Sanity on the mapping source
  jq_count "[apply] mapping-src clientRoles objects" \
           '[..|objects|.clientRoles?|select(type=="object")]|length' "$MAPPING_SRC"
  jq_count "[apply] KC group count (cache)" 'length' "$(_cache_group_paths "$_realm")"  # quick sample count


  [ "${DEBUG_WORKER:-0}" = "1" ] && log "[debug] mapping src: $MAPPING_SRC"

  # 1) Build caches (clients → uuid, existing roles; and KC group tree)

  # (optional) visibility before role creation
  jq_count "[apply] cached KC groups" 'length' "$GROUP_CACHE"
  printf "%s [apply] cached clients with roles: %s file(s)\n" \
    "$(ts)" "$(ls -1 "$CACHED_DIR"/roles-*.json 2>/dev/null | wc -l | tr -d ' ')" >&2
  [ "${DEBUG_INIT:-0}" = 1 ] && dump_head "[apply] client map (cid → uuid)" "$CACHED_DIR/client_map.tsv" 20

  # 🚀 NEW: fast, parallel role creation via curl (creates ONLY missing roles)
  ensure_client_roles_from_mapping_curl "$_realm" "$CACHED_DIR" "$MAPPING_SRC"

  # (optional) quick post-create visibility (cache files are refreshed per client already)
  printf "%s [apply] cached clients with roles (post-create): %s file(s)\n" \
    "$(ts)" "$(ls -1 "$CACHED_DIR"/roles-*.json 2>/dev/null | wc -l | tr -d ' ')" >&2

  # 2) Build batches
  BATCH_DIR="$(_build_batches "$MAPPING_SRC")"

  if [ "${DEBUG_BATCH:-0}" = 1 ]; then
    printf "%s [apply] batch root: %s\n" "$(ts)" "$BATCH_DIR" >&2
    find "$BATCH_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 5 | while read d; do
      dump_head "[apply] sample $(basename "$d")/path" "$d/path" 1
      dump_head "[apply] sample $(basename "$d")/clientId" "$d/clientId" 1
      dump_head "[apply] sample $(basename "$d")/roles.txt" "$d/roles.txt" 10
    done
  fi

  # Optional visibility when nothing to do
  if [ "$(find "$BATCH_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')" -eq 0 ]; then
    log "ℹ️  No (group,client) role batches were produced. Likely no clientRoles present in export."
    return 0
  fi

  # 3) Prepare for worker reinvocation (unchanged)
  SELF="${SELF:-$0}"
  case "$SELF" in
    /*) : ;;
    *) SELF="$(readlink -f "$SELF" 2>/dev/null || realpath "$SELF" 2>/dev/null || printf '%s/%s' "$PWD" "$SELF")"
  esac
  export KC_BOOT_URL KCADM_BASE_CONFIG KCADM_CONFIG_DIR

  # 4) Apply (parallel or serial) … (leave your existing xargs/serial code here)
  PAR="${KCADM_PARALLEL:-1}"
  if command -v xargs >/dev/null 2>&1 && [ "$PAR" -gt 1 ]; then
    find "$BATCH_DIR" -mindepth 1 -maxdepth 1 -type d -print0 \
    | xargs -0 -P"$PAR" -I{} sh -c '
        [ "${DEBUG_WORKER:-0}" = "1" ] && printf "[spawn] %s __apply_one_batch__ %s %s %s %s\n" "$0" "$1" "$2" "$3" "$4" >&2
        exec "$0" __apply_one_batch__ "$1" "$2" "$3" "$4"
      ' "$SELF" "$_realm" "$GROUP_CACHE" "$CACHED_DIR" {}
  else
    for d in "$BATCH_DIR"/*; do
      [ -d "$d" ] || continue
      [ "${DEBUG_WORKER:-0}" = "1" ] && log "[spawn-serial] $SELF __apply_one_batch__ $_realm $GROUP_CACHE $CACHED_DIR $d"
      "$SELF" __apply_one_batch__ "$_realm" "$GROUP_CACHE" "$CACHED_DIR" "$d"
    done
  fi

  log "✅ Finished applying group clientRoles (batched)."
}


# Run it using the same SRC_FILE that powered group-tree creation
set +e
apply_group_client_roles "$REALM" "$SRC_FILE"
rc=$?
set -e
log "[apply] group clientRoles rc=$rc"

if jq -e '.users | type=="array" and length>0' "$IMPORT_FILE_ORIG" >/dev/null 2>&1; then
  n="$(jq '.users|length' "$IMPORT_FILE_ORIG")"
  log "👥 Chunked user import: $n users from $(basename "$IMPORT_FILE_ORIG")"
  i=0
  while :; do
    chunk="/tmp/users-chunk-$i.json"
    jq -c --argjson s $((i*500)) --argjson l 500 '
      { ifResourceExists:"SKIP", users: (.users // [])[ $s : ($s+$l) ] }
    ' "$IMPORT_FILE_ORIG" > "$chunk"
    [ "$(jq '.users|length' "$chunk")" -eq 0 ] && break
    _kc create "realms/$REALM/partialImport" --realm master --server "$KC_BOOT_URL" --insecure -f "$chunk" || true
    i=$((i+1))
  done
else
  log "ℹ️  No users found in $(basename "$IMPORT_FILE_ORIG"); skipping user import."
fi




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

  _id="$(_kc get client-scopes -r "$_realm" --server "$KC_BOOT_URL" --insecure \
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
    if _kc create client-scopes -r "$_realm" --server "$KC_BOOT_URL" --insecure \
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
  _kc get "client-scopes/$2/protocol-mappers/models" -r "$1" --server "$KC_BOOT_URL" --insecure 2>/dev/null \
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
    if _kc create "client-scopes/$_scope_id/protocol-mappers/models" \
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

  if _kc create "client-scopes/$sid/protocol-mappers/models" \
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
  _kc update "realms/$1" --server "$KC_BOOT_URL" --insecure \
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

# --- If sanitized $SRC_FILE has no users, hydrate from original export ---
if ! jq -e '.users | type=="array" and length>0' "$SRC_FILE" >/dev/null 2>&1; then
  if [ -s "$IMPORT_FILE_ORIG" ] && jq -e '.users | type=="array" and length>0' "$IMPORT_FILE_ORIG" >/dev/null 2>&1; then
    log "👥 'users' missing from $(basename "$SRC_FILE"); hydrating from $(basename "$IMPORT_FILE_ORIG")…"
    # 1) the create payloads (one JSON per line)
    jq -c '.users[]' "$IMPORT_FILE_ORIG" > /tmp/users-to-create.json
    # 2) their group memberships for the fallback join logic
    mkdir -p /tmp/user-groups
    jq -r '.users[] | select(.groups|type=="array") | [.username, (.groups[])] | @tsv' "$IMPORT_FILE_ORIG" \
      | while IFS=$'\t' read -r uname gpath; do
          [ -n "$uname" ] && [ -n "$gpath" ] && printf '%s\n' "$gpath" >> "/tmp/user-groups/$uname.txt"
        done
  else
    log "ℹ️  No users in sanitized or original export; skipping user creation."
  fi
fi

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
  raw_json="$(_kc get users -r "$_realm" --server "$KC_BOOT_URL" --insecure \
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
      uid="$(_kc get users -r "$REALM" --server "$KC_BOOT_URL" --insecure -q "username=$uname" --fields id 2>/dev/null | json_first_id || true)"
    else
      # create without credentials/groups (kcadm supports JSON via -f -)
      printf '%s' "$ujson" | jq 'del(.credentials, .groups, .requiredActions)' \
        | _kc create users -r "$REALM" --server "$KC_BOOT_URL" --insecure -f - >/tmp/create-user.out 2>/dev/null || true
      # fetch id
      uid="$(_kc get users -r "$REALM" --server "$KC_BOOT_URL" --insecure -q "username=$uname" --fields id 2>/dev/null | json_first_id || true)"
      [ -n "$uid" ] && log "✅ Created user '$uname' (id=$uid)"
    fi

    [ -z "${uid:-}" ] && continue

    # set requiredActions if any
    req_json="$(printf '%s' "$ujson" | jq -c '.requiredActions | select(length>0)')"
    if [ -n "${req_json:-}" ]; then
      _kc update "users/$uid" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
        -s "requiredActions+=$(printf '%s' "$req_json")" >/dev/null 2>&1 || true
    fi

    # set password from first credential if present
    pass_val="$(printf '%s' "$ujson" | jq -r '.credentials[0]?.value // empty')"
    temp_flag="$(printf '%s' "$ujson" | jq -r '.credentials[0]?.temporary // false')"
    if [ -n "$pass_val" ] && [ "$pass_val" != "null" ]; then
      _kc set-password -r "$REALM" --server "$KC_BOOT_URL" --insecure \
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
          _kc update "users/$uid/groups/$gid" -r "$REALM" --server "$KC_BOOT_URL" --insecure -n >/dev/null 2>&1 || true
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
  _kc create "client-scopes/$CS_ROLES_ID/protocol-mappers/models" -r "$REALM" --server "$KC_BOOT_URL" --insecure -f - <<'JSON' >/dev/null 2>&1 || true
{ "name":"realm roles","protocol":"openid-connect","protocolMapper":"oidc-usermodel-realm-role-mapper",
  "config":{"multivalued":"true","userinfo.token.claim":"true","id.token.claim":"true","access.token.claim":"true",
            "claim.name":"realm_access.roles","jsonType.label":"String"}}
JSON
fi
if ! protocol_mapper_exists "$REALM" "$CS_ROLES_ID" "client roles"; then
  _kc create "client-scopes/$CS_ROLES_ID/protocol-mappers/models" -r "$REALM" --server "$KC_BOOT_URL" --insecure -f - <<'JSON' >/dev/null 2>&1 || true
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
  _kc update "client-scopes/$CS_ACC_AUD_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
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
  _kc update "client-scopes/$CS_API_AUD_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s 'attributes."include.in.token.scope"=true' >/dev/null 2>&1 || true
  ensure_audience_mapper "$REALM" "$CS_API_AUD_ID" "osss-api" "audience: osss-api"
fi

# ---------- Configure built-in account-console as SPA ----------
ACC_CONSOLE_ID=$(_kc get clients -r "$REALM" --server "$KC_BOOT_URL" --insecure -q clientId=account-console --fields id | json_first_id || true)
if [ -n "${ACC_CONSOLE_ID:-}" ]; then
  log "🛠  Configuring 'account-console' as public SPA…"
  _kc update "clients/$ACC_CONSOLE_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
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
_kc update "realms/$REALM" --server "$KC_BOOT_URL" --insecure \
  -s "attributes.frontendUrl=$ORIGIN" \
  -s 'defaultDefaultClientScopes+=profile' \
  -s 'defaultDefaultClientScopes+=email' \
  -s 'defaultDefaultClientScopes+=roles' \
  -s 'defaultDefaultClientScopes+=account-audience' >/dev/null 2>&1 || true

# ---------- CORS/webOrigins for security-a2a-console + account ----------
# set_weborigins:
#   Normalizes the allowed CORS origins (`webOrigins`) for a specific Keycloak client.
#
#   Arguments:
#     $1 – The clientId of the target client (e.g., "account", "security-a2a-console").
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
#     Ensures that critical Keycloak clients (like the security a2a console and account console)
#     have proper `webOrigins` set for cross-origin requests. This prevents CORS errors when the
#     realm’s UI or APIs are accessed from browsers.
#
#   Example:
#     set_weborigins "security-a2a-console"
#     → Ensures that the `security-a2a-console` client in `$REALM` accepts requests from `+` and `$ORIGIN`.
set_weborigins() {
  _CID="$(_kc get clients -r "$REALM" --server "$KC_BOOT_URL" --insecure -q clientId="$1" --fields id 2>/dev/null | json_first_id || true)"
  [ -z "$_CID" ] && { log "ℹ️  Client '$1' not found in realm '$REALM' (skipping)"; return 0; }
  _kc update "clients/$_CID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s 'webOrigins=["+"]' >/dev/null 2>&1 || true
  _kc update "clients/$_CID" -r "$REALM" --server "$KC_BOOT_URL" --insecure \
    -s "webOrigins+=$ORIGIN" >/dev/null 2>&1 || true
}
set_weborigins "security-admin-console"
ACC_ID=$(_kc get clients -r "$REALM" --server "$KC_BOOT_URL" --insecure -q clientId=account --fields id | json_first_id || true)
if [ -n "${ACC_ID:-}" ]; then
  log "🔧 Normalizing webOrigins for 'account' client..."
  set +e
  _kc update "clients/$ACC_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure -s 'webOrigins=["+"]' >/dev/null 2>&1
  _kc update "clients/$ACC_ID" -r "$REALM" --server "$KC_BOOT_URL" --insecure -s "webOrigins+=$ORIGIN" >/dev/null 2>&1
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
  cid="$(_kc get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
          -q clientId="$_clientId" --fields id | json_first_id || true)"

  if [ -z "${cid:-}" ]; then
    log "⚠️  Client '$_clientId' not found. Creating new client with name='$_name'…"
    if _kc create clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
         -s clientId="$_clientId" -s name="$_name" -s protocol=openid-connect \
         -s publicClient=false -s standardFlowEnabled=true -s directAccessGrantsEnabled=false \
         -s serviceAccountsEnabled=false -s 'attributes."post.logout.redirect.uris"=+' >/dev/null 2>&1; then
      log "✅ Successfully created client '$_clientId'"
      # Fetch id again
      cid="$(_kc get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
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
  _cid="$(_kc get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
            -q clientId="$_clientId" --fields id 2>/dev/null | jq -r '.[0].id // empty')"
  if [ -z "${_cid:-}" ]; then
    log "⚠️  Client '$_clientId' not found in realm '$_realm'; skipping."
    return 0
  fi
  log "🔗 Found client '$_clientId' (id=$_cid)"

  # Build payload: id,name,clientRole,containerId required for client-role mapping
  local _roles_json _count
  _roles_json="$(_kc get "clients/$_cid/roles" -r "$_realm" --server "$KC_BOOT_URL" --insecure 2>/dev/null \
                  | jq -c '[.[]? | {id:.id,name:.name,clientRole:true,containerId:"'"$_cid"'"}]')"
  _count="$(printf '%s' "$_roles_json" | jq 'length')"
  if [ "${_count:-0}" -gt 0 ]; then
    log "➕ Assigning ${_count} roles from client '$_clientId'…"
    if printf '%s' "$_roles_json" \
       | _kc create "users/$_uid/role-mappings/clients/$_cid" \
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
  _roles_json="$(_kc get roles -r "$_realm" --server "$KC_BOOT_URL" --insecure 2>/dev/null \
                  | jq -c '[.[]? | {id:.id,name:.name}]')"
  _count="$(printf '%s' "$_roles_json" | jq 'length')"
  if [ "${_count:-0}" -gt 0 ]; then
    log "➕ Assigning ${_count} REALM roles in '$_realm'…"
    if printf '%s' "$_roles_json" \
       | _kc create "users/$_uid/role-mappings/realm" \
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
  cid="$(_kc get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure \
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
  if _kc update "clients/$cid" -r "$_realm" --server "$KC_BOOT_URL" --insecure \
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

# ===================== Ensure CTO user and full a2a mappings in BOTH realms =====================
CTO_USER="chief_technology_officer@osss.local"
CTO_PASS="${CTO_PASSWORD:-password}"  # override with env if desired

# user_id_by_username:
#   Looks up a Keycloak user by their username within a given realm and returns the user’s ID.
#
#   Arguments:
#     $1 – Realm name (e.g., "OSSS" or "master")
#     $2 – Username to look up (e.g., "a2a@osss.local")
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
  _id="$(_kc get users -r "$_realm" --server "$KC_BOOT_URL" --insecure \
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
#   password, and assigning all roles from critical a2a-related clients.
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
#     This is essential for bootstrap and emergency access to Keycloak a2a features.
#
#   Example:
#     grant_admin_mappings "OSSS"
#     → Ensures CTO_USER exists in OSSS realm with all a2a and console roles assigned.
#
#     grant_admin_mappings "master"
#     → Ensures CTO_USER exists in master realm with full a2a access.
grant_admin_mappings () {
  _realm="$1"
  _user="${2:-$CTO_USER}"

  log "🔎 Checking for user $_user in realm $_realm…"
  _uid="$(user_id_by_username "$_realm" "$_user" || true)"
  if [ -z "${_uid:-}" ]; then
    log "➕ Creating user $_user in realm $_realm…"
    _kc create users -r "$_realm" --server "$KC_BOOT_URL" --insecure \
      -s "username=$_user" -s "email=$_user" -s enabled=true -s emailVerified=true \
      >/dev/null 2>&1 || log "⚠️ Failed to create user $_user"
    _uid="$(user_id_by_username "$_realm" "$_user" || true)"
    [ -n "${_uid:-}" ] && log "✅ Created user $_user with id $_uid" || :
  else
    log "ℹ️ User $_user already exists in $_realm with id $_uid"
  fi

  if [ -n "${_uid:-}" ]; then
    log "🔑 Setting password for user $_user in realm $_realm…"
    _kc set-password -r "$_realm" --server "$KC_BOOT_URL" --insecure \
      --userid "$_uid" --new-password "$CTO_PASS" --temporary=false >/dev/null 2>&1 \
      && log "✅ Password set for $_user" || log "⚠️ Failed to set password for $_user"

    # 1) Grant ALL REALM roles
    assign_all_realm_roles "$_realm" "$_uid"

    # 2) Grant ALL client roles from EVERY client in the realm
    client_count="$(_kc get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure 2>/dev/null | jq 'length')"
    log "🔎 Enumerating ${client_count:-0} clients in realm '$_realm' for role assignment…"
    _kc get clients -r "$_realm" --server "$KC_BOOT_URL" --insecure 2>/dev/null \
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