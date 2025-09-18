#!/usr/bin/env bash
# osss-compose-repair.sh
# Dynamic Compose repair + logs utility that adapts to docker-compose.yml (and profile).
# - Auto-detects services per compose file/profile
# - Builds menu entries only for present services
# - Safe fallbacks when compose logs aren't available
# - Persists default tail size in ~/.config/osss-compose-repair.conf

set -Eeuo pipefail

# -------- dotenv loader --------
# Loads a dotenv-style file: KEY=VAL lines (comments & blanks okay). Everything is exported.
load_dotenv() {
  local candidate="$1"
  [[ -z "${candidate:-}" ]] && return 0
  if [[ -f "$candidate" ]]; then
    echo "🔧 Loading environment from: $candidate"
    # shellcheck disable=SC1090
    set -a; source "$candidate"; set +a
  fi
}

# Early dotenv load (before defaults), so .env can set COMPOSE_FILE/PROFILE/etc.
# Priority: $ENV_FILE (if set) → ./.env
if [[ -n "${ENV_FILE:-}" ]]; then
  load_dotenv "$ENV_FILE"
else
  load_dotenv "./.env"
fi

# -------- config / flags --------
PROJECT_DEFAULT="${COMPOSE_PROJECT_NAME:-osss}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
PROFILE="${PROFILE:-seed}"

CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}"
CONFIG_FILE="${CONFIG_DIR}/osss-compose-repair.conf"
DEFAULT_TAIL="200"  # can be overridden by config

usage() {
  cat <<EOF
Usage: $0 [-p PROJECT] [-f docker-compose.yml] [-r PROFILE]

Options:
  -p PROJECT      Compose project name (default: ${PROJECT_DEFAULT})
  -f FILE         Compose file path (default: ${COMPOSE_FILE})
  -r PROFILE      Compose profile to target (default: ${PROFILE})
Environment:
  ENV_FILE        Path to a .env file to load first (overrides ./\.env)
EOF
  exit 0
}

while getopts ":p:f:r:h" opt; do
  case "$opt" in
    p) PROJECT_DEFAULT="$OPTARG" ;;
    f) COMPOSE_FILE="$OPTARG"   ;;
    r) PROFILE="$OPTARG"        ;;
    h) usage                    ;;
    \?) echo "Unknown option: -$OPTARG" >&2; usage ;;
  esac
done

# Late dotenv load (after -f): also load .env next to the compose file
# Priority: $ENV_FILE (again, if you want to ensure it applies after flags) → <dir-of-compose>/.env
if [[ -n "${ENV_FILE:-}" ]]; then
  load_dotenv "$ENV_FILE"
fi
compose_dir="$(dirname -- "$COMPOSE_FILE")"
# If compose file isn't in cwd (or even if it is), load its sibling .env too
load_dotenv "${compose_dir%/}/.env"

export COMPOSE_PROJECT_NAME="${PROJECT_DEFAULT}"

# -------- helpers --------

