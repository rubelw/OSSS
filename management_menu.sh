#!/usr/bin/env bash
# management_menu.sh (Podman-only)
# - Uses Podman + Podman Compose exclusively
# - Adds 127.0.0.1 keycloak.local to /etc/hosts if missing
# - Has helpers to start profiles and view logs
# - Runs build_realm.py after Keycloak is up

set -Eeuo pipefail

# -------- dotenv loader --------
load_dotenv() {
  local candidate="${1:-}"
  [[ -z "$candidate" ]] && return 0
  [[ -f "$candidate" ]] || return 0
  echo "🔧 Loading environment from: $candidate"
  # shellcheck disable=SC1090
  set -a; source "$candidate"; set +a
}

# Early dotenv load
if [[ -n "${ENV_FILE:-}" ]]; then
  load_dotenv "$ENV_FILE"
else
  load_dotenv "./.env"
fi

# -------- config / flags --------
PROJECT_DEFAULT="${COMPOSE_PROJECT_NAME:-osss}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
PROFILE="${PROFILE:-seed}"
DEFAULT_TAIL="200"

usage() {
  cat <<EOF
Usage: $0 [-p PROJECT] [-f docker-compose.yml] [-r PROFILE]

Options:
  -p PROJECT      Compose project name (default: ${PROJECT_DEFAULT})
  -f FILE         Compose file path (default: ${COMPOSE_FILE})
  -r PROFILE      Compose profile to target (default: ${PROFILE})
Environment:
  ENV_FILE             Path to a .env file to load first (overrides ./\.env)
  OSSS_SKIP_VENV_CHECK Set to 1 to skip the Python venv check
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

# Late dotenv load (sibling .env next to compose file wins)
compose_dir="$(dirname -- "$COMPOSE_FILE")"
load_dotenv "${compose_dir%/}/.env"

export COMPOSE_PROJECT_NAME="${PROJECT_DEFAULT}"

# -------- ensure /etc/hosts has keycloak.local --------
ensure_hosts_keycloak() {
  local entry="127.0.0.1 keycloak.local"
  if ! grep -Eq '(^|\s)keycloak\.local(\s|$)' /etc/hosts; then
    echo "➕ Adding 'keycloak.local' → 127.0.0.1 to /etc/hosts (sudo may prompt)…"
    echo "$entry" | sudo tee -a /etc/hosts >/dev/null
  fi
}

# -------- Python venv (optional) --------
ensure_python_cmd() {
  command -v python3 >/dev/null 2>&1 && { echo python3; return; }
  command -v python  >/dev/null 2>&1 && { echo python;  return; }
  echo "❌ Python 3 not found." >&2; exit 1
}
in_venv() { [[ -n "${VIRTUAL_ENV:-}" ]]; }

find_upwards() {
  local target="$1" dir="${2:-$PWD}"
  while :; do
    [[ -e "$dir/$target" ]] && { echo "$dir/$target"; return 0; }
    [[ "$dir" == "/" ]] && break
    dir="$(dirname "$dir")"
  done
  return 1
}

install_from_pyproject() {
  local proj_root="$1" py="$2"
  echo "📦 Installing project dependencies from pyproject.toml in: $proj_root"
  ( cd "$proj_root"
    "$py" -m pip install --upgrade pip setuptools wheel
    "$py" -m pip install .
  )
}

ensure_python_venv() {
  [[ "${OSSS_SKIP_VENV_CHECK:-0}" == "1" ]] && return 0
  [[ "${OSSS_VENV_BOOTSTRAPPED:-0}" == "1" ]] && return 0
  local script_dir; script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local pyproject; pyproject="$(find_upwards "pyproject.toml" "$script_dir" || true)"
  [[ -z "$pyproject" ]] && return 0

  local proj_root; proj_root="$(dirname "$pyproject")"
  local py; py="$(ensure_python_cmd)"
  if in_venv; then
    echo "✅ Python virtual environment detected."
    return 0
  fi
  echo "⚠️  Not running inside a Python virtual environment."
  read -r -p "Create and use '$proj_root/.venv' and install packages from pyproject.toml? [Y/n] " ans || true
  if [[ -z "${ans:-}" || "${ans}" =~ ^[Yy]$ ]]; then
    [[ -d "$proj_root/.venv" ]] || "$py" -m venv "$proj_root/.venv"
    # shellcheck disable=SC1091
    source "$proj_root/.venv/bin/activate"
    py="python"
    install_from_pyproject "$proj_root" "$py"
    export OSSS_VENV_BOOTSTRAPPED=1
    exec "$0" "$@"
  fi
}

ensure_python_venv "$@"

# -------- Podman compose selection --------
compose_cmd() {
  if podman compose version >/dev/null 2>&1; then
    echo "podman compose"; return 0
  fi
  if command -v podman-compose >/dev/null 2>&1; then
    echo "podman-compose"; return 0
  fi
  echo "❌ Neither 'podman compose' nor 'podman-compose' found on PATH." >&2
  echo "   macOS: brew install podman podman-compose" >&2
  echo "   Linux: sudo apt/dnf install podman; pipx install podman-compose" >&2
  exit 1
}

ensure_compose_file() {
  [[ -f "$COMPOSE_FILE" ]] || { echo "❌ Compose file not found: $COMPOSE_FILE" >&2; exit 1; }
}

COMPOSE="$(compose_cmd)"
ensure_compose_file

# Convenience wrappers
run() { echo "+ $*"; "$@"; }
c() { $COMPOSE -f "$COMPOSE_FILE" --profile "$PROFILE" "$@"; }

# -------- Service discovery --------
compose_profiles() {
  local out
  if out="$($COMPOSE -f "$COMPOSE_FILE" config --profiles 2>/dev/null)" && [[ -n "$out" ]]; then
    printf '%s\n' "$out" | sed '/^\s*$/d' | sort -u
  else
    awk '
      $1=="profiles:"{inp=1; next}
      inp && $1!~/:/{ sub("-","",$1); print $1 }
      inp && $1~/.:/{ inp=0 }
    ' "$COMPOSE_FILE" | sed '/^\s*$/d' | sort -u
  fi
}

compose_services_base() {
  local out
  if out="$($COMPOSE -f "$COMPOSE_FILE" config --services 2>/dev/null)" && [[ -n "$out" ]]; then
    printf '%s\n' "$out" | sed '/^\s*$/d'
  else
    awk '
      /^services:[[:space:]]*$/ { in_services=1; next }
      in_services && /^[^[:space:]]/ { in_services=0 }
      in_services && /^[[:space:]]{2}[A-Za-z0-9_.-]+:[[:space:]]*$/ {
        s=$0; sub(/^[[:space:]]+/, "", s); sub(/:.*/, "", s); print s
      }
    ' "$COMPOSE_FILE" | sed '/^\s*$/d' | sort -u
  fi
}

compose_services_for_profile() {
  local prof="$1" out
  if out="$($COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null)" && [[ -n "$out" ]]; then
    printf '%s\n' "$out" | sed '/^\s*$/d'
  else
    awk -v target="$prof" '
      /^services:[[:space:]]*$/ { in_services=1; next }
      in_services && /^[^[:space:]]/ { in_services=0 }
      in_services && /^[[:space:]]{2}[A-Za-z0-9_.-]+:[[:space:]]*$/ {
        if (svc_name != "" && matched) { print svc_name }
        matched=0; in_prof=0
        line=$0; sub(/^[[:space:]]+/, "", line); sub(/:.*/, "", line); svc_name=line; next
      }
      in_services && svc_name != "" {
        if ($0 ~ /^[[:space:]]{4}profiles:[[:space:]]*$/) { in_prof=1; next }
        if (in_prof && $0 ~ /^[[:space:]]{2}[A-Za-z0-9_.-]+:[[:space:]]*$/) { in_prof=0 }
        if (in_prof && $0 ~ /^[[:space:]]{6}-[[:space:]]*[A-Za-z0-9_.-]+[[:space:]]*$/) {
          p=$0; sub(/^[[:space:]]*-[[:space:]]*/, "", p); sub(/[[:space:]]*$/, "", p)
          if (p == target) { matched=1 }
        }
      }
      END { if (svc_name != "" && matched) { print svc_name } }
    ' "$COMPOSE_FILE" | sed '/^\s*$/d' | sort -u
  fi
}

compose_services_all() {
  { compose_services_base; while read -r p; do [[ -n "$p" ]] && compose_services_for_profile "$p"; done < <(compose_profiles); } \
  | awk 'NF && !seen[$0]++' | sort -u
}

# -------- Host info --------
show_status(){
  echo "▶️  Containers (project ${COMPOSE_PROJECT_NAME}):"
  podman ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Networks}}' | (head -n1; grep -E "^${COMPOSE_PROJECT_NAME}[-_]" || true)
  echo; echo "▶️  Networks containing '${COMPOSE_PROJECT_NAME}_':"
  podman network ls | (head -n1; grep -E " ${COMPOSE_PROJECT_NAME}_" || true)
}

