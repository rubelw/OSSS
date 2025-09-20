#!/usr/bin/env bash
# osss-compose-repair.sh
# Dynamic Compose repair + logs utility that adapts to docker-compose.yml (and profile).
# - Auto-detects services per compose file/profile
# - Builds menu entries only for present services
# - Safe fallbacks when compose logs aren't available
# - Persists default tail size in ~/.config/osss-compose-repair.conf
# - NEW: Ensures a Python venv is active; offers to create .venv and install from pyproject.toml

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
  ENV_FILE                Path to a .env file to load first (overrides ./\.env)
  OSSS_SKIP_VENV_CHECK    Set to 1 to skip the Python venv check
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

# -------- Python venv helpers (NEW) --------
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- start only the 'keycloak' profile services ---
KEYCLOAK_PROFILE="${KEYCLOAK_PROFILE:-keycloak}"

# Start services under a profile; if profile not found, fall back to name-matching
start_profile_with_fallback() {
  local prof="$1"
  # First: try proper profile discovery
  mapfile -t svcs < <(compose_services_for_profile "$prof" || true)

  if ((${#svcs[@]}==0)); then
    echo "(no services discovered in profile '${prof}' for ${COMPOSE_FILE})"
    echo "→ Available profiles: $(compose_profiles | tr '\n' ' ' || true)"
    echo "→ Falling back to name match: services containing '${prof}'…"

    # Fallback: pick services whose names contain the token (case-insensitive)
    mapfile -t svcs < <(
      compose_services_base | awk -v p="$prof" 'BEGIN{IGNORECASE=1} index($0,p)>0'
    )
    if ((${#svcs[@]}==0)); then
      echo "(no services with names matching '${prof}')"
      return 1
    fi
  fi

  echo "▶️  Starting ${#svcs[@]} service(s): ${svcs[*]}"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" up -d --build "${svcs[@]}"
  else
    run $COMPOSE -f "$COMPOSE_FILE" up -d "${svcs[@]}"
  fi
}

# Start services strictly by service-name list (no --profile)
start_services_by_name() {
  local svcs=("$@")
  ((${#svcs[@]})) || { echo "(no service names supplied)"; return 1; }
  echo "▶️  Starting ${#svcs[@]} service(s) by name: ${svcs[*]}"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" up -d --build "${svcs[@]}"
  else
    run $COMPOSE -f "$COMPOSE_FILE" up -d "${svcs[@]}"
  fi
}

# Return 0 if any container name suggests the token is already running (SILENT)
docker_has_container_like() {
  local token="$1"
  mapfile -t __ALL_NAMES < <(docker ps -a --format '{{.Names}}' 2>/dev/null || true)
  ((${#__ALL_NAMES[@]})) || return 1
  local n
  for n in "${__ALL_NAMES[@]}"; do
    [[ "$n" == "$token" ]] && return 0
    if [[ "$n" =~ (^|[_-])${token}([_-][0-9]+)?$ ]]; then return 0; fi
    [[ "$n" == *"$token"* ]] && return 0
  done
  return 1
}


# --- interactively 'down' a single compose profile (or ALL) ---
down_profile_interactive() {
  mapfile -t profs < <(compose_profiles || true)
  if ((${#profs[@]}==0)); then
    echo "(no profiles discovered in ${COMPOSE_FILE})"
    return 1
  fi

  echo "Profiles in ${COMPOSE_FILE}:"
  local i
  for ((i=0;i<${#profs[@]};i++)); do
    printf "  %2d) %s\n" "$((i+1))" "${profs[$i]}"
  done
  echo "  a) ALL (same as 'Down ALL')"
  echo

  local choice prof
  read -rp "Choose a profile to tear down: " choice || return 1

  case "$choice" in
    a|A) down_all; return ;;
    ''|*[!0-9]*)
      prof="$choice"
      [[ -z "$prof" ]] && { echo "No selection made."; return 1; }
      if ! printf '%s\n' "${profs[@]}" | grep -qx -- "$prof"; then
        echo "Unknown profile: '$prof'"; return 1
      fi
      ;;
    *)
      if (( choice < 1 || choice > ${#profs[@]} )); then
        echo "Invalid number: ${choice}"; return 1
      fi
      prof="${profs[$((choice-1))]}"
      ;;
  esac

  if [[ "$prof" == "trino" ]]; then
    echo "▶️  Down (containers + anonymous volumes) for profile 'trino' ONLY…"
    down_services_for_profile_only "trino"
  else
    echo "▶️  Down (remove orphans & volumes) for profile '${prof}'…"
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" down --remove-orphans --volumes || true
  fi
}


# --- generic starter for any compose profile ---
start_profile_services() {
  local prof="$1"
  mapfile -t svcs < <(compose_services_for_profile "$prof" || true)
  if ((${#svcs[@]}==0)); then
    echo "(no services discovered in profile '${prof}' for ${COMPOSE_FILE})"
    return 1
  fi
  echo "▶️  Starting ${#svcs[@]} service(s) in profile '${prof}': ${svcs[*]}"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d --build "${svcs[@]}"
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d "${svcs[@]}"
  fi
}

# Start all services for one or more profiles (no discovery)
start_profiles_blind() {
  local args=( -f "$COMPOSE_FILE" )
  for p in "$@"; do args+=( --profile "$p" ); done
  echo "▶️  Starting services for profiles: $* …"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE "${args[@]}" up -d --build
  else
    run $COMPOSE "${args[@]}" up -d
  fi
}


start_profile_app() {
  local prof="app"
  echo "▶️  Starting services for profile 'app' (and enabling 'keycloak' profile for config validation)…"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile keycloak up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile keycloak up -d --no-deps
  fi
}

start_profile_app() {
  local prof="app"
  echo "▶️  Starting services for profile 'app' (and enabling 'keycloak' profile for config validation)…"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile keycloak up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile keycloak up -d --no-deps
  fi
}

# Your compose shows 'elastic' (not 'elastics'):
start_profile_elastic() {
  local prof="elastic"
  echo "▶️  Starting services for profile 'elastic' (and enabling 'keycloak' profile for config validation)…"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile elastic up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile elastic up -d --no-deps
  fi
}

# Robust Keycloak starter:
# 1) Try KEYCLOAK_PROFILE (default "keycloak")
# 2) If none, start any service whose *service key* contains "keycloak"
# 3) If still none, but a keycloak-ish container exists, just "up" by name "keycloak"
start_keycloak_services() {
  local prof="${KEYCLOAK_PROFILE:-keycloak}"

  # Try the profile first
  mapfile -t svcs < <(compose_services_for_profile "$prof" 2>/dev/null || true)
  if ((${#svcs[@]})); then
    echo "▶️  Starting ${#svcs[@]} service(s) in profile '${prof}': ${svcs[*]}"
    if [[ "${BUILD_ALL:-0}" == "1" ]]; then
      run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d --no-deps --build "${svcs[@]}"
    else
      run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d --no-deps "${svcs[@]}"
    fi
    return 0
  fi

  # No services under that profile → fall back to name match
  echo "(no services discovered in profile '${prof}' for ${COMPOSE_FILE})"
  echo "→ Available profiles: $(compose_profiles | tr '\n' ' ' || true)"
  echo "→ Falling back to name match: services containing 'keycloak'…"

  mapfile -t svcs < <(compose_services_base | awk 'BEGIN{IGNORECASE=1} index($0,"keycloak")>0')
  if ((${#svcs[@]})); then
    start_services_by_name "${svcs[@]}"
    return 0
  fi

  # Final fallback: a container that already exists (compose prefixing etc.)
  if docker_has_container_like "keycloak"; then
    echo "ℹ️  A 'keycloak' container exists; attempting to start service 'keycloak' by name…"
    start_services_by_name "keycloak" || true
    return 0
  fi

  echo "⚠️  Couldn’t find a 'keycloak' profile or service key."
  echo "   Services in this compose file are: $(compose_services_base | tr '\n' ' ')"
  return 1
}

# Your compose shows 'vault' explicitly, so this will Just Work now:
start_profile_vault() {
  local prof="vault"
  echo "▶️  Starting services for profile 'vault' (and enabling 'keycloak' profile for config validation)…"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile vault up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile vault up -d --no-deps
  fi
}

start_profile_datalake_data() {
  local prof="datalake_data"
  echo "▶️  Starting services for profile 'datalake_data' (and enabling 'keycloak' profile for config validation)…"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile datalake_data up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile datalake_data up -d --no-deps
  fi
}

start_profile_trino() {
  local prof="trino"
  echo "▶️  Starting services for profile 'trino' (and enabling 'keycloak' profile for config validation)…"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile trino up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile trino up -d --no-deps
  fi
}

start_profile_airflow() {
  local prof="airflow"
  echo "▶️  Starting services for profile 'airflow' (and enabling 'keycloak' profile for config validation)…"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile airflow up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile airflow up -d --no-deps
  fi
}
start_profile_superset() {
  local prof="superset"
  echo "▶️  Starting services for profile 'superset' (and enabling 'keycloak' profile for config validation)…"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile superset up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile superset up -d --no-deps
  fi
}

start_profile_openmetadata() {
  local prof="openmetadata"
  echo "▶️  Starting services for profile 'openmetadata' (and enabling 'keycloak' profile for config validation)…"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile openmetadata up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile openmetadata up -d --no-deps
  fi
}
# Your profiles list showed 'consol' (typo in compose?). Try both:
start_profile_consul() {
  local prof="consul"
  echo "▶️  Starting services for profile 'consul' (and enabling 'keycloak' profile for config validation)…"
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile consul up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" --profile consul up -d --no-deps
  fi
}

find_upwards() {
  # find_upwards <filename> [start_dir]
  local target="$1"
  local dir="${2:-$PWD}"
  while :; do
    if [[ -e "$dir/$target" ]]; then
      echo "$dir/$target"
      return 0
    fi
    [[ "$dir" == "/" ]] && break
    dir="$(dirname "$dir")"
  done
  return 1
}

ensure_python_cmd() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
  elif command -v python >/dev/null 2>&1; then
    echo "python"
  else
    echo "❌ Python is not installed or not on PATH." >&2
    echo "   Please install Python 3.8+ and re-run this script." >&2
    exit 1
  fi
}

in_venv() {
  # Detect venv via env var or python base_prefix comparison
  if [[ -n "${VIRTUAL_ENV:-}" ]]; then
    return 0
  fi
  local py; py="$(ensure_python_cmd)"
  "$py" - <<'PY' >/dev/null 2>&1
import sys
sys.exit(0 if getattr(sys, "base_prefix", sys.prefix) != sys.prefix else 1)
PY
}

install_from_pyproject() {
  local proj_root="$1"
  local py="$2"

  echo "📦 Installing project dependencies from pyproject.toml in: $proj_root"
  ( cd "$proj_root"
    "$py" -m pip install --upgrade pip setuptools wheel
    # Install the project, which installs [project] dependencies in pyproject.toml
    # If you prefer editable installs for development, swap to: pip install -e .
    "$py" -m pip install .
  )
}

ensure_python_venv() {
  # Skip if asked
  if [[ "${OSSS_SKIP_VENV_CHECK:-0}" == "1" ]]; then
    return 0
  fi

  # Only run once in a re-exec loop
  if [[ "${OSSS_VENV_BOOTSTRAPPED:-0}" == "1" ]]; then
    return 0
  fi

  # Look for a pyproject.toml near here or above
  local pyproject
  pyproject="$(find_upwards "pyproject.toml" "$script_dir" || true)"
  if [[ -z "$pyproject" ]]; then
    # No pyproject found; nothing to install, but still nudge about venv best practice
    if ! in_venv; then
      echo "ℹ️  No pyproject.toml found; skipping Python dependency install."
      echo "    (Tip: create a venv and a pyproject.toml to manage tooling for this repo.)"
    fi
    return 0
  fi

  local proj_root; proj_root="$(dirname "$pyproject")"
  local py; py="$(ensure_python_cmd)"

  if in_venv; then
    echo "✅ Python virtual environment detected."
    return 0
  fi

  echo "⚠️  This script is not running inside a Python virtual environment."
  echo "    Project detected at: $proj_root"
  read -r -p "Create and use '$proj_root/.venv' and install packages from pyproject.toml? [Y/n] " ans || true
  if [[ -z "${ans:-}" || "${ans:-}" =~ ^[Yy]$ ]]; then
    # Create venv if missing
    if [[ ! -d "$proj_root/.venv" ]]; then
      echo "🧰 Creating virtual environment at $proj_root/.venv"
      "$py" -m venv "$proj_root/.venv"
    else
      echo "♻️  Using existing virtual environment at $proj_root/.venv"
    fi

    # Activate venv for the current shell
    # shellcheck disable=SC1091
    source "$proj_root/.venv/bin/activate"

    # Recompute python pointer (now inside venv)
    py="python"

    # Install deps from pyproject.toml
    install_from_pyproject "$proj_root" "$py"

    # Re-exec this script under the activated venv to ensure the rest of the run uses it.
    echo "🔁 Restarting script inside the virtual environment…"
    export OSSS_VENV_BOOTSTRAPPED=1
    exec "$0" "$@"
  else
    echo "➡️  Continuing without a Python virtual environment."
  fi
}

# Run the venv bootstrap early
ensure_python_venv "$@"

# -------- helpers --------

# --- helpers: detect containers and build one-shot stub overlay ---

# Stop & remove ONLY the services that belong to a given profile.
# - Stops containers for those services
# - Removes those containers and their *anonymous* volumes (-v)
# - Does NOT prune project networks or named volumes (e.g., datalake_data)
down_services_for_profile_only() {
  local prof="$1"
  mapfile -t svcs < <(compose_services_for_profile "$prof" || true)
  if ((${#svcs[@]}==0)); then
    echo "(no services discovered in profile '${prof}' for ${COMPOSE_FILE})"
    return 0
  fi

  echo "▶️  Stopping ${#svcs[@]} service(s) in profile '${prof}': ${svcs[*]}"
  run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" stop "${svcs[@]}" || true

  echo "🗑  Removing containers for profile '${prof}' (and their anonymous volumes)…"
  # Use rm -fsv on the exact services; this avoids touching other profiles' resources.
  run $COMPOSE -f "$COMPOSE_FILE" rm -fsv "${svcs[@]}" || true

  # Optional: remove orphan containers that belong to these services (defensive)
  echo "🧹 Cleaning up any orphan containers for '${COMPOSE_PROJECT_NAME}' & services: ${svcs[*]}"
  local ids
  ids="$(docker ps -a \
    --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" \
    --format '{{.ID}} {{.Names}}' \
    | awk -v ORS=' ' '{
        name=$2
        for(i=3;i<=NF;i++) name=name" "$i
        print $1" "name"\n"
      }' \
    | awk -v proj="${COMPOSE_PROJECT_NAME}" '
        { id=$1; name=$0; sub(/^[^ ]+ /,"",name);
          # if name includes any of the service keys, mark for deletion
          split("'"${svcs[*]}"'", S, " ")
          for (i in S) if (index(name, S[i])>0) print id
        }')" || true
  if [[ -n "${ids:-}" ]]; then
    run docker rm -f ${ids} || true
  fi

  echo "✅ Done tearing down profile '${prof}' without touching other profiles’ volumes."
}

# Convenience: apply to current $PROFILE if it's set, else refuse
down_current_profile_services_only() {
  local prof="${PROFILE:-}"
  if [[ -z "$prof" ]]; then
    echo "❌ PROFILE not set; use -r PROFILE or call down_services_for_profile_only <profile>."
    return 1
  fi
  down_services_for_profile_only "$prof"
}


# Return 0 if any Docker container name matches the service token.
# We accept "exact", "<project>-<service>-N", or anything that contains the token
docker_has_container_like() {
  local token="$1"
  # Load all container names once
  mapfile -t __ALL_NAMES < <(docker ps -a --format '{{.Names}}' 2>/dev/null || true)
  ((${#__ALL_NAMES[@]})) || return 1

  local n
  for n in "${__ALL_NAMES[@]}"; do
    # exact match (when user set container_name: token)
    [[ "$n" == "$token" ]] && return 0
    # typical compose name: <project>_<service>_N or <project>-<service>-N
    # allow either '_' or '-' as separators
    if [[ "$n" =~ (^|[_-])${token}([_-][0-9]+)?$ ]]; then
      return 0
    fi
    # looser fallback (contains token)
    [[ "$n" == *"$token"* ]] && return 0
  done
  return 1
}
# Parse undefined services from compose stderr/stdout
parse_undefined_services_from_stderr() {
  sed -nE '
    s/.*undefined service "([^"]+)".*/\1/p;
    s/.*depends on undefined service "([^"]+)".*/\1/p
  ' | sort -u
}

# Build one stub overlay for a list of names; print ONLY the file path to stdout.
# Any informational text goes to stderr. Returns non-zero if nothing to stub.
make_stub_overlay() {
  local names=("$@")
  local stubbed=() n
  for n in "${names[@]}"; do
    if docker_has_container_like "$n"; then
      echo "ℹ️  Found running container for '${n}' — no stub needed." >&2
      continue
    fi
    stubbed+=("$n")
  done
  ((${#stubbed[@]})) || return 1

  local tmp
  tmp="$(mktemp -t osss-stub-XXXXXX.yml)"

  # NOTE: no "version:" key (Compose warns it is obsolete)
  {
    echo 'services:'
    for n in "${stubbed[@]}"; do
      cat <<YAML
  ${n}:
    image: busybox:latest
    command: ["sh","-c","sleep 1"]
    profiles: ["_stub"]    # never started implicitly
    deploy:
      replicas: 0
YAML
    done
  } > "$tmp"

  echo "$tmp"
}

make_stub_overlay_force() {
  local names=("$@")
  ((${#names[@]})) || return 1

  local tmp
  tmp="$(mktemp -t osss-stub-XXXXXX.yml)"

  {
    echo 'services:'
    local n
    for n in "${names[@]}"; do
      cat <<YAML
  ${n}:
    image: busybox:latest
    command: ["sh","-c","sleep 1"]
    restart: "no"
    labels:
      osss.stub: "1"
    deploy:
      replicas: 0
YAML
    done
  } > "$tmp"

  echo "$tmp"
}


# Start a profile ignoring depends_on, auto-stubbing undefined services
start_profile_no_deps() {
  local prof="$1"
  echo "▶️  Starting services for profile '${prof}' (ignoring depends_on; auto-stubbing undefined services)…"

  local base_args=(-f "$COMPOSE_FILE" --profile "$prof" up -d --no-deps)
  [[ "${BUILD_ALL:-0}" == "1" ]] && base_args=(-f "$COMPOSE_FILE" --profile "$prof" up -d --no-deps --build)

  # First attempt (might fail validation)
  run $COMPOSE "${base_args[@]}" || true

  # Capture diagnostics
  local err
  err="$($COMPOSE "${base_args[@]}" 2>&1 >/dev/null || true)"
  mapfile -t missing < <(printf '%s\n' "$err" | parse_undefined_services_from_stderr || true)

  if ((${#missing[@]}==0)); then
    return 0
  fi

  echo "⚠️  Compose references undefined services: ${missing[*]}"

  # For depends_on validation, the service must EXIST in config.
  # So we ALWAYS stub the missing names, even if a similarly named container is already running.
  stub_file="$(make_stub_overlay_force "${missing[@]}")" 2>/dev/null || stub_file=""
  if [[ -z "$stub_file" || ! -f "$stub_file" ]]; then
    echo "❌ Couldn’t create stub overlay for required services: ${missing[*]}"
    return 1
  fi

  echo "➕ Using stub overlay: $stub_file"

  # IMPORTANT: real compose file FIRST, stub LAST (so stub only fills the holes)
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" -f "$stub_file" --profile "$prof" up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" -f "$stub_file" --profile "$prof" up -d --no-deps
  fi

  # Optional: verify and cleanup
  $COMPOSE -f "$COMPOSE_FILE" -f "$stub_file" --profile "$prof" config >/dev/null 2>&1 || true
  rm -f "$stub_file" || true


  echo "➕ Using stub overlay: $stub_file"

  # IMPORTANT: put the real compose file FIRST, stub LAST
  if [[ "${BUILD_ALL:-0}" == "1" ]]; then
    run $COMPOSE -f "$COMPOSE_FILE" -f "$stub_file" --profile "$prof" up -d --no-deps --build
  else
    run $COMPOSE -f "$COMPOSE_FILE" -f "$stub_file" --profile "$prof" up -d --no-deps
  fi

  # Optional: sanity check if errors persist (and always clean up)
  err="$($COMPOSE -f "$COMPOSE_FILE" -f "$stub_file" --profile "$prof" config >/dev/null 2>&1; echo $?)"
  rm -f "$stub_file" || true

}


# Compose wrapper: run and capture stderr to a var name you pass
run_compose_capture_stderr() {
  # Usage: run_compose_capture_stderr VAR -- rest of compose args...
  local -n __ERR="$1"; shift
  __ERR=""
  # Capture only stderr to preserve normal stdout behavior
  # shellcheck disable=SC2034
  local out
  out="$("$COMPOSE" "$@" 2> >(cat >&2 | tee /dev/fd/3) 3>&1 )" || true
  # Re-run but capture stderr properly (portable approach)
  __ERR="$("$COMPOSE" "$@" 2>&1 >/dev/null || true)"
}


# Create a temporary override that defines a stub service (busybox sleeper)
_make_stub_override() {
  local missing="$1"
  local tmpfile
  tmpfile="$(mktemp -t osss-stub-XXXXXX.yml)"
  cat >"$tmpfile" <<EOF
services:
  ${missing}:
    image: busybox
    command: ["sh","-c","sleep infinity"]
    profiles: ["_auto_stub"]
EOF
  echo "$tmpfile"
}

# Run `up -d --no-deps` for a profile; if validation fails due to an undefined
# depends_on target, auto-stub it and retry once (loop supports multiple misses).
# Run `up -d --no-deps` for a profile; if validation fails due to an undefined
# depends_on target, auto-stub it and retry up to 5 missing names. Uses a temp log
# file so the call returns promptly, then parses/logs after.
_compose_up_profile_ignoring_dep_validation() {
  local prof="$1"; shift
  local extra_files=()
  local attempt=0

  while (( attempt < 5 )); do
    attempt=$((attempt+1))

    # Build command with any extra override files we’ve added
    local cmd=( $COMPOSE )
    for f in "${extra_files[@]}"; do cmd+=( -f "$f" ); done
    cmd+=( -f "$COMPOSE_FILE" --profile "$prof" )
    if [[ "${BUILD_ALL:-0}" == "1" ]]; then
      cmd+=( up -d --build --no-deps )
    else
      cmd+=( up -d --no-deps )
    fi

    echo "+ ${cmd[*]}"

    # Run -> temp log (avoid giant in-memory captures / buffering)
    local tmp_log rc out
    tmp_log="$(mktemp -t osss-up-XXXXXX.log)"
    set +e
    "${cmd[@]}" >"$tmp_log" 2>&1
    rc=$?
    set -e
    out="$(cat "$tmp_log")"
    rm -f "$tmp_log" || true

    if (( rc == 0 )); then
      [[ -n "$out" ]] && echo "$out"
      # cleanup temp files on success
      for f in "${extra_files[@]}"; do rm -f "$f" || true; done
      return 0
    fi

    # Look for "depends on undefined service "NAME""
    if [[ "$out" =~ depends\ on\ undefined\ service\ \"([^\"]+)\" ]]; then
      local missing="${BASH_REMATCH[1]}"
      echo "⚠️  Compose references undefined service '${missing}'. Creating stub override and retrying…"
      local stub="$(_make_stub_override "$missing")"
      extra_files+=( "$stub" )
      continue
    fi

    # Any other error → print and fail
    echo "$out"
    for f in "${extra_files[@]}"; do rm -f "$f" || true; done
    return "$rc"
  done

  echo "❌ Too many unresolved missing services while trying to start profile '${prof}'."
  for f in "${extra_files[@]}"; do rm -f "$f" || true; done
  return 1
}



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
down_profile() {
  if [[ "${PROFILE:-}" == "trino" ]]; then
    echo "▶️  Down (containers + anonymous volumes) for profile 'trino' ONLY…"
    down_current_profile_services_only
  else
    echo "▶️  Down (remove orphans & volumes) for profile '${PROFILE}'…"
    run c down --remove-orphans --volumes || true
  fi
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
    echo " 1) Start profile 'keycloak'"
    echo " 2) Start profile 'app'"
    echo " 3) Start profile 'web-app'"
    echo " 4) Start profile 'elastics'"
    echo " 5) Start profile 'vault'"
    echo " 6) Start profile 'consul'"
    echo " 7) Start ALL services"
    echo " 8) Start profile 'datalake_data'"
    echo " 9) Start profile 'trino'"
    echo "10) Start profile 'airflow'"
    echo "11) Start profile 'superset'"
    echo "12) Start profile 'openmetadata'"
    echo "13) Down a profile (remove-orphans, volumes)"
    echo "14) Down ALL (remove-orphans, volumes)"
    echo "15) Remove leftover containers for project"
    echo "16) Prune dangling networks"
    echo "17) Logs submenu"
    echo "18) Rebuild ALL services (no cache)"
    echo "  q) Quit"
    echo "-----------------------------------------------"
    read -rp "Select an option: " ans || exit 0
    case "${ans}" in
      1)  start_keycloak_services ;;
      2)  start_profile_app ;;
      3)  start_profile_web_app ;;
      4)  start_profile_elastics ;;
      5)  start_profile_vault ;;
      6)  start_profile_consul ;;
      7)  start_all_services ;;
      8)  start_profile_datalake_data ;;
      9)  start_profile_trino ;;
      10) start_profile_airflow ;;
      11) start_profile_superset ;;
      12) start_profile_openmetadata ;;
      13) down_profile_interactive ;;
      14) down_all ;;
      15) kill_leftovers ;;
      16) prune_networks ;;
      17) logs_menu ;;
      18) rebuild_all_services ;;
      q|Q) echo "Bye!"; exit 0 ;;
      *)   echo "Unknown choice: ${ans}" ;;
    esac

  done
}


menu
