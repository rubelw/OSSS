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
FORCE_VOLUME_REMOVE=1

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
  # Prefer podman compose; fall back to podman-compose or docker compose.
  if command -v podman >/dev/null 2>&1 && podman --help | grep -qE '\bcompose\b'; then
    echo "podman compose"
  elif command -v podman-compose >/dev/null 2>&1; then
    echo "podman-compose"
  elif command -v docker >/dev/null 2>&1; then
    echo "docker compose"
  else
    echo "❌ Neither podman-compose nor docker was found." >&2
    return 127
  fi
}

__compose_cmd() {
  if command -v podman >/dev/null 2>&1 && podman --help | grep -qE '\bcompose\b'; then
    echo "podman compose"
  elif command -v podman-compose >/dev/null 2>&1; then
    echo "podman-compose"
  elif command -v docker >/dev/null 2>&1; then
    echo "docker compose"
  else
    echo "❌ Neither podman-compose nor docker found." >&2
    return 127
  fi
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

# get compose project name the same way compose will (respect env/flags)
__compose_project_name() {
  # Respect COMPOSE_PROJECT_NAME if set; otherwise let compose compute.
  if [ -n "${COMPOSE_PROJECT_NAME:-}" ]; then
    echo "$COMPOSE_PROJECT_NAME"
  else
    # Ask the compose CLI directly (works with both podman-compose and docker compose)
    # Falls back to directory name if config doesn’t expose name.
    local CMD; CMD="$(__compose_cmd)" || return $?
    # docker compose: `config --services` doesn’t show project; but `config --hash` not universal.
    # Use ps to read labels if running; else derive from current dir.
    local pn
    pn="$($CMD config 2>/dev/null | awk -F: '/^name:/{gsub(/[[:space:]]/,"",$2);print $2; exit}')" || true
    if [ -n "$pn" ]; then echo "$pn"; else basename "$PWD"; fi
  fi
}

compose_down_profile() {
  local prof="$1"
  # Try a native compose down first (best at cleaning pods, networks, orphans)
  # Fall back silently if the CLI doesn’t support flags.
  set +e
  compose_stop_rm_profile "$prof" 2>/dev/null
  rc=$?
  set -e
  return $rc
}

# list profiles (quote-safe)
__compose_profiles() {
  awk '
    BEGIN{in_services=0; svc=""; in_profiles=0}
    /^[[:space:]]*services[[:space:]]*:/ {in_services=1; next}
    in_services {
      if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) {in_services=0; next}
      if ($0 ~ /^[[:space:]][[:space:]][A-Za-z0-9._-]+:[[:space:]]*$/) { svc=$0; sub(/^[[:space:]]+/, "", svc); sub(/:.*/, "", svc); in_profiles=0; next }
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*\[/) {
        s=$0; sub(/^[^[]*\[/,"",s); sub(/\].*$/,"",s)
        gsub(/[[:space:]"]/,"",s); gsub(/[[:space:]]'\''/,"",s)
        n=split(s, arr, ","); for(i=1;i<=n;i++) if (arr[i]!="") seen[arr[i]]=1
        next
      }
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*$/) { in_profiles=1; next }
      if (in_profiles && $0 ~ /^[[:space:]]{6}-[[:space:]]*/) {
        p=$0; sub(/^[^ -]*-/,"",p); gsub(/^[[:space:]'"'"'"]+|[[:space:]'"'"'"]+$/,"",p)
        if (p!="") seen[p]=1; next
      }
      if (in_profiles && $0 ~ /^[[:space:]]{4}[A-Za-z0-9._-]+:/) { in_profiles=0 }
    }
    END{ for (k in seen) print k }
  ' "${COMPOSE_FILE:-docker-compose.yml}" | sort -u
}

# Back-compat shim for older callsites
__compose_services_for_profile() { compose_services_for_profile "$@"; }

# services for a given profile (quote-safe)
# Return services in a profile that have a 'build:' section
__compose_services_with_build_for_profile() {
  local prof="$1"
  local cfg allowed=()

  # Services that belong to this profile (from the compose file itself)
  mapfile -t allowed < <(__compose_services_for_profile "$prof")

  # Try a profile-scoped config (compose v2); fall back to full config
  if ! cfg="$($COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config 2>/dev/null)"; then
    cfg="$($COMPOSE -f "$COMPOSE_FILE" config 2>/dev/null || true)"
  fi

  # Parse config YAML for services that contain a top-level 'build:' key
  mapfile -t all_with_build < <(awk '
    BEGIN{in_services=0; svc=""; has_build=0}
    /^[[:space:]]*services[[:space:]]*:/ {in_services=1; next}
    in_services {
      # leaving services block
      if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) {
        if (svc!="" && has_build) print svc
        in_services=0; svc=""; has_build=0; next
      }
      # service header
      if ($0 ~ /^[[:space:]]{2}[A-Za-z0-9._-]+:[[:space:]]*$/) {
        if (svc!="" && has_build) print svc
        line=$0; sub(/^[[:space:]]+/,"",line); sub(/:.*/,"",line)
        svc=line; has_build=0; next
      }
      # build key at indent 4
      if (svc!="" && $0 ~ /^[[:space:]]{4}build[[:space:]]*:/) { has_build=1 }
    }
    END{ if (svc!="" && has_build) print svc }
  ' <<<"$cfg")

  # If we know which services are in the profile, filter against them
  if ((${#allowed[@]})); then
    for s in "${all_with_build[@]}"; do
      for a in "${allowed[@]}"; do
        [[ "$s" == "$a" ]] && echo "$s" && break
      done
    done | awk 'NF && !seen[$0]++'
  else
    printf "%s\n" "${all_with_build[@]}" | awk 'NF && !seen[$0]++'
  fi
}

# Prompt to rebuild images for services with build: in a profile
maybe_build_profile() {
  local prof="$1"
  mapfile -t build_svcs < <(__compose_services_with_build_for_profile "$prof")
  ((${#build_svcs[@]})) || return 0

  echo "🧱 The following services in profile '${prof}' have a build section:"
  echo "    ${build_svcs[*]}"

  local ans; read -rp "Rebuild these images before starting '${prof}'? [y/N] " ans || true
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    local nocache=""
    read -rp "Use --no-cache? [y/N] " ans || true
    [[ "$ans" =~ ^[Yy]$ ]] && nocache="--no-cache"

    echo "+ $COMPOSE -f \"$COMPOSE_FILE\" --profile \"$prof\" build $nocache ${build_svcs[*]}"
    $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" build $nocache "${build_svcs[@]}"
  fi
}


compose_profiles() {
  # Emits unique profile names found in services.*.profiles (inline list or multiline).
  awk '
    BEGIN{in_services=0; svc=""; in_profiles=0}
    /^[[:space:]]*services[[:space:]]*:/ {in_services=1; next}
    in_services {
      # top-level key ends services
      if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) {in_services=0; next}
      # service header (two spaces then "name:")
      if ($0 ~ /^[[:space:]][[:space:]][A-Za-z0-9._-]+:[[:space:]]*$/) {
        svc=$0; sub(/^[[:space:]]+/, "", svc); sub(/:.*/, "", svc); in_profiles=0; next
      }
      # inline profiles: "    profiles: [a,b,c]"
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*\[/) {
        s=$0; sub(/^[^[]*\[/,"",s); sub(/\].*$/,"",s); gsub(/[[:space:]]/,"",s)
        n=split(s, arr, ","); for(i=1;i<=n;i++) if (arr[i]!="") seen[arr[i]]=1
        next
      }
      # multiline profiles: start
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*$/) { in_profiles=1; next }
      # multiline items: "      - prof"
      if (in_profiles && $0 ~ /^[[:space:]]{6}-[[:space:]]*[A-Za-z0-9._-]+/) {
        p=$0; sub(/^[^ -]*-/,"",p); gsub(/^[[:space:]]+|[[:space:]]+$/,"",p); if(p!="") seen[p]=1; next
      }
      # any new key at indent 4 ends profiles block
      if (in_profiles && $0 ~ /^[[:space:]]{4}[A-Za-z0-9._-]+:/) { in_profiles=0 }
    }
    END{ for (k in seen) print k }
  ' "${COMPOSE_FILE:-docker-compose.yml}" | sort -u
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
  # Arg: profile name; emits service names belonging to that profile
  prof="$1"
  awk -v prof="$prof" '
    BEGIN{in_services=0; svc=""; in_profiles=0}
    /^[[:space:]]*services[[:space:]]*:/ {in_services=1; next}
    in_services {
      if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) {in_services=0; next}
      if ($0 ~ /^[[:space:]][[:space:]][A-Za-z0-9._-]+:[[:space:]]*$/) {
        line=$0; sub(/^[[:space:]]+/, "", line); sub(/:.*/, "", line)
        svc=line; in_profiles=0; next
      }
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*\[/) {
        s=$0; sub(/^[^[]*\[/,"",s); sub(/\].*$/,"",s); gsub(/[[:space:]]/,"",s)
        n=split(s, arr, ","); for(i=1;i<=n;i++) if (arr[i]==prof) { print svc; break }
        next
      }
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*$/) { in_profiles=1; next }
      if (in_profiles && $0 ~ /^[[:space:]]{6}-[[:space:]]*[A-Za-z0-9._-]+/) {
        p=$0; sub(/^[^ -]*-/,"",p); gsub(/^[[:space:]]+|[[:space:]]+$/,"",p)
        if (p==prof) print svc; next
      }
      if (in_profiles && $0 ~ /^[[:space:]]{4}[A-Za-z0-9._-]+:/) { in_profiles=0 }
    }
  ' "${COMPOSE_FILE:-docker-compose.yml}" | sort -u
}


compose_services_all() {
  { compose_services_base; while read -r p; do [[ -n "$p" ]] && compose_services_for_profile "$p"; done < <(compose_profiles); } \
  | awk 'NF && !seen[$0]++' | sort -u
}

# -------- Host info --------
show_status(){
  echo "▶️  Containers (project ${COMPOSE_PROJECT_NAME}):"
  printf "NAMES\tSTATUS\tNETWORKS\n"
  podman ps -a --format '{{.Names}}\t{{.Status}}\t{{.Networks}}' \
    | (grep -E "^${COMPOSE_PROJECT_NAME}[-_]" || true)

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
  mapfile -t ids < <(podman ps -a \
  --filter "label=io.podman.compose.project=${COMPOSE_PROJECT_NAME}" \
  --filter "label=io.podman.compose.service=${svc}" \
  -q 2>/dev/null || true)

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
  echo "▶️  Starting services for profiles: $* …"

  # Offer rebuilds profile-by-profile before bringing anything up
  for p in "$@"; do
    maybe_build_profile "$p"
    args+=( --profile "$p" )
  done

  run $COMPOSE "${args[@]}" up -d
}


start_profile_with_build_prompt() {
  local prof="$1"
  ensure_hosts_keycloak
  maybe_build_profile "$prof"
  run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d
  prompt_return
}

start_profile_services() {
  local CMD; CMD="$(__compose_cmd)" || return $?
  mapfile -t svcs < <($CMD -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF')
  if [ "${#svcs[@]}" -eq 0 ]; then
    mapfile -t svcs < <(compose_services_for_profile "$prof" 2>/dev/null || true)
  fi

  ((${#svcs[@]})) || { echo "(no services discovered in profile '${prof}')"; prompt_return; return 1; }
  echo "▶️  Starting ${#svcs[@]} service(s) in profile '${prof}': ${svcs[*]}"
  run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d
  prompt_return
}

down_all() {
  local CMD; CMD="$(__compose_cmd)" || return $?
  local PROJECT; PROJECT="$(__compose_project_name)"

  echo "🔻 Bringing down ALL compose services for project '${PROJECT}'…"
  set +e
  $COMPOSE -f "$COMPOSE_FILE" down --remove-orphans -v 2>/dev/null
  set -e

  # Sweep any project-prefixed volumes and common networks
  echo "🧹 Sweeping leftover project volumes and networks…"
  mapfile -t VOLS < <(podman volume ls --format '{{.Name}}' | grep -E "^${PROJECT}_" || true)
  for v in "${VOLS[@]}"; do podman volume rm -f "$v" >/dev/null 2>&1 || true; done

  for net in "${PROJECT}_osss-net" "${PROJECT}_default"; do
    if podman network exists "$net" 2>/dev/null; then
      if ! podman network inspect "$net" --format '{{len .Containers}}' 2>/dev/null | awk '{exit ($1>0)}'; then
        podman network rm "$net" >/dev/null 2>&1 || true
      fi
    fi
  done

  echo "✅ All services down for project '${PROJECT}'."
  prompt_return
}

# elastic under Podman: skip filebeat/filebeat-setup (docker-only bind paths)
start_profile_elastic() {
  ensure_hosts_keycloak
  maybe_build_profile elastic
  echo "▶️  Starting services for profile 'elastic' (and enabling 'keycloak' profile for config validation)…"
  run $COMPOSE -f "$COMPOSE_FILE" --profile elastic up -d --no-deps \
      shared-vol-init elasticsearch kibana kibana-pass-init api-key-init
  prompt_return
}


start_profile_app()          { start_profile_with_build_prompt app; }
start_profile_web_app()      { start_profile_with_build_prompt web-app; }
start_profile_vault()        { start_profile_with_build_prompt vault; }

start_profile_trino() {
  ensure_hosts_keycloak
  maybe_build_profile trino
  up_force_profile trino
}

start_profile_airflow()      { start_profile_with_build_prompt airflow; }
start_profile_superset()     { start_profile_with_build_prompt superset; }
start_profile_openmetadata() { start_profile_with_build_prompt openmetadata; }
start_profile_consul()       { start_profile_with_build_prompt consul; }


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

# Stop & remove only services that belong to a given profile.
# No networks/volumes are removed globally; anonymous volumes attached to the removed containers are cleaned.
compose_stop_rm_profile() {
  local prof="$1"
  local CMD; CMD="$(__compose_cmd)" || return $?

  # Find the services that belong to this profile
  mapfile -t SVCS < <($CMD -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF')
  if ((${#SVCS[@]}==0)); then
    echo "No services found for profile '$prof'."
    return 0
  fi

  echo "+ $CMD -f \"$COMPOSE_FILE\" stop ${SVCS[*]}"
  $CMD -f "$COMPOSE_FILE" stop "${SVCS[@]}" || true

  # podman compose / docker compose support 'rm'; podman-compose does not (we'll clean by labels later)
  if $CMD rm -h >/dev/null 2>&1; then
    echo "+ $CMD -f \"$COMPOSE_FILE\" rm -s -f -v ${SVCS[*]}"
    $CMD -f "$COMPOSE_FILE" rm -s -f -v "${SVCS[@]}" || true
  fi
}


start_keycloak_services() {
  ensure_hosts_keycloak
  local CMD; CMD="$(__compose_cmd)" || return $?
  local PROJECT; PROJECT="$(__compose_project_name)"

  echo "▶️  Starting Keycloak…"
  echo "ℹ️  Compose command: $CMD"
  echo "ℹ️  Project: $PROJECT   File: ${COMPOSE_FILE:-docker-compose.yml}"

  local svcs=()
  if compose_supports_profile; then
    mapfile -t svcs < <($CMD -f "$COMPOSE_FILE" --profile "keycloak" config --services 2>/dev/null | awk 'NF')
    if [ "${#svcs[@]}" -eq 0 ]; then
      mapfile -t svcs < <(compose_services_for_profile "keycloak" 2>/dev/null || true)
    fi
  fi

  if ((${#svcs[@]})); then
    maybe_build_profile keycloak
    echo "🔎 Found profile 'keycloak' with services: ${svcs[*]}"
    echo "+ $CMD --profile keycloak up -d --no-deps ${svcs[*]}"
    $CMD --profile keycloak up -d --no-deps "${svcs[@]}"
    prompt_return; return 0
  fi

  mapfile -t ALL_SERVS < <(compose_list_services)
  want=(keycloak kc_postgres)
  chosen=()
  for w in "${want[@]}"; do for s in "${ALL_SERVS[@]}"; do [[ "$s" == "$w" ]] && { chosen+=("$w"); break; }; done; done

  if ((${#chosen[@]}==0)); then
    echo "⚠️  Neither a 'keycloak' profile nor 'keycloak' service was detected."
    echo "   Services available: ${ALL_SERVS[*]}"
    prompt_return; return 1
  fi

  echo "🔎 Starting services (no profile): ${chosen[*]}"
  compose_up_services "${chosen[@]}"
  prompt_return
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

__compose_named_volumes_for_service() {
  # Arg1: service name
  local svc="$1"
  awk -v target="$svc" '
    BEGIN{
      in_services=0; in_svc=0; in_vols=0; in_item=0; # YAML-ish state
    }
    /^[[:space:]]*services[[:space:]]*:/ { in_services=1; next }

    in_services {
      # leaving services block
      if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) { in_services=0; in_svc=0; in_vols=0; next }

      # service header (two spaces, then "<name>:")
      if ($0 ~ /^[[:space:]]{2}[A-Za-z0-9._-]+:[[:space:]]*$/) {
        line=$0; sub(/^[[:space:]]+/,"",line); sub(/:.*/,"",line);
        in_svc = (line==target); in_vols=0; in_item=0; next
      }

      # only parse volumes inside the target service
      if (in_svc) {
        # start of volumes block
        if ($0 ~ /^[[:space:]]{4}volumes:[[:space:]]*$/) { in_vols=1; in_item=0; next }

        # inline list: volumes: [a:/x, b:/y]
        if ($0 ~ /^[[:space:]]{4}volumes:[[:space:]]*\[/) {
          s=$0; sub(/^[^[]*\[/,"",s); sub(/\].*$/,"",s)
          n=split(s, arr, ",")
          for(i=1;i<=n;i++){
            v=arr[i]; gsub(/^[[:space:]]+|[[:space:]]+$/,"",v)
            # grab left of ":" if present
            split(v, kv, ":"); src=kv[1]
            # ignore binds like ./ or / or ${...}
            if (src !~ /^(\.\/|\/|\$\{)/ && src!="") print src
          }
          next
        }

        if (in_vols) {
          # end volumes block if new key at same indent
          if ($0 ~ /^[[:space:]]{4}[A-Za-z0-9._-]+:/) { in_vols=0; in_item=0; next }

          # list item start
          if ($0 ~ /^[[:space:]]{6}-[[:space:]]*/) {
            in_item=1
            # shorthand: "- volname:/container/path"
            item=$0; sub(/^[^ -]*-[[:space:]]*/,"",item)
            if (item ~ /:/) {
              split(item, kv, ":"); src=kv[1]
              gsub(/[[:space:]]*/,"",src)
              if (src !~ /^(\.\/|\/|\$\{)/ && src!="") print src
              in_item=0
            }
            next
          }

          # long form inside list item: "source: volname"
          if (in_item && $0 ~ /^[[:space:]]{8}source:[[:space:]]*/) {
            src=$0; sub(/^[^:]*:[[:space:]]*/,"",src)
            gsub(/^[[:space:]]+|[[:space:]]+$/,"",src)
            if (src !~ /^(\.\/|\/|\$\{)/ && src!="") print src
            next
          }
        }
      }
    }
  ' "${COMPOSE_FILE:-docker-compose.yml}" | awk 'NF && !seen[$0]++'
}

# Return 0 if compose supports --profile (podman compose / docker compose), 1 otherwise (podman-compose)
compose_supports_profile() {
  local cmd="$(__compose_cmd)" || return 1
  # crude but reliable: podman-compose is a python wrapper and doesn't accept 'help --profile'
  if command -v podman-compose >/dev/null 2>&1 && [[ "$cmd" == podman-compose* ]]; then
    return 1
  fi
  return 0
}

# Safe "config --services" into a bash array
compose_list_services() {
  local cmd="$(__compose_cmd)" || return 1
  mapfile -t __SERVS < <($cmd config --services 2>/dev/null | awk 'NF')
  printf "%s\n" "${__SERVS[@]}"
}

# Convenience runner that prints the command first
compose_up_services() {
  local cmd="$(__compose_cmd)" || return 1
  echo "+ $cmd up -d --no-deps $*"
  $cmd up -d --no-deps "$@"
}



# Remove named volumes for selected services (Bash-3 compatible).
# Enable with REMOVE_VOLUMES=1 (default skip). Add FORCE_VOLUME_REMOVE=1 to
# stop/remove same-project containers still using those volumes before deleting them.
remove_volumes_for_services() {
  # helpers (no associative arrays)
  _add_unique() {  # _add_unique VAR value
    local __var="$1" __val="$2" __e
    eval "for __e in \"\${${__var}[@]}\"; do [[ \"\$__e\" == \"\$__val\" ]] && return 0; done"
    eval "${__var}+=(\"\$__val\")"
  }
  _in_list() { local n="$1"; shift; for e in "$@"; do [[ "$e" == "$n" ]] && return 0; done; return 1; }

  local project="$1"; shift
  local do_rm="${REMOVE_VOLUMES:-0}"
  [[ "${1:-}" == "--volumes" ]] && { do_rm=1; shift; }
  local svcs=( "$@" )

  if [[ "$do_rm" != "1" ]]; then
    echo "ℹ️  Volume removal is DISABLED (set REMOVE_VOLUMES=1 or pass --volumes)."
    return 0
  fi

  local CMD cfg
  CMD="$(__compose_cmd)" || { echo "⚠️  compose cmd unavailable"; return 0; }
  if ! cfg="$($CMD config 2>/dev/null)"; then
    echo "⚠️  Could not run 'compose config'; skipping volume cleanup."
    return 0
  fi

  # top-level volume keys (normalized by `compose config`)
  local topkeys=()
  while IFS= read -r k; do [[ -n "$k" ]] && _add_unique topkeys "$k"; done < <(
    awk '
      /^[[:space:]]*volumes:[[:space:]]*$/ { in_vols=1; next }
      in_vols {
        if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) { in_vols=0; next }
        if ($0 ~ /^[[:space:]]{2}[A-Za-z0-9._-]+:[[:space:]]*$/) {
          s=$0; sub(/^[[:space:]]+/, "", s); sub(/:.*/, "", s); print s
        }
      }' <<<"$cfg" | sort -u
  )

  # named volumes referenced by selected services
  local named=()
  for svc in "${svcs[@]}"; do
    while IFS= read -r vk; do
      # keep only volumes that exist as top-level keys; add project prefix
      _in_list "$vk" "${topkeys[@]}" && _add_unique named "${project}_${vk}"
    done < <(__compose_named_volumes_for_service "$svc")
  done


  # attached volumes still visible on any remaining containers for these services (should be none, but be safe)
  local attached=()
  for svc in "${svcs[@]}"; do
    while IFS= read -r cid; do
      [[ -z "$cid" ]] && continue
      while IFS= read -r v; do [[ -n "$v" ]] && _add_unique attached "$v"; done < <(
        podman inspect --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{"\n"}}{{end}}{{end}}' "$cid" 2>/dev/null
      )
    done < <(podman ps -a --filter "label=io.podman.compose.project=$project" \
                           --filter "label=io.podman.compose.service=$svc" -q)
  done

  echo "🔎 Named volumes to consider: ${named[*]:-(none)}"
  echo "🔎 Attached volumes to consider: ${attached[*]:-(none)}"

  # union
  local to_rm=()
  local v; for v in "${named[@]}";    do _add_unique to_rm "$v"; done
           for v in "${attached[@]}"; do _add_unique to_rm "$v"; done
  [[ "${#to_rm[@]}" -eq 0 ]] && { echo "ℹ️  No volumes eligible for removal."; return 0; }

  # remove, optionally forcing same-project users to stop
  for v in "${to_rm[@]}"; do
    # existence check using name-only listing (works regardless of columns)
    if ! podman volume ls --format '{{.Name}}' | grep -qx "$v"; then
      echo "   • $v (does not exist)"
      continue
    fi
    # who’s using it?
    mapfile -t USERS < <(podman ps -a --filter "volume=$v" -q)
    if ((${#USERS[@]})); then
      if [[ "${FORCE_VOLUME_REMOVE:-0}" == "1" ]]; then
        # only stop/remove users that belong to the same project (by label)
        mapfile -t PROJ_USERS < <(
          for id in "${USERS[@]}"; do
            lab=$(podman inspect -f '{{or (index .Config.Labels "io.podman.compose.project") (index .Config.Labels "com.docker.compose.project")}}' "$id" 2>/dev/null)
            [[ "$lab" == "$project" ]] && echo "$id"
          done
        )
        if ((${#PROJ_USERS[@]})); then
          echo "   • $v (in use by ${#USERS[@]} container/s → stopping same-project users: ${#PROJ_USERS[@]})"
          podman stop "${PROJ_USERS[@]}" || true
          podman rm -fv "${PROJ_USERS[@]}" || true
          # re-check other users
          mapfile -t USERS < <(podman ps -a --filter "volume=$v" -q)
        fi
      fi
    fi
    if ((${#USERS[@]})); then
      echo "   • $v (skipping — still used by ${#USERS[@]} container/s)"
      continue
    fi
    echo "🧹 Removing volume: $v"
    podman volume rm -f "$v" || echo "   • failed to remove $v (continuing)"
  done

  # If nothing matched through compose parsing, sweep all project-prefixed volumes.
  if [[ "${#to_rm[@]}" -eq 0 ]]; then
    echo "ℹ️  No service-mapped volumes found; falling back to project-prefixed sweep."
    while IFS= read -r v; do
      [[ -n "$v" ]] && _add_unique to_rm "$v"
    done < <(podman volume ls --format '{{.Name}}' | grep -E "^${project}_" || true)
  fi

}


down_profile_interactive() {
  local CMD; CMD="$(__compose_cmd)" || return $?
  local PROJECT; PROJECT="$(__compose_project_name)"

  echo "ℹ️  Using compose command: $CMD"
  echo "ℹ️  Compose project: $PROJECT"
  echo "ℹ️  Compose file:    ${COMPOSE_FILE:-docker-compose.yml}"

  mapfile -t PROFILES < <(__compose_profiles)
  echo "🔎 Detected profiles: ${PROFILES[*]:-(none)}"
  if [ "${#PROFILES[@]}" -eq 0 ]; then
    echo "⚠️  No profiles found."
    return 0
  fi

  echo "Available profiles:"
  local i=1
  for p in "${PROFILES[@]}"; do printf "  %2d) %s\n" "$i" "$p"; i=$((i+1)); done
  echo "  q) Cancel"
  read -r -p "Select a profile to take down: " choice || return 0
  case "$choice" in q|Q) echo "❌ Cancelled."; return 0 ;; esac

  local prof
  if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#PROFILES[@]}" ]; then
    prof="${PROFILES[$((choice-1))]}"
    echo "✅ Selected by number: $prof"
  else
    prof="$choice"
    echo "✅ Selected by name: $prof"
  fi
  prof="${prof%\"}"; prof="${prof#\"}"; prof="${prof%\'}"; prof="${prof#\'}"
  echo "ℹ️  Normalized profile: $prof"

  # Discover services via the compose CLI (authoritative), with a parser fallback
  mapfile -t SVCS < <($CMD -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF')
  if [ "${#SVCS[@]}" -eq 0 ]; then
    mapfile -t SVCS < <(compose_services_for_profile "$prof" 2>/dev/null || true)
  fi
  echo "🔎 Services in profile '$prof': ${SVCS[*]:-(none)}"
  if [ "${#SVCS[@]}" -eq 0 ]; then
    echo "⚠️  No services declare profile '${prof}'. Nothing to do."
    return 0
  fi

  echo "🚧 Taking down profile '${prof}' services: ${SVCS[*]}"

  # ---- VERBOSE EXECUTION SCOPE ----
  {
    set -x

    # 0) Stop & remove ONLY the services in this profile (never use 'down' here)
    echo "+ $CMD -f \"$COMPOSE_FILE\" stop ${SVCS[*]}"
    $CMD -f "$COMPOSE_FILE" stop "${SVCS[@]}" || true

    if $CMD rm -h >/dev/null 2>&1; then
      echo "+ $CMD -f \"$COMPOSE_FILE\" rm -s -f -v ${SVCS[*]}"
      $CMD -f "$COMPOSE_FILE" rm -s -f -v "${SVCS[@]}" || true
    fi


    # 1) Resolve containers by label (compose project + service)
    declare -a CIDS=()
    for svc in "${SVCS[@]}"; do
      while read -r id; do
        [[ -n "$id" ]] && CIDS+=("$id")
      done < <(podman ps -a \
                 --filter "label=io.podman.compose.project=$PROJECT" \
                 --filter "label=io.podman.compose.service=$svc" \
                 -q)
    done
    echo "🔎 Container IDs to stop/rm: ${CIDS[*]:-(none)}"

    # 2) Find related pods (if any)
    declare -a PODS=()
    if ((${#CIDS[@]})); then
      while read -r pod; do
        [[ -n "$pod" && "$pod" != "<no value>" ]] && PODS+=("$pod")
      done < <(podman inspect -f '{{.PodName}}' "${CIDS[@]}" 2>/dev/null | awk 'NF && !seen[$0]++')
    fi
    echo "🔎 Pods to stop/rm: ${PODS[*]:-(none)}"

    # 3) Disable auto-restart (prevents immediate respawn)
    if ((${#CIDS[@]})); then
      for id in "${CIDS[@]}"; do
        podman update --restart=no "$id" || true
      done
    fi


    # 4) Gather attached volumes before containers disappear (dedupe without assoc arrays)
    mapfile -t VOL_ATTACHED < <(
      for id in "${CIDS[@]}"; do
        podman inspect --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{"\n"}}{{end}}{{end}}' "$id" 2>/dev/null
      done | awk 'NF && !seen[$0]++'
    )
    echo "🔎 Candidate volumes (attached): ${VOL_ATTACHED[*]:-(none)}"

    # 5) Stop pods first (if any), then containers by ID, then by service name (fallback)
    if ((${#CIDS[@]})); then
      podman rm -fv "${CIDS[@]}" || true
    fi
    podman rm -fv "${SVCS[@]}" || true
    if ((${#PODS[@]})); then
      podman pod rm -f "${PODS[@]}" || true
    fi

    # 6) Drop any attached volumes we captured
    for v in "${VOL_ATTACHED[@]}"; do
      podman volume rm -f "$v" || true
    done

    set +x
  }

  # 7) Report what’s still running for this project after teardown
  echo "🔎 Remaining containers matching project='$PROJECT':"
  podman ps --format '{{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}' \
    --filter "label=io.podman.compose.project=$PROJECT" | sed 's/^/  /' || true

  # also remove named volumes referenced by those services
  remove_volumes_for_services "$PROJECT" --volumes "${SVCS[@]}"
  echo "✅ Done with profile '${prof}'."
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