# -------- logs helpers --------
DEFAULT_TAIL_CONF="${XDG_CONFIG_HOME:-$HOME/.config}/osss-compose-repair.conf"
load_config(){ [[ -f "$DEFAULT_TAIL_CONF" ]] && source "$DEFAULT_TAIL_CONF"; : "${DEFAULT_TAIL:=${DEFAULT_TAIL:-200}}"; }
save_config(){ mkdir -p "$(dirname "$DEFAULT_TAIL_CONF")"; printf "DEFAULT_TAIL=%s\n" "$DEFAULT_TAIL" > "$DEFAULT_TAIL_CONF"; echo "Saved -> $DEFAULT_TAIL_CONF"; }
load_config

last_container_id() {
  local svc="$1" newest="" created_newest="" id created
  mapfile -t ids < <(podman ps -a --filter "label=io.podman.compose.project=${COMPOSE_PROJECT_NAME}" \
                              --filter "label=io.podman.compose.service=${svc}" --format '{{.ID}}' 2>/dev/null || true)
  for id in "${ids[@]:-}"; do
    created=$(podman inspect -f '{{.Created}}' "$id" 2>/dev/null || true)
    [[ -z "$created" ]] && continue
    if [[ -z "$created_newest" || "$created" > "$created_newest" ]]; then created_newest="$created"; newest="$id"; fi
  done
  [[ -n "$newest" ]] && echo "$newest"
}