down_all() {
  echo "▶️  Down ALL profiles for project '${COMPOSE_PROJECT_NAME}' (remove orphans & volumes)…"
  run $COMPOSE -f "$COMPOSE_FILE" down --remove-orphans --volumes || true

  echo "▶️  Ensuring no leftover containers remain for '${COMPOSE_PROJECT_NAME}'…"
  ids=$(docker ps -a --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" -q)
  if [[ -n "${ids:-}" ]]; then
    run docker rm -f ${ids}
  else
    echo "(none)"
  fi

  echo "▶️  Removing ALL Docker volumes (global prune)…"
  vols="$(docker volume ls -q)"
  if [[ -n "${vols:-}" ]]; then
    run docker volume rm ${vols} || true
  else
    echo "(no volumes to remove)"
  fi
}

# --- service discovery across ALL profiles ---
compose_profiles() {
  if $COMPOSE -f "$COMPOSE_FILE" config --profiles >/dev/null 2>&1; then
    $COMPOSE -f "$COMPOSE_FILE" config --profiles | sed '/^\s*$/d' | sort -u
  else
    # best-effort fallback parser
    awk '
      $1=="profiles:"{inp=1; next}
      inp && $1!~/:/{ sub("-","",$1); print $1 }
      inp && $1~/.:/{ inp=0 }
    ' "$COMPOSE_FILE" | sed '/^\s*$/d' | sort -u
  fi
}

# Replace this whole function
compose_services_base() {
  # First try the canonical way; if it fails (e.g., undefined env), fall back to YAML parsing.
  if $COMPOSE -f "$COMPOSE_FILE" config --services >/dev/null 2>&1; then
    $COMPOSE -f "$COMPOSE_FILE" config --services 2>/dev/null | sed '/^\s*$/d' || true
  else
    # Fallback: parse top-level services keys without expanding env vars.
    # Prints each service name that appears under the root "services:" key.
    awk '
      /^services:[[:space:]]*$/ { in_services=1; next }
      in_services && /^[^[:space:]]/ { in_services=0 }                 # back to root
      in_services && /^[[:space:]]{2}[A-Za-z0-9_.-]+:[[:space:]]*$/ {
        s=$0
        sub(/^[[:space:]]+/, "", s)
        sub(/:.*/, "", s)
        print s
      }
    ' "$COMPOSE_FILE" | sed '/^\s*$/d' | sort -u
  fi
}

# Replace this whole function
compose_services_for_profile() {
  local prof="$1"
  # Canonical path first
  if $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config --services >/dev/null 2>&1; then
    $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | sed '/^\s*$/d' || true
  else
    # Fallback: print services that declare the given profile in their "profiles:" list
    awk -v target="$prof" '
      /^services:[[:space:]]*$/ { in_services=1; next }
      in_services && /^[^[:space:]]/ { in_services=0 }                     # left services block

      # Detect service start: two-space indent + "name:"
      in_services && /^[[:space:]]{2}[A-Za-z0-9_.-]+:[[:space:]]*$/ {
        # flush previous service
        if (svc_name != "" && matched) { print svc_name }
        matched=0; in_prof=0
        line=$0
        sub(/^[[:space:]]+/, "", line)
        sub(/:.*/, "", line)
        svc_name=line
        next
      }

      # Inside a service, track indentation and profiles block
      in_services && svc_name != "" {
        # entering profiles:
        if ($0 ~ /^[[:space:]]{4}profiles:[[:space:]]*$/) {
          in_prof=1
          next
        }
        # leaving profiles if indentation drops to 2 spaces (next key of the service)
        if (in_prof && $0 ~ /^[[:space:]]{2}[A-Za-z0-9_.-]+:[[:space:]]*$/) {
          in_prof=0
        }
        # within profiles list, look for "- foo"
        if (in_prof && $0 ~ /^[[:space:]]{6}-[[:space:]]*[A-Za-z0-9_.-]+[[:space:]]*$/) {
          p=$0
          sub(/^[[:space:]]*-[[:space:]]*/, "", p)
          sub(/[[:space:]]*$/, "", p)
          if (p == target) { matched=1 }
        }
      }

      END {
        if (svc_name != "" && matched) { print svc_name }
      }
    ' "$COMPOSE_FILE" | sed '/^\s*$/d' | sort -u
  fi
}


rebuild_all_services() {
  # Discover all profiles and services
  mapfile -t profs < <(compose_profiles)
  mapfile -t all   < <(compose_services_all)

  if ((${#all[@]}==0)); then
    echo "(no services discovered in ${COMPOSE_FILE})"
    return 1
  fi

  # Build args: enable all profiles so profiled services are included
  local args=( -f "$COMPOSE_FILE" )
  if ((${#profs[@]})); then
    echo "▶️  Enabling profiles: ${profs[*]}"
    for p in "${profs[@]}"; do
      args+=( --profile "$p" )
    done
  fi

  echo "🛠  Rebuilding ALL services (no cache) (${#all[@]}): ${all[*]}"
  run $COMPOSE "${args[@]}" build --no-cache "${all[@]}"

  echo "🚀 Bringing up ALL services with --force-recreate"
  run $COMPOSE "${args[@]}" up -d --force-recreate "${all[@]}"
}

# Union of all services across base + every profile (unique, sorted)
compose_services_all() {
  {
    compose_services_base
    while read -r p; do
      [[ -n "$p" ]] && compose_services_for_profile "$p"
    done < <(compose_profiles)
  } | awk 'NF && !seen[$0]++' | sort -u
}

list_services_logs() {
  compose_services_all
}

start_all_services() {
  # Discover all profiles and services
  mapfile -t profs < <(compose_profiles)
  mapfile -t all   < <(compose_services_all)

  if ((${#all[@]}==0)); then
    echo "(no services discovered in ${COMPOSE_FILE})"
    return 1
  fi

  # Build args: include *all* profiles so profiled services are enabled
  local args=( -f "$COMPOSE_FILE" )
  if ((${#profs[@]})); then
    echo "▶️  Enabling profiles: ${profs[*]}"
    for p in "${profs[@]}"; do
      args+=( --profile "$p" )
    done
  fi

  echo "▶️  Starting ALL services (${#all[@]}): ${all[*]}"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE "${args[@]}" up -d --build "${all[@]}"
  else
    run $COMPOSE "${args[@]}" up -d "${all[@]}"
  fi
}

compose_cmd() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    echo "❌ Neither 'docker compose' nor 'docker-compose' found on PATH." >&2
    exit 1
  fi
}

ensure_compose_file() {
  if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "❌ Compose file not found: $COMPOSE_FILE" >&2
    exit 1
  fi
}

run() { echo "+ $*"; "$@"; }
c() { $COMPOSE -f "$COMPOSE_FILE" --profile "$PROFILE" "$@"; }

load_config() {
  mkdir -p "$CONFIG_DIR"
  [[ -f "$CONFIG_FILE" ]] && source "$CONFIG_FILE"
  : "${DEFAULT_TAIL:=${DEFAULT_TAIL:-200}}"
}
save_config() {
  {
    echo "# Auto-generated by osss-compose-repair.sh"
    echo "DEFAULT_TAIL=${DEFAULT_TAIL}"
  } > "$CONFIG_FILE"
  echo "Saved settings -> $CONFIG_FILE"
}

COMPOSE="$(compose_cmd)"
ensure_compose_file
load_config

# -------- service discovery (profile-bound cache used by some helpers) --------
COMPOSE_MTIME="$(stat -c %Y "$COMPOSE_FILE" 2>/dev/null || stat -f %m "$COMPOSE_FILE" 2>/dev/null || echo 0)"

declare -a SERVICES=()
refresh_services() {
  local now_mtime
  now_mtime="$(stat -c %Y "$COMPOSE_FILE" 2>/dev/null || stat -f %m "$COMPOSE_FILE" 2>/dev/null || echo 0)"
  if (( ${#SERVICES[@]} == 0 )) || [[ "$now_mtime" != "$COMPOSE_MTIME" ]]; then
    COMPOSE_MTIME="$now_mtime"
    if c config --services >/dev/null 2>&1; then
      mapfile -t SERVICES < <(c config --services | sed '/^\s*$/d' | sort -u)
    else
      mapfile -t SERVICES < <(docker ps -a --format '{{.Names}}' \
        | sed -n "s/^${COMPOSE_PROJECT_NAME}-\([a-zA-Z0-9_.-]\+\)-[0-9]\+$/\1/p" \
        | sort -u)
    fi
    echo "(services refreshed from ${COMPOSE_FILE} @ ${COMPOSE_MTIME})"
  fi
}

has_service() {
  local s="$1"
  for x in "${SERVICES[@]:-}"; do
    [[ "$x" == "$s" ]] && return 0
  done
  return 1
}
any_service_matching() {
  local pat="$1"
  for x in "${SERVICES[@]:-}"; do
    [[ "$x" =~ $pat ]] && { echo "$x"; return 0; }
  done
  return 1
}

# -------- Vault helpers --------
print_vault_install_instructions() {
  cat <<'EOS'

Vault CLI not found. Install on Ubuntu via APT:

  # prerequisites
  sudo apt-get update && sudo apt-get install -y gpg

  # add HashiCorp’s signing key
  curl -fsSL https://apt.releases.hashicorp.com/gpg \
    | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg

  # add the repository
  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] \
  https://apt.releases.hashicorp.com $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/hashicorp.list

  # install Vault
  sudo apt-get update && sudo apt-get install -y vault

Alternative (snap):
  sudo snap install vault

EOS
}

check_vault_cli() {
  echo "▶️  Checking Vault CLI on host PATH…"
  if command -v vault >/dev/null 2>&1; then
    echo "✅ Vault found: $(vault version 2>/dev/null || echo 'version unknown')"
    local va="${VAULT_ADDR:-<unset>}"
    local vt="<unset>"; [[ -n "${VAULT_TOKEN:-}" ]] && vt="<set>"
    echo "   VAULT_ADDR=${va}   VAULT_TOKEN=${vt}"
    read -r -p "Run 'vault status' now (uses VAULT_ADDR=${VAULT_ADDR:-http://127.0.0.1:8200}, VAULT_TOKEN=${VAULT_TOKEN:-root})? [y/N] " ans || true
    if [[ "${ans:-}" =~ ^[Yy]$ ]]; then
      set +e
      VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}" VAULT_TOKEN="${VAULT_TOKEN:-root}" vault status || true
      set -e
    fi
  else
    echo "❌ Vault CLI not found on PATH."
    print_vault_install_instructions
  fi
}

vcmd() { VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}" VAULT_TOKEN="${VAULT_TOKEN:-root}" vault "$@"; }

vault_enabled_oidc() {
  vcmd auth list 2>/dev/null | awk 'NR>2 && $1 ~ /^oidc\// {found=1} END{exit !found}'
}

verify_vault_oidc() {
  echo; echo "🔎 Verifying Vault OIDC mount, config, and role…"
  echo "— auth mounts (filtered to oidc):"
  if vcmd auth list -detailed >/dev/null 2>&1; then
    vcmd auth list -detailed | sed -n '/^path\s*oidc\//,/^$/p' || true
  else
    vcmd auth list | sed -n '1,2d;/^oidc\//p' || true
  fi

  echo; echo "— OIDC config:"
  if command -v jq >/dev/null 2>&1; then
    vcmd read -format=json auth/oidc/config | jq '.data' || true
  else
    vcmd read auth/oidc/config || true
  fi

  echo; echo "— OIDC roles:"
  if command -v jq >/dev/null 2>&1; then
    vcmd list -format=json auth/oidc/role | jq -r '.[]' || true
  else
    vcmd list auth/oidc/role || true
  fi

  echo; echo "— Role details (vault):"
  if command -v jq >/dev/null 2>&1; then
    vcmd read -format=json auth/oidc/role/vault | jq '.data' || true
  else
    vcmd read auth/oidc/role/vault || true
  fi
  echo
}

setup_vault_oidc() {
  if ! command -v vault >/dev/null 2>&1; then
    echo "❌ Vault CLI not found; cannot configure OIDC."
    print_vault_install_instructions
    return 1
  fi

  echo "▶️  Using VAULT_ADDR=${VAULT_ADDR:-http://127.0.0.1:8200}  VAULT_TOKEN=${VAULT_TOKEN:-root}"
  echo "▶️  Checking Vault availability…"
  if ! vcmd status >/dev/null 2>&1; then
    echo "❌ Cannot reach Vault at ${VAULT_ADDR:-http://127.0.0.1:8200}. Is it running and accessible?"
    return 1
  fi

  if vault_enabled_oidc; then
    echo "ℹ️  OIDC auth method already enabled at path 'oidc/'."
    read -r -p "Reset OIDC mount (disable → enable) to a known-good state? [y/N] " ans || true
    if [[ "${ans:-}" =~ ^[Yy]$ ]]; then
      set +e
      vcmd auth disable oidc >/dev/null 2>&1
      set -e
      vcmd auth enable oidc
    fi
  else
    echo "▶️  Enabling OIDC auth method…"
    vcmd auth enable oidc
  fi

  echo "▶️  Writing OIDC config (issuer/keycloak on localhost)…"
  vcmd write auth/oidc/config \
    oidc_discovery_url="http://localhost:8080/realms/OSSS" \
    oidc_client_id="vault" \
    oidc_client_secret="password" \
    default_role="vault"

  echo "▶️  Writing OIDC role 'vault'…"
  local role_args=(
    "user_claim=email"
    "oidc_scopes=openid,profile,email"
    "allowed_redirect_uris=http://127.0.0.1:8200/ui/vault/auth/oidc/oidc/callback"
    "allowed_redirect_uris=http://localhost:8200/ui/vault/auth/oidc/oidc/callback"
    "allowed_redirect_uris=http://127.0.0.1:8250/oidc/callback"
    "allowed_redirect_uris=http://localhost:8250/oidc/callback"
  )
  vcmd write auth/oidc/role/vault "${role_args[@]}"

  verify_vault_oidc
}

# -------- actions --------
down_profile() { echo "▶️  Down (remove orphans & volumes) for profile '${PROFILE}'…"; run c down --remove-orphans --volumes || true; }
kill_leftovers() {
  echo "▶️  Removing leftover containers for project '${COMPOSE_PROJECT_NAME}'…"
  ids=$(docker ps -a --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" -q)
  if [[ -n "${ids:-}" ]]; then run docker rm -f ${ids}; else echo "(none)"; fi
}
prune_networks() { echo "▶️  Pruning dangling networks…"; run docker network prune -f; }
rm_project_networks() {
  echo "▶️  Removing '${COMPOSE_PROJECT_NAME}_…' networks…"
  nets=$(docker network ls --format '{{.Name}}' | grep -E "^${COMPOSE_PROJECT_NAME}_" || true)
  if [[ -n "${nets:-}" ]]; then run docker network rm ${nets}; else echo "(none)"; fi
}

up_service() {
  local svc="$1"
  echo "▶️  Starting '${svc}'…"
  run c up -d "$svc"
}
recreate_service() {
  local svc="$1"
  echo "▶️  Recreating '${svc}'…"
  run c up --force-recreate "$svc"
}
rebuild_service() {
  local svc="$1"
  echo "▶️  Building (no cache) '${svc}'…"
  run c build --no-cache "$svc"
  echo "▶️  Bringing up '${svc}'…"
  run c up -d "$svc"
}

show_status(){
  echo "▶️  Containers (project ${COMPOSE_PROJECT_NAME}):"
  docker ps -a --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" \
    --format 'table {{.Names}}\t{{.Status}}\t{{.Networks}}'
  echo; echo "▶️  Networks containing '${COMPOSE_PROJECT_NAME}_':"
  docker network ls | (head -n1; grep -E "^.* ${COMPOSE_PROJECT_NAME}_" || true)
}

# -------- logs helpers (PROFILE-FREE) --------
list_services() { refresh_services; printf "%s\n" "${SERVICES[@]:-}"; }

last_container_id() {
  local svc="$1"
  local ids created id newest created_newest
  mapfile -t ids < <(docker ps -a \
    --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" \
    --filter "label=com.docker.compose.service=${svc}" \
    --format '{{.ID}}')
  newest=""
  created_newest=""
  for id in "${ids[@]:-}"; do
    created=$(docker inspect -f '{{.Created}}' "$id" 2>/dev/null || true)
    [[ -z "$created" ]] && continue
    if [[ -z "$created_newest" || "$created" > "$created_newest" ]]; then
      created_newest="$created"; newest="$id"
    fi
  done
  [[ -n "$newest" ]] && echo "$newest"
}

logs_tail_service_any(){
  local svc="$1" lines="${2:-$DEFAULT_TAIL}" rc=0
  [[ "$lines" =~ ^[0-9]+$ ]] || lines="$DEFAULT_TAIL"
  echo "📜 Last ${lines} lines for '${svc}':"
  set +e
  # 🔁 NO --profile here so logs work for all services, profiled or not
  $COMPOSE -f "$COMPOSE_FILE" logs --no-color --tail "$lines" "$svc" 2>&1
  rc=$?
  set -e
  if (( rc != 0 )); then
    local cid
    cid=$(last_container_id "$svc" || true)
    if [[ -n "$cid" ]]; then
      echo "(compose logs unavailable; showing last container $cid)"
      docker logs --tail "$lines" "$cid" || true
    else
      echo "(no logs found for service '$svc')"
    fi
  fi
}

logs_follow_service_any(){
  local svc="$1" rc=0
  echo "📜 Following logs for '${svc}'. Press Ctrl-C to return."
  trap 'echo; echo "↩ Back to logs menu"; trap - INT; return 0' INT
  set +e
  # 🔁 NO --profile here either
  $COMPOSE -f "$COMPOSE_FILE" logs -f --tail "$DEFAULT_TAIL" "$svc"
  rc=$?
  set -e
  if (( rc != 0 )); then
    local cid
    cid=$(last_container_id "$svc" || true)
    if [[ -n "$cid" ]]; then
      echo "(compose stream unavailable; following last container $cid)"
      docker logs -f --tail "$DEFAULT_TAIL" "$cid" || true
    else
      echo "(no container found to follow for service '$svc')"
    fi
  fi
  trap - INT
}

logs_tail_all_any(){
  local n="${1:-$DEFAULT_TAIL}"
  [[ "$n" =~ ^[0-9]+$ ]] || n="$DEFAULT_TAIL"
  echo "📜 Last ${n} lines for ALL services (including stopped if present):"
  local svc
  while read -r svc; do
    [[ -z "$svc" ]] && continue
    echo; echo "===== ${svc} ====="
    logs_tail_service_any "$svc" "$n" || true
  done < <(list_services_logs)
}

set_default_tail(){
  local n
  read -rp "Enter default tail size (current ${DEFAULT_TAIL}): " n || return 0
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "Not a number."; return 1; }
  DEFAULT_TAIL="$n"
  save_config
}

maybe_start_db() {
  local db_svc
  if has_service "kc_postgres"; then db_svc="kc_postgres"
  else db_svc="$(any_service_matching '(^|-)postgres($|-)|(^|-)db($|-)')" || true
  fi
  if [[ -n "${db_svc:-}" ]]; then
    up_service "$db_svc"
  else
    echo "(no database-like service found)"
  fi
}

maybe_recreate_importer() {
  local svc
  if has_service "kc-importer"; then svc="kc-importer"
  elif has_service "kc_importer"; then svc="kc_importer"
  else svc="$(any_service_matching 'importer')" || true
  fi
  if [[ -n "${svc:-}" ]]; then
    recreate_service "$svc"
  else
    echo "(no importer-like service found)"
  fi
}

maybe_recreate_post_import() {
  local svc
  if has_service "kc-post-import"; then svc="kc-post-import"
  else svc="$(any_service_matching 'post[-_]?import')" || true
  fi
  if [[ -n "${svc:-}" ]]; then
    recreate_service "$svc"
  else
    echo "(no post-import-like service found)"
  fi
}

maybe_start_keycloak() {
  local svc
  if has_service "keycloak"; then svc="keycloak"
  else svc="$(any_service_matching '^keycloak($|-)')" || true
  fi
  if [[ -n "${svc:-}" ]]; then
    rebuild_service "$svc"
  else
    echo "(no keycloak service found)"
  fi
}

maybe_run_verify() {
  local svc
  if has_service "kc-verify"; then svc="kc-verify"
  else svc="$(any_service_matching 'verify')" || true
  fi
  if [[ -n "${svc:-}" ]]; then
    recreate_service "$svc"
  else
    echo "(no verify-like service found)"
  fi
}

full_repair(){
  echo "==== Full repair ===="
  down_profile
  kill_leftovers
  prune_networks
  rm_project_networks
  maybe_start_db
  maybe_recreate_importer
  echo "✅ Full repair sequence finished."
}
pick_service() {
  refresh_services
  # Count safely even if SERVICES is unset/empty
  local svc_count=0
  if [[ ${#SERVICES[@]+x} ]]; then
    svc_count=${#SERVICES[@]}
  fi

  if (( svc_count == 0 )); then
    echo "(no services)"
    return 1
  fi

  echo "Available services:"
  local i
  for (( i=0; i<svc_count; i++ )); do
    printf "  %2d) %s\n" "$((i+1))" "${SERVICES[$i]}"
  done

  local inp
  read -rp "Pick a number or type a service name: " inp || return 1
  if [[ "$inp" =~ ^[0-9]+$ ]] && (( inp>=1 && inp<=svc_count )); then
    echo "${SERVICES[$((inp-1))]}"
  else
    echo "$inp"
  fi
}

# -------- logs submenu --------
logs_menu() {
  local tail_n="${TAIL:-$DEFAULT_TAIL}"
  local choice svc_count svc
  local __LOG_SERVICES=()

  while true; do
    refresh_services
    mapfile -t __LOG_SERVICES < <(list_services_logs)
    svc_count="${#__LOG_SERVICES[@]}"

    echo
    echo "==== Logs Menu ===="
    echo "Enter a number to follow that service's logs."
    echo "a) follow ALL services"
    echo "t) tail ALL services (with fallback)"
    echo "d) last-run details for a service"
    echo "s) set default tail (currently ${DEFAULT_TAIL})"
    echo "r) refresh services   b) back   q) quit"
    echo

    if (( svc_count == 0 )); then
      echo "(No services found for project ${COMPOSE_PROJECT_NAME})"
    else
      local i
      for ((i=0;i<svc_count;i++)); do
        printf "  %2d) %s\n" "$((i+1))" "${__LOG_SERVICES[$i]}"
      done
    fi

    read -rp "Choice: " choice || return 0
    case "$choice" in
      b|B) return 0 ;;
      q|Q) echo "Bye!"; exit 0 ;;
      r|R) continue ;;
      s|S) set_default_tail ;;
      a|A)
        echo "Following logs for ALL services (all profiles). Ctrl-C to return…"
        mapfile -t _profs < <(compose_profiles)
        _args=( -f "$COMPOSE_FILE" )
        if ((${#_profs[@]})); then
          for _p in "${_profs[@]}"; do _args+=( --profile "$_p" ); done
        fi
        ( trap - INT; $COMPOSE "${_args[@]}" logs -f --tail "$tail_n" ) || true
        ;;
      t|T)
        logs_tail_all_any "$tail_n"
        ;;
      d|D)
        echo "Enter service name for last-run details (or number):"
        read -r svc || continue
        if [[ "$svc" =~ ^[0-9]+$ ]]; then
          (( svc>=1 && svc<=svc_count )) && svc="${__LOG_SERVICES[$((svc-1))]}"
        fi
        print_last_run_details "$svc" || true
        ;;
      ''|*[!0-9]*)
        echo "Unknown choice: ${choice}"
        ;;
      *)
        if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
          echo "Unknown choice: ${choice}"
          continue
        fi
        if (( choice < 1 || choice > svc_count )); then
          echo "Invalid number: ${choice}"
          continue
        fi
        svc="${__LOG_SERVICES[$((choice-1))]}"
        echo "Following logs for service: ${svc} (Ctrl-C to return)…"
        ( trap - INT; logs_follow_service_any "$svc" ) || true
        ;;
    esac
  done
}

# -------- main menu --------
menu() {
  while true; do
    refresh_services
    echo
    echo "==============================================="
    echo " Menu (project: ${COMPOSE_PROJECT_NAME})"
    echo " File: ${COMPOSE_FILE}   Profile: ${PROFILE}"
    echo " Services: ${#SERVICES[@]}"
    echo "==============================================="
    echo " 1) Start all services"
    echo " 2) Down ALL (remove-orphans, volumes)"
    echo " 3) Remove leftover containers for project"
    echo " 4) Prune dangling networks"
    echo " 5) Logs submenu"
    echo " 6) Rebuild ALL services (no cache)"
    echo "  q) Quit"
    echo "-----------------------------------------------"
    read -rp "Select an option: " ans || exit 0
    case "${ans}" in
      1)  start_all_services ;;
      2)  down_all ;;
      3)  kill_leftovers ;;
      4)  prune_networks ;;
      5)  logs_menu ;;
      6)  rebuild_all_services ;;
      q|Q) echo "Bye!"; exit 0 ;;
      *) echo "Unknown choice: ${ans}" ;;
    esac
  done
}

menu