logs_tail_service_any(){
  local svc="$1" lines="${2:-$DEFAULT_TAIL}" rc=0
  [[ "$lines" =~ ^[0-9]+$ ]] || lines="$DEFAULT_TAIL"
  echo "📜 Last ${lines} lines for '${svc}':"
  set +e
  $COMPOSE -f "$COMPOSE_FILE" logs --no-color --tail "$lines" "$svc" 2>&1
  rc=$?
  set -e
  if (( rc != 0 )); then
    local cid; cid=$(last_container_id "$svc" || true)
    if [[ -n "${cid:-}" ]]; then
      echo "(compose logs unavailable; showing last container $cid)"
      podman logs --tail "$lines" "$cid" || true
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
  $COMPOSE -f "$COMPOSE_FILE" logs -f --tail "$DEFAULT_TAIL" "$svc"
  rc=$?
  set -e
  if (( rc != 0 )); then
    local cid; cid=$(last_container_id "$svc" || true)
    if [[ -n "${cid:-}" ]]; then
      echo "(compose stream unavailable; following last container $cid)"
      podman logs -f --tail "$DEFAULT_TAIL" "$cid" || true
    else
      echo "(no container found to follow for service '$svc')"
    fi
  fi
  trap - INT
}

list_services_logs(){ compose_services_all; }

logs_tail_all_any(){
  local n="${1:-$DEFAULT_TAIL}"
  [[ "$n" =~ ^[0-9]+$ ]] || n="$DEFAULT_TAIL"
  echo "📜 Last ${n} lines for ALL services:"
  while read -r svc; do
    [[ -z "$svc" ]] && continue
    echo; echo "===== ${svc} ====="
    logs_tail_service_any "$svc" "$n" || true
  done < <(list_services_logs)
}

set_default_tail(){
  local n; read -rp "Enter default tail size (current ${DEFAULT_TAIL}): " n || return 0
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "Not a number."; return 1; }
  DEFAULT_TAIL="$n"; save_config
}

# --- Return-to-menu prompt ---
prompt_return() {
  echo
  # don’t die if stdin isn’t a tty; just sleep briefly so users see output
  if [[ -t 0 ]]; then
    read -r -p "✅ Done. Press Enter to return to the menu..." _
  else
    echo "✅ Done. Returning to menu…"
    sleep 1
  fi
}


# Force-recreate all services in a given profile (works with both `podman compose` and `podman-compose`)
up_force_profile() {
  local prof="$1"

  # discover services in the profile (never fail hard)
  mapfile -t svcs < <(compose_services_for_profile "$prof" 2>/dev/null || true)
  if ((${#svcs[@]}==0)); then
    echo "⚠️  No services declare profile '${prof}' in ${COMPOSE_FILE:-docker-compose.yml}."
    prompt_return
    return 0
  fi

  echo "🛠️  Forcing recreate of ${#svcs[@]} service(s) in profile '${prof}': ${svcs[*]}"

  # make this block failure-tolerant, then restore -e
  set +e

  # Stop via compose first (ok if already stopped)
  $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" stop "${svcs[@]}"

  # Hard-stop & remove any existing containers/pods that belong to these services
  for svc in "${svcs[@]}"; do
    ids=$(podman ps -a \
      --filter "label=io.podman.compose.project=${COMPOSE_PROJECT_NAME}" \
      --filter "label=io.podman.compose.service=${svc}" -q 2>/dev/null)
    if [[ -n "$ids" ]]; then
      # stop pods that contain these containers (ignore errors)
      pods=$(podman inspect -f '{{.PodName}}' $ids 2>/dev/null | awk 'NF && $0!="<no value>" && !seen[$0]++')
      if [[ -n "$pods" ]]; then podman pod stop $pods >/dev/null 2>&1; fi
      # remove containers + anon volumes
      podman rm -f -v $ids >/dev/null 2>&1
      # remove pods if any
      if [[ -n "$pods" ]]; then podman pod rm -f $pods >/dev/null 2>&1; fi
    fi
  done

  # Bring them back up (ignore “network in use”/pod removal errors, compose will reuse)
  $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d --no-deps --force-recreate

  set -e

  prompt_return
  return 0
}

# -------- profile helpers --------
start_profiles_blind() {
  local args=( -f "$COMPOSE_FILE" )
  for p in "$@"; do args+=( --profile "$p" ); done
  echo "▶️  Starting services for profiles: $* …"
  run $COMPOSE "${args[@]}" up -d
}

start_profile_services() {
  local prof="$1"
  mapfile -t svcs < <(compose_services_for_profile "$prof" || true)
  ((${#svcs[@]})) || { echo "(no services discovered in profile '${prof}')"; prompt_return; return 1; }
  echo "▶️  Starting ${#svcs[@]} service(s) in profile '${prof}': ${svcs[*]}"
  run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d
  prompt_return
}

# elastic under Podman: skip filebeat/filebeat-setup (docker-only bind paths)
start_profile_elastic() {
  ensure_hosts_keycloak
  echo "▶️  Starting services for profile 'elastic' (and enabling 'keycloak' profile for config validation)…"
  run $COMPOSE -f "$COMPOSE_FILE" --profile elastic up -d --no-deps shared-vol-init elasticsearch kibana kibana-pass-init api-key-init
  prompt_return
}

start_profile_app()         { ensure_hosts_keycloak; run $COMPOSE -f "$COMPOSE_FILE" --profile app         up -d --no-deps; prompt_return; }
start_profile_web_app()     { ensure_hosts_keycloak; run $COMPOSE -f "$COMPOSE_FILE" --profile web-app     up -d --no-deps; prompt_return; }
start_profile_vault()       { ensure_hosts_keycloak; run $COMPOSE -f "$COMPOSE_FILE" --profile vault       up -d --no-deps; prompt_return; }

start_profile_trino() {
  ensure_hosts_keycloak
  up_force_profile trino
}

start_profile_airflow()     { ensure_hosts_keycloak; run $COMPOSE -f "$COMPOSE_FILE" --profile airflow     up -d --no-deps; prompt_return; }
start_profile_superset()    { ensure_hosts_keycloak; run $COMPOSE -f "$COMPOSE_FILE" --profile superset    up -d --no-deps; prompt_return; }
start_profile_openmetadata(){ ensure_hosts_keycloak; run $COMPOSE -f "$COMPOSE_FILE" --profile openmetadata up -d --no-deps; prompt_return; }
start_profile_consul()      { ensure_hosts_keycloak; run $COMPOSE -f "$COMPOSE_FILE" --profile consul      up -d --no-deps; prompt_return; }

# Keycloak start with realm bootstrap
run_build_realm() {
  local script_dir; script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local py="python"; in_venv || py="$(ensure_python_cmd)"
  local script_path=""
  if   [[ -f "$script_dir/build_realm.py" ]]; then script_path="$script_dir/build_realm.py"
  elif [[ -f "./build_realm.py" ]]; then         script_path="./build_realm.py"
  else script_path="$(find_upwards "build_realm.py" "$script_dir" || true)"
  fi
  [[ -z "$script_path" ]] && { echo "ℹ️  build_realm.py not found; skipping."; return 0; }
  local url="${KEYCLOAK_URL:-http://localhost:8080}"
  if command -v curl >/dev/null 2>&1; then
    echo "⏳ Waiting for Keycloak at ${url} …"
    local i=0; local max=60
    until curl -fsS "${url}" >/dev/null 2>&1 || (( i >= max )); do sleep 1; i=$((i+1)); done
  fi
  echo "🔧 Running realm bootstrap: ${script_path}"
  "$py" -u "$script_path" || echo "⚠️ build_realm.py exited non-zero (continuing)."
}

start_keycloak_services() {
  ensure_hosts_keycloak
  echo "▶️  Starting Keycloak profile/services…"
  mapfile -t svcs < <(compose_services_for_profile "keycloak" || true)
  if ((${#svcs[@]})); then
    run $COMPOSE -f "$COMPOSE_FILE" --profile keycloak up -d --no-deps "${svcs[@]}"
    run_build_realm
    prompt_return
    return 0
  fi
  if $COMPOSE -f "$COMPOSE_FILE" config --services 2>/dev/null | grep -qx "keycloak"; then
    run $COMPOSE -f "$COMPOSE_FILE" up -d --no-deps keycloak
    run_build_realm
    prompt_return
    return 0
  fi
  echo "⚠️  Couldn’t find a 'keycloak' profile or service."
  echo "   Services: $(compose_services_base | tr '\n' ' ')"
  prompt_return
  return 1
}

# -------- Trino cert helpers --------
create_trino_cert() {
  local dir="trino/etc/keystore"
  local ks="$dir/trino-keystore.p12"
  mkdir -p "$dir"

  echo "▶️  Recreating self-signed cert + PKCS#12 keystore for Trino in $dir"

  rm -f "$ks"

  keytool -genkeypair \
    -alias trino \
    -keyalg RSA -keysize 2048 \
    -storetype PKCS12 \
    -keystore "$ks" \
    -storepass changeit -keypass changeit \
    -validity 825 \
    -dname "CN=trino" \
    -ext "SAN=dns:localhost,dns:trino,dns:trino.local,ip:127.0.0.1" \
    -ext "BasicConstraints=ca:false" \
    -ext "ExtendedKeyUsage=serverAuth" \
    -noprompt || { echo "❌ keytool failed"; prompt_return; return 1; }

  echo "✅ Trino keystore created: $ks (password: changeit)"
  echo "🔎 Keystore contents:"
  keytool -list -keystore "$ks" -storepass changeit
  prompt_return
}

# -------- teardown & cleanup --------
# Down only the TRINO profile (containers + their named/anon volumes), leave networks/other profiles intact
down_profile_interactive() {
  local prof="trino"
  local compose="${COMPOSE:-docker compose}"
  local compose_file_flag=()
  [[ -n "$COMPOSE_FILE" ]] && compose_file_flag=(-f "$COMPOSE_FILE")

  mapfile -t trino_svcs < <(
    awk -v prof="$prof" '
      BEGIN{in_services=0; svc=""; in_profiles=0}
      /^\s*services\s*:/ {in_services=1; next}
      in_services {
        if ($0 ~ /^[^[:space:]]/ && $0 !~ /^\s/) { in_services=0; next }
        if (match($0, /^[[:space:]]{2}([A-Za-z0-9._-]+):[[:space:]]*$/, m)) {
          svc=m[1]; in_profiles=0; next
        }
        if (svc && match($0, /^[[:space:]]{4}profiles:[[:space:]]*\[(.*)\][[:space:]]*$/, m)) {
          s=m[1]; gsub(/[[:space:]]/,"",s); n=split(s, arr, ",")
          for(i=1;i<=n;i++) if (arr[i]==prof) { print svc; break }
          next
        }
        if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*$/) { in_profiles=1; next }
        if (in_profiles) {
          if ($0 ~ /^[[:space:]]{6}-[[:space:]]*([A-Za-z0-9._-]+)/) {
            p=$0; sub(/^[[:space:]]*-/, "", p); gsub(/^[[:space:]]+/, "", p)
            if (p==prof) print svc
            next
          }
          if ($0 ~ /^[[:space:]]{4}[A-Za-z0-9._-]+:/) { in_profiles=0 }
        }
      }
    ' "${COMPOSE_FILE:-docker-compose.yml}" | sort -u
  )

  if ((${#trino_svcs[@]}==0)); then
    echo "⚠️  No services declare profile '${prof}' in ${COMPOSE_FILE:-docker-compose.yml}."
    echo "Nothing to do. (Won’t call 'compose down' to avoid impacting other resources.)"
    prompt_return
    return 0
  fi

  echo "▶️  Stopping ${#trino_svcs[@]} service(s) in profile '${prof}': ${trino_svcs[*]}"
  $compose "${compose_file_flag[@]}" stop "${trino_svcs[@]}" || true

  echo "🧹  Removing containers (and their volumes) for: ${trino_svcs[*]}"
  if [[ "$COMPOSE" == "podman-compose" ]]; then
    for svc in "${trino_svcs[@]}"; do
      ids=$(podman ps -a \
        --filter "label=io.podman.compose.project=${COMPOSE_PROJECT_NAME}" \
        --filter "label=io.podman.compose.service=${svc}" -q || true)
      [[ -n "${ids:-}" ]] && podman rm -f -v $ids || true
    done
  else
    $compose "${compose_file_flag[@]}" rm -f -s -v "${trino_svcs[@]}" || true
  fi

  echo "✅  Done. Networks and non-'${prof}' services were left untouched."
  prompt_return
}

down_all() {
  echo "▶️  Down ALL profiles (remove orphans & volumes)…"
  run $COMPOSE -f "$COMPOSE_FILE" down --remove-orphans --volumes || true
  echo "▶️  Removing '${COMPOSE_PROJECT_NAME}_…' networks…"
  nets=$(podman network ls --format '{{.Name}}' | grep -E "^${COMPOSE_PROJECT_NAME}_" || true)
  [[ -n "${nets:-}" ]] && podman network rm ${nets} || echo "(none)"
  echo "▶️  Removing named volumes for project…"
  vols=$(podman volume ls --format '{{.Name}}' | grep -E "^${COMPOSE_PROJECT_NAME}_" || true)
  [[ -n "${vols:-}" ]] && podman volume rm ${vols} || echo "(none)"
  prompt_return
}

# -------- menu --------
refresh_services() { :; } # compatibility no-op

logs_menu() {
  local tail_n="${TAIL:-$DEFAULT_TAIL}"
  local choice svc_count svc
  local __LOG_SERVICES=()
  while true; do
    mapfile -t __LOG_SERVICES < <(compose_services_all)
    svc_count="${#__LOG_SERVICES[@]}"
    echo
    echo "==== Logs Menu ===="
    echo "Enter a number to follow that service's logs."
    echo "a) follow ALL services"
    echo "t) tail ALL services"
    echo "s) set default tail (currently ${DEFAULT_TAIL})"
    echo "r) refresh services   b) back   q) quit"
    echo
    if (( svc_count == 0 )); then
      echo "(No services found for project ${COMPOSE_PROJECT_NAME})"
    else
      local i; for ((i=0;i<svc_count;i++)); do printf "  %2d) %s\n" "$((i+1))" "${__LOG_SERVICES[$i]}"; done
    fi
    read -rp "Choice: " choice || return 0
    case "$choice" in
      b|B) return 0 ;;
      q|Q) echo "Bye!"; exit 0 ;;
      r|R) continue ;;
      s|S) set_default_tail ;;
      a|A)
        echo "Following logs for ALL services. Ctrl-C to return…"
        ( trap - INT; $COMPOSE -f "$COMPOSE_FILE" logs -f --tail "$tail_n" ) || true
        ;;
      t|T) logs_tail_all_any "$tail_n" ;;
      *)
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice>=1 && choice<=svc_count )); then
          svc="${__LOG_SERVICES[$((choice-1))]}"
          echo "Following logs for service: ${svc} (Ctrl-C to return)…"
          ( trap - INT; logs_follow_service_any "$svc" ) || true
        else
          echo "Unknown choice: ${choice}"
        fi
        ;;
    esac
  done
}

menu() {
  ensure_hosts_keycloak
  while true; do
    echo
    echo "==============================================="
    echo " Menu (project: ${COMPOSE_PROJECT_NAME})"
    echo " File: ${COMPOSE_FILE}   Profile: ${PROFILE}"
    echo "==============================================="
    echo " 1) Start profile 'keycloak'"
    echo " 2) Start profile 'app' (keycloak must be up)"
    echo " 3) Start profile 'web-app' (keycloak must be up)"
    echo " 4) Start profile 'elastic'"
    echo " 5) Start profile 'vault' (keycloak must be up)"
    echo " 6) Start profile 'consul'"
    echo " 7) Start ALL services (enable all profiles)"
    echo " 8) Start profile 'trino' (keycloak must be up)"
    echo " 9) Start profile 'airflow' (keycloak must be up)"
    echo "10) Start profile 'superset' (keycloak must be up)"
    echo "11) Start profile 'openmetadata' (elastic+keycloak should be up)"
    echo "12) Down a profile (remove-orphans, volumes)"
    echo "13) Down ALL (remove-orphans, volumes)"
    echo "14) Show status"
    echo "15) Logs submenu"
    echo "16) Create Trino server certificate + keystore"
    echo "  q) Quit"
    echo "-----------------------------------------------"
    read -rp "Select an option: " ans || exit 0
    case "${ans}" in
      1)  start_keycloak_services ;;
      2)  start_profile_app ;;
      3)  start_profile_web_app ;;
      4)  start_profile_elastic ;;
      5)  start_profile_vault ;;
      6)  start_profile_consul ;;
      7)  start_profiles_blind $(compose_profiles) ;;
      8)  start_profile_trino ;;
      9)  start_profile_airflow ;;
      10) start_profile_superset ;;
      11) start_profile_openmetadata ;;
      12) down_profile_interactive ;;
      13) down_all ;;
      14) show_status; prompt_return ;;
      15) logs_menu ;;
      16) create_trino_cert ;;
      q|Q) echo "Bye!"; exit 0 ;;
      *)   echo "Unknown choice: ${ans}"; prompt_return ;;
    esac
  done
}

menu
