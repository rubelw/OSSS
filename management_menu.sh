#!/usr/bin/env bash
# management_menu.sh (Podman-only)
# - Uses Podman + Podman Compose exclusively
# - Adds 127.0.0.1 keycloak.local to /etc/hosts if missing
# - Has helpers to start profiles and view logs
# - Runs build_realm.py after Keycloak is up

set -Eeuo pipefail

DEBUG=1

ensure_podman_ready() {
  # Debug/trace toggle
  local _had_xtrace=
  if [ "${DEBUG:-0}" = "1" ]; then
    set -x
    _had_xtrace=1
  fi

  # Tiny logger helpers
  _log()  { printf "\033[1;34m[ensure_podman_ready]\033[0m %s\n" "$*"; }
  _ok()   { printf "\033[1;32m[OK]\033[0m %s\n" "$*"; }
  _warn() { printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
  _err()  { printf "\033[1;31m[ERR]\033[0m %s\n" "$*"; }

  _log "Podman bootstrap starting…"
  _log "Shell: $SHELL  |  User: $(id -un)  |  Host: $(hostname)"

  # ---------- Podman binary & version ----------
  if ! command -v podman >/dev/null 2>&1; then
    _err "Podman is not installed (podman not found in PATH)"
    return 1
  fi
  _log "podman path: $(command -v podman)"
  _log "podman version: $(podman --version 2>&1 || true)"
  _log "podman env: XDG_RUNTIME_DIR='${XDG_RUNTIME_DIR:-}'  PATH='$PATH'"

  # ---------- Current connection (if any) ----------
  local _uri=""
  _uri="$(podman system connection show -f '{{.URI}}' 2>/dev/null || true)"
  [ -n "$_uri" ] && _log "Current connection URI: ${_uri}" || _warn "No active podman system connection URI detected"

  _log "Connections:"
  podman system connection list || _warn "Failed to list connections"

  # ---------- Quick health check ----------
  if podman info --debug >/dev/null 2>&1; then
    _ok "Podman is reachable (host-side)"
  else
    _warn "podman info failed; attempting machine bootstrap if available…"

    # ---------- macOS/Windows (podman machine flow) ----------
    if podman machine --help >/dev/null 2>&1; then
      local NAME="${PODMAN_MACHINE_NAME:-default}"
      _log "Using Podman VM name: '${NAME}'"

      # If VM missing, clean stale connections and init
      if ! podman machine inspect "$NAME" >/dev/null 2>&1; then
        _log "No VM named '${NAME}' found; checking for stale system connections…"
        if podman system connection list --format '{{.Name}}' | grep -qx "$NAME"; then
          _warn "Removing stale system connection '$NAME'…"
          podman system connection rm "$NAME" >/dev/null 2>&1 || _warn "Failed to remove stale '$NAME' (continuing)"
        fi
        if podman system connection list --format '{{.Name}}' | grep -qx "${NAME}-root"; then
          _warn "Removing stale system connection '${NAME}-root'…"
          podman system connection rm "${NAME}-root" >/dev/null 2>&1 || _warn "Failed to remove stale '${NAME}-root' (continuing)"
        fi

        _log "Initializing Podman VM '${NAME}'…"
        _log "Resources: CPUs=${PODMAN_MACHINE_CPUS:-12}  MEM(MB)=${PODMAN_MACHINE_MEM_MB:-40960}  DISK(GB)=${PODMAN_MACHINE_DISK_GB:-100}"
        podman machine init "$NAME" \
          --cpus "${PODMAN_MACHINE_CPUS:-12}" \
          --memory "${PODMAN_MACHINE_MEM_MB:-40960}" \
          --disk-size "${PODMAN_MACHINE_DISK_GB:-100}" || {
            _err "podman machine init failed"; return 1; }
      fi

      # Start if not running
      local _state
      _state="$(podman machine inspect "$NAME" --format '{{.State}}' 2>/dev/null || echo 'unknown')"
      _log "VM '${NAME}' state: ${_state}"
      if ! printf "%s" "$_state" | grep -qx Running; then
        _log "Starting Podman VM '${NAME}'…"
        podman machine start "$NAME" || { _err "Failed to start VM '${NAME}'"; return 1; }
      fi

      # Prefer matching default connection (rootless first)
      if podman system connection list --format '{{.Name}}' | grep -qx "$NAME"; then
        podman system connection default "$NAME" >/dev/null 2>&1 || _warn "Could not set default connection '$NAME'"
      elif podman system connection list --format '{{.Name}}' | grep -qx "${NAME}-root"; then
        podman system connection default "${NAME}-root" >/dev/null 2>&1 || _warn "Could not set default connection '${NAME}-root'"
      fi

      _ok "Podman VM '${NAME}' initialized/started"
    else
      _err "podman info failed and 'podman machine' is unavailable on this platform"
      return 1
    fi
  fi

  # ---------- Final host-side health check ----------
  if ! podman info --debug >/dev/null 2>&1; then
    _err "Podman not reachable after bootstrap"
    _log "Helpful next steps:"
    _log "  podman system connection list"
    _log "  podman system connection default <VALID_NAME>"
    return 1
  fi
  _ok "Podman is reachable (post-bootstrap)"

  # ---------- Ensure podman-compose inside VM (macOS/Windows) ----------
  if podman machine --help >/dev/null 2>&1; then
    local NAME="${PODMAN_MACHINE_NAME:-default}"
    local _vm_state
    _vm_state="$(podman machine inspect "$NAME" --format '{{.State}}' 2>/dev/null || echo 'unknown')"
    _log "VM '${NAME}' state check before compose install: ${_vm_state}"

    if printf "%s" "$_vm_state" | grep -qx Running; then
      _log "Checking for podman-compose inside VM '${NAME}'…"
      if ! podman machine ssh "$NAME" -- bash -lc 'command -v podman-compose >/dev/null 2>&1'; then
        _warn "podman-compose not present; installing via rpm-ostree…"
        podman machine ssh "$NAME" -- sudo rpm-ostree install -y podman-compose || {
          _err "Failed to install podman-compose via rpm-ostree"; return 1; }

        _log "Restarting VM '${NAME}' to apply rpm-ostree changes…"
        podman machine stop "$NAME" || { _err "Failed to stop VM '${NAME}'"; return 1; }
        podman machine start "$NAME" || { _err "Failed to start VM '${NAME}'"; return 1; }

        _log "Verifying podman-compose after reboot…"
        podman machine ssh "$NAME" -- bash -lc 'podman-compose --version' || {
          _err "podman-compose not available after reboot"; return 1; }
        _ok "podman-compose installed and active in VM '${NAME}'"
      else
        _ok "podman-compose already present in VM '${NAME}' ($(podman machine ssh "$NAME" -- bash -lc 'podman-compose --version 2>/dev/null' || echo 'unknown'))"
      fi
    else
      _warn "VM '${NAME}' is not running; skipping compose install. (state=${_vm_state})"
    fi
  fi

  # ---------- Pin CONTAINER_HOST so podman-compose uses the same connection ----------
  if command -v podman >/dev/null 2>&1; then
    export CONTAINER_HOST="$(podman system connection show -f '{{.URI}}' 2>/dev/null || echo '')"
    if [ -n "$CONTAINER_HOST" ]; then
      _ok "Pinned CONTAINER_HOST=$CONTAINER_HOST"
    else
      _warn "Could not determine CONTAINER_HOST from current connection"
    fi
  fi

  # ---------- Diagnostics: machine + networks ----------
  _log "Diagnostics snapshot:"
  _log "podman machine list:"
  podman machine list || true

  _log "Host-side networks (current connection):"
  podman network ls || true

  if podman machine --help >/dev/null 2>&1; then
    local NAME="${PODMAN_MACHINE_NAME:-default}"
    _log "VM '${NAME}' networks:"
    podman machine ssh "$NAME" -- podman network ls || true
  fi

  _ok "Podman bootstrap completed."

  # Disable xtrace if we enabled it
  if [ "$_had_xtrace" = "1" ]; then set +x; fi
}

ensure_podman_ready

HOST_PROJ="$(pwd -P)"
COMPOSE_PROFILES_VERBOSE=1
export PODMAN_MACHINE=default
export PODMAN_OVERLAY_DIR="$(
  podman machine ssh "${PODMAN_MACHINE:-$(podman machine active 2>/dev/null || echo default)}" -- \
    podman info | awk -F': *' 'tolower($1) ~ /graphroot/ { gsub(/[[:space:]]+/,"",$2); print $2 "/overlay-containers"; exit }'
)"
echo "$PODMAN_OVERLAY_DIR"   # sanity check; should exist inside VM



# --- Bash 3.x compatibility shims (macOS default shell lacks mapfile/readarray) ---
if ! command -v mapfile >/dev/null 2>&1; then
  mapfile() {


    # supports: mapfile -t ARRAY  (reads from stdin)
    local strip=0 OPTIND=1 OPTARG
    while getopts "t" opt; do
      case "$opt" in
        t) strip=1 ;;
      esac
    done
    shift $((OPTIND-1))
    local __arr_name="$1"
    local __i=0 __line
    # ensure target exists as an array
    eval "$__arr_name=()"
    while IFS= read -r __line; do
      # -t behavior: strip trailing newline
      (( strip )) && __line="${__line%$'\n'}"
      eval "$__arr_name[__i]=\$__line"
      __i=$((__i+1))
    done
  }
fi


# Bash 3.x on macOS doesn't have readarray; alias it to mapfile.
if ! command -v readarray >/dev/null 2>&1; then
  readarray() { mapfile "$@"; }
fi

# Return the container engine binary ("podman" or "docker") matching the compose provider
get_compose_engine() {
  local CMD
  CMD="$(__compose_cmd)" || return 127
  case "$CMD" in
    "podman compose"|podman-compose) echo "podman";;
    "docker compose"|docker-compose) echo "docker";;
    *)
      # Best-effort default
      echo "podman"
      ;;
  esac
}

# Run an engine command with nice diagnostics
# --- engine_exec: trace to STDERR, emit only command STDOUT to caller ---

# --- External networks create-only helper (called by start_* funcs) ---
ensure_external_networks_exist() {
  # Ensure external networks referenced by compose exist.
  # For now we only create 'osss-net' if missing (create-only; no deletes).
  if ! podman network exists osss-net 2>/dev/null; then
    echo "➕ Creating external network: osss-net"
    podman network create osss-net >/dev/null || echo "⚠️  Could not create osss-net (continuing)"
  fi
}



# --- Podman preflight (idempotent) ---
podman_ready_once() {
  # Only run once per process
  [[ "${__OSSS_PODMAN_READY:-}" == "1" ]] && return 0
  command -v podman >/dev/null 2>&1 || { __OSSS_PODMAN_READY=1; export __OSSS_PODMAN_READY; return 0; }

  # Fast path: if the VM is already running, don't touch it
  if pm_ssh -h >/dev/null 2>&1; then
    local NAME="${PODMAN_MACHINE_NAME:-default}"
    if pm_ssh ls --format '{{.Name}} {{.Running}}' \
       | awk -v n="$NAME" '$1==n && $2=="true"{ok=1} END{exit ok?0:1}'; then
      __OSSS_PODMAN_READY=1; export __OSSS_PODMAN_READY; return 0
    fi
  fi

  # If CLI is already connected, we're good
  if podman info --debug >/dev/null 2>&1; then
    __OSSS_PODMAN_READY=1; export __OSSS_PODMAN_READY; return 0
  fi

  # Init/start only when needed
  local NAME="${PODMAN_MACHINE_NAME:-default}"
  if pm_ssh -h >/dev/null 2>&1; then
    if ! pm_ssh inspect "$NAME" >/dev/null 2>&1; then
      pm_ssh init \
        --cpus  "${PODMAN_MACHINE_CPUS:-6}" \
        --memory "${PODMAN_MACHINE_MEM_MB:-8192}" \
        --disk-size "${PODMAN_MACHINE_DISK_GB:-50}" \
        "$NAME"
    fi
    pm_ssh start "$NAME"

    # Ensure the default connection matches the running machine
    if podman system connection list --format '{{.Name}}' | grep -qx "$NAME"; then
      podman system connection default "$NAME" >/dev/null 2>&1 || true
    elif podman system connection list --format '{{.Name}}' | grep -qx "${NAME}-root"; then
      podman system connection default "${NAME}-root" >/dev/null 2>&1 || true
    fi
  fi

  # Final health check
  podman info --debug >/dev/null 2>&1 || { echo "❌ Podman not reachable"; exit 1; }
  __OSSS_PODMAN_READY=1; export __OSSS_PODMAN_READY
}


podman_ready_once


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

build_trino_truststore() {
  echo "🛠️  Building Trino PKCS12 truststore (CA-based)…"

  # --- Config/paths ---
  local OUT_DIR="./config_files/trino/opt"
  local TRUSTSTORE_P12="${OUT_DIR}/osss-truststore.p12"
  local STOREPASS="changeit"

  # Your Keycloak CA (from create_keycloak_cert)
  local CA_CRT="./config_files/keycloak/secrets/ca/ca.crt"
  local CA_ALIAS="osss-dev-ca"

  # --- Preflight ---
  if ! command -v keytool >/dev/null 2>&1; then
    echo "❌ keytool not found."
    echo "   macOS: brew install --cask temurin || brew install openjdk"
    echo "   Linux: apt-get install -y openjdk-17-jre-headless (or similar)"
    return 1
  fi
  echo "✅ keytool: $(command -v keytool)"

  mkdir -p "${OUT_DIR}"

  if [ ! -f "${CA_CRT}" ]; then
    echo "❌ Missing CA certificate at ${CA_CRT}"
    echo "   Run your create_keycloak_cert step first."
    return 1
  fi

  # --- Build CA-only PKCS12 truststore (idempotent) ---
  echo "→ Creating PKCS12 truststore at ${TRUSTSTORE_P12} with alias '${CA_ALIAS}'"
  rm -f "${TRUSTSTORE_P12}"

  if ! keytool -importcert \
        -alias "${CA_ALIAS}" \
        -file "${CA_CRT}" \
        -keystore "${TRUSTSTORE_P12}" \
        -storetype PKCS12 \
        -storepass "${STOREPASS}" -noprompt; then
    echo "❌ Failed to create ${TRUSTSTORE_P12}"
    return 1
  fi

  # --- Sanity check ---
  echo "→ Sanity check: listing truststore entries"
  if ! keytool -list -v \
        -keystore "${TRUSTSTORE_P12}" \
        -storetype PKCS12 -storepass "${STOREPASS}"; then
    echo "❌ keytool -list failed on ${TRUSTSTORE_P12}"
    return 1
  fi

  echo "🎉 Truststore ready: ${TRUSTSTORE_P12}"
  echo "   Mount in docker-compose as read-only:"
  echo "     - ./config_files/trino/opt/osss-truststore.p12:/opt/trust/osss-truststore.p12:ro"
  echo "   And set JAVA_TOOL_OPTIONS:"
  echo "     -Djavax.net.ssl.trustStore=/opt/trust/osss-truststore.p12"
  echo "     -Djavax.net.ssl.trustStorePassword=changeit"
  echo "     -Djavax.net.ssl.trustStoreType=PKCS12"
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



# Extra services to remove when downing a given profile (Bash 3–friendly).
# Extend this case list as needed.

# Parse docker-compose.yml and list services that include a given profile, without needing compose on the host.
# Usage: services_for_profile_from_yaml "elastic"


# -------- Podman compose selection --------
compose_cmd() {
  # Prefer native `podman compose` (try it directly)
  if podman compose version >/dev/null 2>&1; then
    echo "podman compose"
    return 0
  fi

  # Fallback to podman-compose if installed on host
  if command -v podman-compose >/dev/null 2>&1; then
    echo "podman-compose"
    return 0
  fi

  # Last-resort: run compose inside the Podman VM (macOS)
  if podman machine --help >/dev/null 2>&1; then
    echo "podman machine ssh -- podman compose"
    return 0
  fi

  echo "❌ Neither 'podman compose' nor 'podman-compose' is available." >&2
  return 127
}

__compose_cmd() { compose_cmd; }

ensure_compose_file() {
  [[ -f "$COMPOSE_FILE" ]] || { echo "❌ Compose file not found: $COMPOSE_FILE" >&2; exit 1; }
}

podman_ready_once
COMPOSE="$(compose_cmd)"
ensure_compose_file

# Convenience wrappers
run() { echo "+ $*"; "$@"; }
c() { $COMPOSE -f "$COMPOSE_FILE" --profile "$PROFILE" "$@"; }

# -------- Service discovery --------

# Returns unique profile names for the active compose file, even under podman compose
discover_profiles() {
  # Logs → stderr, data (profile names one per line) → stdout
  echo "[discover_profiles] Invoked" >&2

  local CMD; CMD="$(__compose_cmd)" || { echo "[discover_profiles] ❌ no compose cmd" >&2; return 0; }

  # COMPOSE_FILE may be colon-separated
  local CF="${COMPOSE_FILE:-docker-compose.yml}"
  IFS=':' read -r -a FILES <<<"$CF"
  ((${#FILES[@]})) || FILES=("docker-compose.yml")

  echo "[discover_profiles] Using command: $CMD" >&2
  echo "[discover_profiles] Compose files:" >&2
  local f
  for f in "${FILES[@]}"; do
    echo "  • $f $([ -f "$f" ] && echo '(exists)' || echo '(MISSING)')" >&2
  done

  # -------- 1) Native path: `compose config --profiles` (union across files) ----
  echo "[discover_profiles] Probing native '--profiles'…" >&2
  local argv=(); for f in "${FILES[@]}"; do argv+=(-f "$f"); done
  local native_out="" native_rc=1
  if $CMD "${argv[@]}" config --profiles >/dev/null 2>&1; then
    native_out="$($CMD "${argv[@]}" config --profiles 2>/dev/null | awk 'NF' | sort -u)"
    native_rc=$?
    echo "[discover_profiles] native rc=${native_rc} count=$(printf '%s\n' "$native_out" | awk 'NF' | wc -l | tr -d ' ')" >&2
  else
    echo "[discover_profiles] '--profiles' unsupported by this engine" >&2
  fi

  # -------- 2) YAML fallback (Python + PyYAML first; then AWK) ------------------
  echo "[discover_profiles] Fallback: parsing source YAML…" >&2
  local parsed_all="" py_rc=99

  if command -v python3 >/dev/null 2>&1; then
    # Try Python + PyYAML (most reliable for all YAML constructs)
    parsed_all="$(
      python3 - "$@" <<'PY' "${FILES[@]}"
import sys
files = sys.argv[1:]
try:
    import yaml  # PyYAML
except Exception:
    sys.exit(90)  # signal "PyYAML missing"

profiles = set()
for path in files:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
    except Exception:
        continue
    services = doc.get("services") or {}
    if isinstance(services, dict):
        for name, svc in services.items():
            if not isinstance(svc, dict):
                continue
            p = svc.get("profiles")
            if isinstance(p, str):
                profiles.add(p.strip())
            elif isinstance(p, (list, tuple)):
                for v in p:
                    if isinstance(v, str) and v.strip():
                        profiles.add(v.strip())

for p in sorted(profiles):
    print(p)
PY
    )"
    py_rc=$?
    if (( py_rc == 0 )); then
      echo "[discover_profiles] PyYAML parse count=$(printf '%s\n' "$parsed_all" | awk 'NF' | wc -l | tr -d ' ')" >&2
    elif (( py_rc == 90 )); then
      echo "[discover_profiles] python3 present but PyYAML missing; using AWK fallback" >&2
      parsed_all=""
    else
      echo "[discover_profiles] python3 parse failed rc=$py_rc; using AWK fallback" >&2
      parsed_all=""
    fi
  else
    echo "[discover_profiles] python3 not found; using AWK fallback" >&2
  fi

  # AWK fallback if Python path didn’t produce results
  if [[ -z "$parsed_all" ]]; then
    local parsed_this=""
    for f in "${FILES[@]}"; do
      if [[ ! -f "$f" ]]; then
        echo "[discover_profiles]   skip (missing): $f" >&2
        continue
      fi
      parsed_this="$(
        awk '
          function indent(s){match(s,/^[ \t]*/); return RLENGTH}
          BEGIN{ in_prof=0; prof_i=-1 }
          {
            li = indent($0)
            # Any occurrence of "profiles:" (we will validate by indentation for list items)
            if ($0 ~ /^[ \t]*profiles:[ \t]*/) {
              in_prof = 1
              prof_i  = li
              # Grab anything inline: e.g., "profiles: elastic" OR "profiles: [a, b]"
              rest=$0
              sub(/^[ \t]*profiles:[ \t]*/, "", rest)
              # If flow list: [a, b]
              if (rest ~ /\[[^]]*\]/) {
                gsub(/\[/, "", rest); gsub(/\]/, "", rest)
                n=split(rest, arr, /[ \t,]+/)
                for (i=1; i<=n; i++) if (arr[i]!="") print arr[i]
                in_prof=0
                next
              }
              # If scalar: "profiles: elastic"
              if (rest ~ /[^ \t]/) {
                gsub(/^[ \t]+|[ \t]+$/, "", rest)
                if (rest!="") print rest
                in_prof=0
                next
              }
              # Otherwise expect block list items on following lines
              next
            }
            if (in_prof) {
              # list item under profiles: (must be further indented)
              if ($0 ~ /^[ \t]*-[ \t]*[A-Za-z0-9._-]+[ \t]*$/ && li > prof_i) {
                p=$0; sub(/^[ \t]*-[ \t]*/, "", p); sub(/[ \t]*$/, "", p); print p
                next
              }
              # End of profiles block: dedent to <= prof_i or new key at same/lower indent
              if (li <= prof_i || $0 ~ /^[ \t]*[A-Za-z0-9._-]+:[ \t]*$/) {
                in_prof=0
              }
            }
          }
        ' "$f"
      )"
      if [[ -n "$parsed_this" ]]; then
        while IFS= read -r line; do
          [[ -z "$line" ]] && continue
          echo "[discover_profiles] parsed ($f) → $line" >&2
        done <<<"$parsed_this"
        parsed_all+=$'\n'"$parsed_this"
      else
        echo "[discover_profiles] parsed ($f) → <none>" >&2
      fi
    done
  fi

  # -------- 3) Union results (native + parsed) ----------------------------------
  local combined
  combined="$( (printf '%s\n' "$native_out"; printf '%s\n' "$parsed_all") | awk 'NF' | sort -u )"
  echo "[discover_profiles] combined count=$(printf '%s\n' "$combined" | awk 'NF' | wc -l | tr -d ' ')" >&2

  if [[ -n "$combined" ]]; then
    printf '%s\n' "$combined"
  else
    echo "[discover_profiles] ❌ No profiles discovered." >&2
    echo "  Hints:" >&2
    echo "   • Ensure each service defines a 'profiles:' list (block, flow [a,b], or scalar)." >&2
    echo "   • Verify COMPOSE_FILE points to the right file(s); multiple files use ':' separators." >&2
    echo "   • Try: grep -nE \"^[[:space:]]*profiles:[[:space:]]*(\\[.*\\]|[[:alnum:]_.-]+)?$\" ${FILES[*]}" >&2
    echo "   • Try: $CMD ${argv[*]} config --services" >&2
  fi
}



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
# List unique compose profiles (multi-file aware, verbose when COMPOSE_PROFILES_VERBOSE/VERBOSE/DEBUG set)

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
  local file="${COMPOSE_FILE:-docker-compose.yml}"
  local v=0
  [[ -n "$COMPOSE_PROFILES_VERBOSE" || -n "$VERBOSE" || -n "$DEBUG" ]] && v=1

  awk -v verbose="$v" -v FILE="$file" '
    function dbg(msg){ if (verbose) print msg > "/dev/stderr" }

    BEGIN{
      in_services=0; svc=""; in_profiles=0
      dbg("» scanning compose file: " FILE)
    }

    /^[[:space:]]*services[[:space:]]*:/ {
      in_services=1
      dbg(sprintf("[L%05d] enter services", NR))
      next
    }

    in_services {
      # top-level key ends services
      if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) {
        dbg(sprintf("[L%05d] leave services", NR))
        in_services=0; next
      }

      # service header (two spaces then "name:")
      if ($0 ~ /^[[:space:]][[:space:]][A-Za-z0-9._-]+:[[:space:]]*$/) {
        svc=$0; sub(/^[[:space:]]+/, "", svc); sub(/:.*/, "", svc); in_profiles=0
        dbg(sprintf("[L%05d] service: %s", NR, svc))
        next
      }

      # inline profiles: "    profiles: [a,b,c]"
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*\[/) {
        s=$0; sub(/^[^[]*\[/,"",s); sub(/\].*$/,"",s)
        raw=s
        gsub(/[[:space:]]/,"",s)
        dbg(sprintf("[L%05d] %s: inline profiles raw: [%s]", NR, svc, raw))
        n=split(s, arr, ",")
        for(i=1;i<=n;i++) if (arr[i]!="") { seen[arr[i]]=1; dbg("           -> +" arr[i]) }
        next
      }

      # multiline profiles: start
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*$/) {
        in_profiles=1
        dbg(sprintf("[L%05d] %s: profiles list start", NR, svc))
        next
      }

      # multiline items: "      - prof"
      if (in_profiles && $0 ~ /^[[:space:]]{6}-[[:space:]]*[A-Za-z0-9._-]+/) {
        p=$0; sub(/^[^ -]*-/,"",p); gsub(/^[[:space:]]+|[[:space:]]+$/,"",p)
        if (p!="") { seen[p]=1; dbg("           -> +" p) }
        next
      }

      # any new key at indent 4 ends profiles block
      if (in_profiles && $0 ~ /^[[:space:]]{4}[A-Za-z0-9._-]+:/) {
        in_profiles=0
        dbg(sprintf("[L%05d] %s: profiles list end", NR, svc))
      }
    }

    END{
      if (verbose) {
        dbg("== collected profiles ==")
        for (k in seen) dbg("  * " k)
        dbg("== end ==")
      }
      for (k in seen) print k
    }
  ' "$file" | sort -u
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

# Return services for a profile, clean (one per line, no logs).
compose_services_for_profile() {
  local CMD="$1" FILE="$2" PROFILE="$3"
  "$CMD" -f "$FILE" --profile "$PROFILE" config --services 2>/dev/null | awk 'NF'
}


compose_services_all() {
  { compose_services_base; while read -r p; do [[ -n "$p" ]] && compose_services_for_profile "$p"; done < <(compose_profiles); } \
  | awk 'NF && !seen[$0]++' | sort -u
}

# -------- Host info --------



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
  # Print a subtle prompt and wait for the user to press Enter
  printf "\n↩ Press Enter to return to the menu..."
  # shellcheck disable=SC2162
  read _
  printf "\n"
}


# Force-recreate all services in a given profile (works with both `podman compose` and `podman-compose`)
up_force_profile() {
  local prof="$1"
  echo "[up_force_profile] Invoked with profile: '$prof'"

  # Prefer compose CLI; fall back to awk parser
  echo "[up_force_profile] Resolving services for profile '$prof'..."
  mapfile -t svcs < <($COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF')
  echo "[up_force_profile] Found ${#svcs[@]} service(s) from compose CLI: ${svcs[*]:-<none>}"

  if ((${#svcs[@]}==0)); then
    echo "[up_force_profile] Falling back to compose_services_for_profile..."
    mapfile -t svcs < <(compose_services_for_profile "$prof" 2>/dev/null || true)
    echo "[up_force_profile] Found ${#svcs[@]} service(s) via fallback: ${svcs[*]:-<none>}"
  fi

  if ((${#svcs[@]}==0)); then
    echo "⚠️  No services declare profile '${prof}' in ${COMPOSE_FILE:-docker-compose.yml}."
    echo "[up_force_profile] Exiting early, nothing to do"
    prompt_return
    return 0
  fi

  echo "🛠️  Forcing recreate of ${#svcs[@]} service(s) in profile '${prof}': ${svcs[*]}"

  # make this block failure-tolerant, then restore -e
  echo "[up_force_profile] Disabling 'set -e' to tolerate failures..."
  set +e

  # Stop via compose first (ok if already stopped)
  echo "[up_force_profile] Stopping services via compose..."
  $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" stop "${svcs[@]}"

  # Hard-stop & remove any existing containers/pods that belong to these services
  for svc in "${svcs[@]}"; do
    echo "[up_force_profile] Checking for existing containers of service '$svc'..."
    ids=$(podman ps -a \
      --filter "label=io.podman.compose.project=${COMPOSE_PROJECT_NAME}" \
      --filter "label=io.podman.compose.service=${svc}" -q 2>/dev/null)

    if [[ -n "$ids" ]]; then
      echo "[up_force_profile] Found containers for '$svc': $ids"
      pods=$(podman inspect -f '{{.PodName}}' $ids 2>/dev/null | awk 'NF && $0!="<no value>" && !seen[$0]++')

      if [[ -n "$pods" ]]; then
        echo "[up_force_profile] Stopping pods: $pods"
        podman pod stop $pods >/dev/null 2>&1
      fi

      echo "[up_force_profile] Removing containers + anon volumes for '$svc'..."
      podman rm -f -v $ids >/dev/null 2>&1

      if [[ -n "$pods" ]]; then
        echo "[up_force_profile] Removing pods: $pods"
        podman pod rm -f $pods >/dev/null 2>&1
      fi
    else
      echo "[up_force_profile] No containers found for service '$svc'"
    fi
  done

  # Bring them back up (ignore “network in use”/pod removal errors, compose will reuse)
  echo "[up_force_profile] Starting services with 'up -d --no-deps --force-recreate'..."
  $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d --no-deps --force-recreate

  echo "[up_force_profile] Restoring 'set -e'"
  set -e

  echo "[up_force_profile] Completed, returning to menu..."
  prompt_return
  return 0
}



start_profile_with_build_prompt() {
  local prof="$1"

  echo "[start_profile_with_build_prompt] Maybe building profile: '$prof'"
  maybe_build_profile "$prof"
  echo "[start_profile_with_build_prompt] Build check complete for profile '$prof'"

  if compose_supports_profile; then
    echo "[start_profile_with_build_prompt] Backend supports profiles"
    echo "[start_profile_with_build_prompt] Running compose up with: $COMPOSE -f \"$COMPOSE_FILE\" --profile \"$prof\" up -d --no-deps"
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d --no-deps
    echo "[start_profile_with_build_prompt] Compose up complete (profile mode)"
  else
    echo "[start_profile_with_build_prompt] Backend does NOT support profiles → falling back to manual service resolution"
    mapfile -t svcs < <(compose_services_for_profile "$prof" 2>/dev/null || true)
    echo "[start_profile_with_build_prompt] Resolved ${#svcs[@]} service(s) for profile '$prof': ${svcs[*]:-<none>}"

    if ((${#svcs[@]}==0)); then
      echo "⚠️  No services declare profile '${prof}' in ${COMPOSE_FILE:-docker-compose.yml}."
      echo "[start_profile_with_build_prompt] Exiting early, nothing to start"
      prompt_return
      return 1
    fi

    echo "⚠️  Backend lacks profile support; starting services only: ${svcs[*]}"
    echo "[start_profile_with_build_prompt] Running compose_up_services with: ${svcs[*]}"
    compose_up_services "${svcs[@]}"   # calls: up -d --no-deps <services...>
    echo "[start_profile_with_build_prompt] Compose up complete (manual fallback)"
  fi

  echo "[start_profile_with_build_prompt] Returning to menu..."
  prompt_return
  echo "[start_profile_with_build_prompt] Finished execution"
}


start_profile_services() {
  echo "[start_profile_services] Invoked with profile: '$prof'"

  echo "[start_profile_services] Determining compose command..."
  local CMD; CMD="$(__compose_cmd)" || {
    echo "[start_profile_services] Failed to determine compose command → exiting with error"
    return $?
  }
  echo "[start_profile_services] Using compose command: $CMD"

  echo "[start_profile_services] Resolving services via compose CLI for profile '$prof'..."
  mapfile -t svcs < <($CMD -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF')
  echo "[start_profile_services] Found ${#svcs[@]} service(s) from compose CLI: ${svcs[*]:-<none>}"

  if [ "${#svcs[@]}" -eq 0 ]; then
    echo "[start_profile_services] Falling back to compose_services_for_profile..."
    mapfile -t svcs < <(compose_services_for_profile "$prof" 2>/dev/null || true)
    echo "[start_profile_services] Found ${#svcs[@]} service(s) via fallback: ${svcs[*]:-<none>}"
  fi

  if ((${#svcs[@]}==0)); then
    echo "(no services discovered in profile '${prof}')"
    echo "[start_profile_services] Nothing to start, returning to menu"
    prompt_return
    return 1
  fi

  echo "▶️  Starting ${#svcs[@]} service(s) in profile '${prof}': ${svcs[*]}"
  echo "[start_profile_services] Running: $COMPOSE -f \"$COMPOSE_FILE\" --profile \"$prof\" up -d"
  run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d
  echo "[start_profile_services] Compose up complete for profile '$prof'"

  echo "[start_profile_services] Returning to menu..."
  prompt_return
  echo "[start_profile_services] Finished execution"
}

# Override: start_keycloak_services to ensure external networks first
start_keycloak_services() {
  echo "[start_keycloak_services] Invoked"

  echo "[start_keycloak_services] Determining compose command..."
  local CMD; CMD="$(__compose_cmd)" || {
    echo "[start_keycloak_services] Failed to determine compose command → exiting"
    return $?
  }
  echo "[start_keycloak_services] Using compose command: $CMD"

  echo "[start_keycloak_services] Determining project name..."
  local PROJECT; PROJECT="$(__compose_project_name)"
  echo "[start_keycloak_services] Project: $PROJECT"
  echo "[start_keycloak_services] Compose file: ${COMPOSE_FILE:-docker-compose.yml}"

  echo "[start_keycloak_services] Ensuring external networks exist (non-destructive)..."
  echo "[start_keycloak_services] External networks ensured"

  local svcs=()
  if compose_supports_profile; then
    echo "[start_keycloak_services] Backend supports profiles, checking profile 'keycloak'..."
    mapfile -t svcs < <($CMD -f "$COMPOSE_FILE" --profile "keycloak" config --services 2>/dev/null | awk 'NF')
    echo "[start_keycloak_services] Found ${#svcs[@]} service(s) in 'keycloak' profile via compose CLI: ${svcs[*]:-<none>}"

    if [ "${#svcs[@]}" -eq 0 ]; then
      echo "[start_keycloak_services] Falling back to compose_services_for_profile 'keycloak'..."
      mapfile -t svcs < <(compose_services_for_profile "keycloak" 2>/dev/null || true)
      echo "[start_keycloak_services] Found ${#svcs[@]} service(s) via fallback: ${svcs[*]:-<none>}"
    fi
  else
    echo "[start_keycloak_services] Backend does NOT support profiles → skipping profile resolution"
  fi

  if ((${#svcs[@]})); then
    echo "[start_keycloak_services] Profile 'keycloak' detected with ${#svcs[@]} service(s): ${svcs[*]}"
    echo "[start_keycloak_services] Maybe building profile 'keycloak'..."
    maybe_build_profile keycloak
    echo "[start_keycloak_services] Build check complete"

    echo "[start_keycloak_services] Running: $CMD --profile keycloak up -d --no-deps ${svcs[*]}"
    $CMD --profile keycloak up -d --no-deps "${svcs[@]}"
    echo "[start_keycloak_services] Compose up complete for profile 'keycloak'"
    echo "[start_keycloak_services] Returning to menu..."
    prompt_return
    echo "[start_keycloak_services] Finished execution"
    return 0
  fi

  echo "[start_keycloak_services] No 'keycloak' profile found, falling back to direct service detection..."
  mapfile -t ALL_SERVS < <(compose_list_services)
  echo "[start_keycloak_services] All available services: ${ALL_SERVS[*]}"

  want=(keycloak kc_postgres)
  chosen=()
  for w in "${want[@]}"; do
    for s in "${ALL_SERVS[@]}"; do
      if [[ "$s" == "$w" ]]; then
        echo "[start_keycloak_services] Matched service '$w'"
        chosen+=("$w")
        break
      fi
    done
  done

  if ((${#chosen[@]}==0)); then
    echo "⚠️  Neither a 'keycloak' profile nor 'keycloak' service was detected."
    echo "   Services available: ${ALL_SERVS[*]}"
    echo "[start_keycloak_services] Exiting, nothing to start"
    prompt_return
    return 1
  fi

  echo "[start_keycloak_services] Starting services directly (no profile): ${chosen[*]}"
  compose_up_services "${chosen[@]}"
  echo "[start_keycloak_services] Compose up complete (direct services)"
  echo "[start_keycloak_services] Returning to menu..."
  prompt_return
  echo "[start_keycloak_services] Finished execution"
}

# --- Run a compose command *inside* the Podman VM (macOS) ---
# Usage: vm_compose_in_dir "$PWD" -f docker-compose.yml up -d svc1 svc2 ...


# Return list of services in a profile (1 per line)
__services_for_profile() {
  local prof="$1"
  $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF'
}

__rm_existing_for_profile() {
  local prof="$1"
  local project; project="$(__compose_project_name)"
  mapfile -t svcs < <(__services_for_profile "$prof")
  ((${#svcs[@]})) || return 0

  # Use VM if present to avoid host/VM storage path issues
  if pm_ssh -h >/dev/null 2>&1; then
    for s in "${svcs[@]}"; do
      local cmd="podman ps -a \
        --filter 'label=io.podman.compose.project=${project}' \
        --filter 'label=io.podman.compose.service=${s}' -q \
        | xargs -r podman rm -f -v || true
      if [ \$(podman ps -a \
        --filter 'label=com.docker.compose.project=${project}' \
        --filter 'label=com.docker.compose.service=${s}' -q | wc -l) -gt 0 ]; then
        podman ps -a \
          --filter 'label=com.docker.compose.project=${project}' \
          --filter 'label=com.docker.compose.service=${s}' -q \
          | xargs -r podman rm -f -v || true
      fi"
      echo "  - VM cleanup for service: $s"
      pm_ssh ssh -- bash -lc "$cmd"
    done
  else
    # Host fallback
    for s in "${svcs[@]}"; do
      mapfile -t ids < <(podman ps -a \
        --filter "label=io.podman.compose.project=${project}" \
        --filter "label=io.podman.compose.service=${s}" -q 2>/dev/null)
      ((${#ids[@]}==0)) && mapfile -t ids < <(podman ps -a \
        --filter "label=com.docker.compose.project=${project}" \
        --filter "label=com.docker.compose.service=${s}" -q 2>/dev/null)
      ((${#ids[@]})) || continue
      podman rm -f "${ids[@]}" >/dev/null 2>&1 || true
    done
  fi
}


# Detect whether the Podman VM has the overlay-containers path (needed by filebeat-podman)
__podman_vm_has_overlay() {
  if command -v podman >/dev/null 2>&1 && pm_ssh -h >/dev/null 2>&1; then
    pm_ssh ssh -- test -d /var/lib/containers/storage/overlay-containers
    return $?
  fi
  return 1
}

# Recreate all containers in a given profile (stop → rm → maybe build → up)
recreate_profile() {
  local prof="${1:-elastic}"
  echo "🔄 Recreating all containers for profile: ${prof}"

  echo "# 0) Ensure external networks"
  prompt_return

  echo "# 1) Down (ignore noisy 'no such container') --profile ${prof}"
  prompt_return
  compose_stop_rm_profile "$prof"

  echo "# 2) Extra cleanup of anything lingering with compose labels (profile-scoped)"
  __rm_existing_for_profile "$prof"

  echo "# 3) Rebuild images if needed"
  maybe_build_profile "$prof"

  echo "# 4) Decide service set (optionally skip filebeat-podman if VM path missing)"
  local -a SVCS=()
  mapfile -t SVCS < <($COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF')

  # Drop filebeat-podman when overlay path isn’t visible in the Podman VM
  if [[ " ${SVCS[*]} " == *" filebeat-podman "* ]] && ! __podman_vm_has_overlay; then
    echo "⚠️  Skipping 'filebeat-podman' (Podman VM overlay path not visible)."
    SVCS=("${SVCS[@]/filebeat-podman}")
  fi

  echo "# 5) Up"
  if ((${#SVCS[@]})); then
    echo "▶️  Up: ${SVCS[*]}"
    $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d --force-recreate "${SVCS[@]}"
  else
    echo "ℹ️  No services resolved for profile '${prof}'"
  fi
}


# Simple interactive prompt
prompt_recreate_profile() {
  echo
  echo "🔧 Recreate Containers"
  echo "======================"
  echo "This will stop, remove, rebuild, and restart all containers in a profile."
  echo
  echo "Available profiles:"
  compose_profiles
  echo
  read -rp "Enter profile to recreate [elastic]: " prof
  prof="${prof:-elastic}"
  read -rp "Are you sure you want to recreate ALL containers in profile '${prof}'? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { echo "❌ Cancelled."; return 0; }
  recreate_profile "$prof"
}


down_all() {
  echo "[down_all] Invoked"

  echo "[down_all] Determining compose command..."
  local CMD; CMD="$(__compose_cmd)" || {
    echo "[down_all] Failed to determine compose command → exiting"
    return $?
  }
  echo "[down_all] Compose command: $CMD"

  echo "[down_all] Determining project name..."
  local PROJECT; PROJECT="$(__compose_project_name)"
  echo "[down_all] Project: $PROJECT"

  local COMPOSE_FILE_LOCAL="${COMPOSE_FILE:-docker-compose.yml}"
  echo "[down_all] Compose file: $COMPOSE_FILE_LOCAL"

  # Split the compose command into an array (e.g., "docker compose" or "podman compose" or "docker-compose")
  echo "[down_all] Splitting compose command into array..."
  local -a CMD_ARR; IFS=' ' read -r -a CMD_ARR <<< "$CMD"
  local ENGINE="${CMD_ARR[0]}"
  [[ "$ENGINE" == "docker-compose" ]] && ENGINE="docker"
  echo "[down_all] Engine detected: $ENGINE"
  echo "[down_all] Command array: ${CMD_ARR[*]}"

  echo "🔻 Bringing down ALL compose services for project '${PROJECT}'…"
  set +e
  echo "[down_all] Running: ${CMD_ARR[*]} -f \"$COMPOSE_FILE_LOCAL\" -p \"$PROJECT\" down --remove-orphans -v"
  "${CMD_ARR[@]}" -f "$COMPOSE_FILE_LOCAL" -p "$PROJECT" down --remove-orphans -v >/dev/null 2>&1
  echo "[down_all] Compose down command complete"
  set -e

  # -------- Containers --------
  echo "🧹 Removing leftover containers…"
  local cids
  cids="$($ENGINE ps -a --filter "label=com.docker.compose.project=${PROJECT}" -q 2>/dev/null)"
  echo "[down_all] Container IDs found: ${cids:-<none>}"
  if [[ -n "$cids" ]]; then
    echo "[down_all] Removing containers: $cids"
    $ENGINE rm -f $cids >/dev/null 2>&1 || true
  fi

  # -------- Networks --------
  echo "🧹 Removing leftover networks…"
  local nids
  nids="$($ENGINE network ls --filter "label=com.docker.compose.project=${PROJECT}" -q 2>/dev/null)"
  echo "[down_all] Network IDs found: ${nids:-<none>}"
  if [[ -n "$nids" ]]; then
    echo "[down_all] Removing networks: $nids"
    $ENGINE network rm $nids >/dev/null 2>&1 || true
  fi
  # Also remove common names if they still exist (label-less fallbacks)
  for net in "${PROJECT}_osss-net" "${PROJECT}_default" "osss-net"; do
    if $ENGINE network inspect "$net" >/dev/null 2>&1; then
      echo "[down_all] Removing fallback network: $net"
      $ENGINE network rm "$net" >/dev/null 2>&1 || true
    else
      echo "[down_all] Fallback network '$net' not found"
    fi
  done

  # -------- Volumes --------
  echo "🧹 Removing leftover volumes…"
  local vids
  vids="$($ENGINE volume ls --filter "label=com.docker.compose.project=${PROJECT}" -q 2>/dev/null)"
  echo "[down_all] Volume IDs found: ${vids:-<none>}"
  if [[ -n "$vids" ]]; then
    echo "[down_all] Removing volumes: $vids"
    $ENGINE volume rm -f $vids >/dev/null 2>&1 || true
  fi
  # Fallback: remove project-prefixed volumes even if not labeled
  echo "[down_all] Checking for fallback volumes with prefix '${PROJECT}_'..."
  mapfile -t VOLS < <($ENGINE volume ls --format '{{.Name}}' 2>/dev/null | grep -E "^${PROJECT}_" || true)
  if ((${#VOLS[@]})); then
    echo "[down_all] Removing fallback volumes: ${VOLS[*]}"
    for v in "${VOLS[@]}"; do
      $ENGINE volume rm -f "$v" >/dev/null 2>&1 || true
    done
  else
    echo "[down_all] No fallback volumes found"
  fi

  echo "✅ All services down for project '${PROJECT}'."
  echo "[down_all] Returning to menu..."
  prompt_return
  echo "[down_all] Finished execution"
}


start_profile_elastic() {
  echo "[start_profile_elastic] Ensuring hosts entry for keycloak..."




  # Start elastic stack in one shot
  prompt_recreate_profile elastic
  up_profile_with_podman elastic || { echo "❌ compose up failed (elastic)"; prompt_return; return 1; }
  prompt_return
}




start_profile_app()          { start_profile_with_build_prompt app; }
start_profile_web_app()      { start_profile_with_build_prompt web-app; }
start_profile_vault()        { start_profile_with_build_prompt vault; }

start_profile_trino() {
  up_force_profile trino
}

start_profile_airflow()      { start_profile_with_build_prompt airflow; }
start_profile_superset()     { start_profile_with_build_prompt superset; }

# ✅ Start all services for a profile in ONE compose call.
# Falls back to a sequenced bring-up for 'elastic' if the provider throws
# a "depends on container … not found in input list" error.
up_profile_with_podman() {
  podman_require_ready_or_die() { podman_ready_once; }

  set -Eeuo pipefail

  local CMD; CMD="$(__compose_cmd)" || return $?
  local FILE="${COMPOSE_FILE:-docker-compose.yml}"
  local PROFILE="${1:-elastic}"
  local PROJECT; PROJECT="$(__compose_project_name)"

  echo "CMD: ${CMD}"
  echo "FILE: ${FILE}"
  echo "PROFILE: ${PROFILE}"
  echo "PROJECT: ${PROJECT}"
  prompt_return             # defaults to "Press Enter to continue..."

  # Split provider ("podman compose" vs "podman-compose") into argv
  local -a CMDA; IFS=' ' read -r -a CMDA <<<"$CMD"

  # Resolve services that belong to the profile
  local -a SVCS=()
  if "${CMDA[@]}" -f "$FILE" --profile "$PROFILE" config --services >/dev/null 2>&1; then
    mapfile -t SVCS < <("${CMDA[@]}" -f "$FILE" --profile "$PROFILE" config --services 2>/dev/null | awk 'NF')
  else
    mapfile -t SVCS < <(services_for_profile_from_yaml "$PROFILE" 2>/dev/null || true)
  fi
  ((${#SVCS[@]})) || { echo "⚠️  No services for profile '$PROFILE' in $FILE"; return 1; }




  echo "[up_profile_with_podman] Provider: $CMD"
  echo "[up_profile_with_podman] File: $FILE   Profile: $PROFILE"
  echo "[up_profile_with_podman] Services: ${SVCS[*]}"
  echo "[up_profile_with_podman] 🧹 Pre-clean stale containers/pods for this profile…"

  prompt_return

  # Targeted cleanup: remove only containers/pods for these services (by label)
  local s ids pods
  for s in "${SVCS[@]}"; do

    echo "SVCS: ${s}"

    ids="$(podman ps -a --filter "label=io.podman.compose.project=${PROJECT}" \
                      --filter "label=io.podman.compose.service=${s}" -q 2>/dev/null || true)"

    echo "ids: ${ids}"
    prompt_return


    if [[ -n "$ids" ]]; then
      pods="$(podman inspect -f '{{.PodName}}' $ids 2>/dev/null | awk 'NF && $0!="<no value>" && !seen[$0]++' || true)"

      echo "about ready to stop these pods: ${pods}"
      prompt_return

      [[ -n "$pods" ]] && { echo "  - stopping pods: $pods"; podman pod stop $pods >/dev/null 2>&1 || true; }
      echo "  - removing containers: $ids"
      podman rm -f -v $ids >/dev/null 2>&1 || true
      [[ -n "$pods" ]] && { echo "  - removing pods: $pods"; podman pod rm -f $pods >/dev/null 2>&1 || true; }
    fi
  done

  echo "[up_profile_with_podman] 🚀 Single compose call (no explicit services, force-recreate)…"
  set +e
  "${CMDA[@]}" -f "$FILE" --profile "$PROFILE" up -d --force-recreate
  local rc=$?
  set -e
  if (( rc == 0 )); then
    return 0
  fi

  if [[ "$PROFILE" == "elastic" ]]; then
    echo "[up_profile_with_podman] ⚠️ Compose failed; using elastic fallback sequencer…"

    echo "# starting phase 1: core"
    prompt_return             # defaults to "Press Enter to continue..."

    "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps shared-vol-init elasticsearch
    _wait_health "elasticsearch" 180

    echo "# starting phase 2: init + kibana"
    prompt_return             # defaults to "Press Enter to continue..."

    "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps kibana-pass-init
    _wait_exit0 "kibana-pass-init" 180
    "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps kibana

    echo "# starting phase 3: api key init"
    prompt_return             # defaults to "Press Enter to continue..."

    if "${CMDA[@]}" -f "$FILE" --profile elastic config --services 2>/dev/null | grep -qx 'api-key-init'; then
      "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps api-key-init
      _wait_exit0 "api-key-init" 180
    fi

    echo "# starting phase 4: filebeat (optional)"
    prompt_return             # defaults to "Press Enter to continue..."

    if "${CMDA[@]}" -f "$FILE" --profile elastic config --services 2>/dev/null | grep -qx 'filebeat-setup'; then
      "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps filebeat-setup
      _wait_exit0 "filebeat-setup" 180
    fi
    if "${CMDA[@]}" -f "$FILE" --profile elastic config --services 2>/dev/null | grep -qx 'filebeat'; then
      "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps filebeat
    fi

    return 0
  fi

  return $rc
}

# Wait until service’s newest container is healthy (or running with no HC)
_wait_health() {
  local svc="$1" timeout="${2:-180}" start now cid state health
  start="$(date +%s)"
  while :; do
    cid="$(last_container_id "$svc" || true)"
    [[ -n "$cid" ]] || sleep 1
    state="$(podman inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || true)"
    health="$(podman inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || true)"
    if { [[ "$health" == "healthy" ]] || { [[ "$health" == "none" ]] && [[ "$state" == "running" ]]; }; }; then
      echo "✅ $svc is ready"
      break
    fi
    now="$(date +%s)"; (( now - start > timeout )) && { echo "⏱️  $svc readiness timed out"; return 1; }
    sleep 2
  done
}

# Wait until an init/one-off container exits with code 0
_wait_exit0() {
  local svc="$1" timeout="${2:-180}" start now cid code
  start="$(date +%s)"
  while :; do
    cid="$(last_container_id "$svc" || true)"
    [[ -n "$cid" ]] || { sleep 1; continue; }
    code="$(podman inspect -f '{{.State.ExitCode}}' "$cid" 2>/dev/null || echo '')"
    if [[ "$code" == "0" ]]; then
      echo "✅ $svc completed successfully"
      break
    fi
    now="$(date +%s)"; (( now - start > timeout )) && { echo "⏱️  $svc completion timed out"; return 1; }
    sleep 2
  done
}


start_profile_openmetadata() {
  echo "▶️  Starting profile 'openmetadata' inside the Podman VM (dependencies honored)…"
  pm_ssh ssh -- bash -lc "
set -Eeuo pipefail

# 👉 Adjust this to your project path inside the Podman VM if needed
cd /Users/rubelw/projects/OSSS

# --- Pick a compose provider in the VM ---
have_podman_compose() { podman compose version >/dev/null 2>&1; }

install_compose_plugin() {
  # Install docker-compose v2 plugin into ~/.docker/cli-plugins/docker-compose (no root needed)
  local ver=\"\${COMPOSE_PLUGIN_VERSION:-v2.29.7}\"
  local arch=\"\$(uname -m)\"
  case \"\$arch\" in
    x86_64|amd64) arch=\"x86_64\" ;;
    aarch64|arm64) arch=\"aarch64\" ;;
    *) echo \"❌ Unsupported arch: \$arch\"; return 1 ;;
  esac
  local url=\"https://github.com/docker/compose/releases/download/\${ver}/docker-compose-linux-\${arch}\"
  local dst=\"\$HOME/.docker/cli-plugins/docker-compose\"
  mkdir -p \"\$(dirname \"\$dst\")\"
  echo \"⬇️  Installing docker-compose plugin \${ver} for \${arch} -> \$dst\"
  curl -fsSL \"\$url\" -o \"\$dst\"
  chmod +x \"\$dst\"
}

install_podman_compose_py() {
  echo \"ℹ️  Installing podman-compose via pip (user)…\"
  if ! python3 -m pip --version >/dev/null 2>&1; then
    echo \"ℹ️  Bootstrapping pip (user)…\"
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    python3 /tmp/get-pip.py --user
  fi
  export PATH=\"\$HOME/.local/bin:\$PATH\"
  python3 -m pip install --user --upgrade podman-compose
}

PROVIDER=\"\"
if have_podman_compose; then
  PROVIDER=\"podman compose\"
else
  if install_compose_plugin && have_podman_compose; then
    PROVIDER=\"podman compose\"
  else
    if command -v podman-compose >/dev/null 2>&1; then
      PROVIDER=\"podman-compose\"
    else
      install_podman_compose_py
      PROVIDER=\"podman-compose\"
    fi
  fi
fi

echo \"ℹ️  Compose provider in VM: \$PROVIDER\"

# --- Phase 1: bring up ONLY MySQL ---
\$PROVIDER -f docker-compose.yml up -d mysql


# --- Phase 2: wait until MySQL is healthy ---
echo \"⏳ waiting for openmetadata-mysql to be healthy…\"
for i in \$(seq 1 240); do
  # get the exact container id
  CID=\$(podman ps -aq --filter name=^openmetadata-mysql\$ | head -n1)
  echo \"\$CID\"

  if [ -z \"\$CID\" ]; then
    echo \"❌ openmetadata-mysql not found\"
    exit 1
  fi

  # read state + health (health can be nil if no healthcheck)
  state=\$(podman inspect -f '{{.State.Status}}' \"\$CID\" 2>/dev/null || echo unknown)
  health=\$(podman inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \"\$CID\" 2>/dev/null || echo unknown)
  echo \"state=\$state health=\$health\"

  if [ \"\$health\" = \"healthy\" ] || { [ \"\$health\" = \"none\" ] && [ \"\$state\" = \"running\" ]; }; then
    echo \"✅ openmetadata-mysql is ready\"
    break   # keep if this lives inside a wait loop
  fi

  sleep 2
done

# --- Phase 3: now bring up OpenMetadata ---
\$PROVIDER -f docker-compose.yml --profile openmetadata up -d openmetadata-server
\$PROVIDER -f docker-compose.yml --profile openmetadata up -d openmetadata-ingestion

"
  prompt_return
}



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

# --- stop + remove containers for a profile, independent of shim limitations ---
# Stop & remove ONLY the services in the given profile (keeps other profiles running)
compose_stop_rm_profile() {
  local prof="$1"
  # get services belonging to this profile from the compose file
  mapfile -t svcs < <(services_for_profile_from_yaml "$prof")
  if ((${#svcs[@]}==0)); then
    echo "ℹ️ No services found for profile '$prof' in $COMPOSE_FILE"; return 0
  fi

  echo "+ $COMPOSE -f \"$COMPOSE_FILE\" stop ${svcs[*]}"
  $COMPOSE -f "$COMPOSE_FILE" stop "${svcs[@]}" || true

  # Try native 'rm'; if unavailable (podman-compose), fall back to label-based rm
  if $COMPOSE -f "$COMPOSE_FILE" rm -f -v "${svcs[@]}" 2>/dev/null; then
    :
  else
    echo "ℹ️  Using label-based cleanup (compose provider has no 'rm')"
    local project; project="$(__compose_project_name)"
    for s in "${svcs[@]}"; do
      # Remove containers just for this service in this project
      podman ps -a \
        --filter "label=com.docker.compose.project=${project}" \
        --filter "label=com.docker.compose.service=${s}" -q \
      | xargs -r podman rm -f -v
    done
  fi
}


# -------- Trino cert helpers --------
create_trino_cert() {
  local dir="config_files/trino/etc/keystore"
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
    -ext "SAN=dns:localhost,dns:trino,dns:trino.local,dns:trino.osss.local,dns:host.docker.internal,ip:127.0.0.1,ip:0.0.0.0" \
    -ext "BasicConstraints=ca:false" \
    -ext "ExtendedKeyUsage=serverAuth" \
    -noprompt || { echo "❌ keytool failed"; prompt_return; return 1; }

  echo "✅ Trino keystore created: $ks (password: changeit)"
  echo "🔎 Keystore contents:"
  keytool -list -keystore "$ks" -storepass changeit
  prompt_return
}
# -------- keycloak cert helpers --------
create_keycloak_cert() {
  set -euo pipefail
  local dir="config_files/keycloak"
  mkdir -p "${dir}/secrets/ca" "${dir}/secrets/keycloak"

  # 1) Root CA (self-signed)
  #    Includes CA extensions so it’s clearly a CA cert
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -subj "/CN=osss-dev-ca" \
    -keyout "${dir}/secrets/ca/ca.key" \
    -out    "${dir}/secrets/ca/ca.crt" \
    -addext "basicConstraints = critical, CA:true" \
    -addext "keyUsage = critical, keyCertSign, cRLSign"

  # 2) Keycloak server key + CSR with SANs
  openssl req -new -nodes -newkey rsa:2048 \
    -subj "/CN=keycloak" \
    -keyout "${dir}/secrets/keycloak/server.key" \
    -out    "${dir}/secrets/keycloak/server.csr" \
    -addext "subjectAltName = DNS:keycloak, DNS:keycloak.local, DNS:localhost, IP:127.0.0.1"

  # 3) Sign the server cert with the CA, adding server extensions
  #    Use a temporary extfile to include SAN + EKU/KU, and ensure CA:false
  tmp_ext="$(mktemp)"
  cat > "$tmp_ext" <<'EOF'
basicConstraints = CA:false
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:keycloak, DNS:keycloak.local, DNS:localhost, IP:127.0.0.1
EOF

  openssl x509 -req -days 365 \
    -in  "${dir}/secrets/keycloak/server.csr" \
    -CA  "${dir}/secrets/ca/ca.crt" \
    -CAkey "${dir}/secrets/ca/ca.key" \
    -CAcreateserial \
    -out "${dir}/secrets/keycloak/server.crt" \
    -extfile "$tmp_ext"

  rm -f "$tmp_ext" "${dir}/secrets/ca/ca.srl" 2>/dev/null || true

  # 4) Create a proper CA bundle (PEM **only**). Since you have no intermediates,
  #    the CA bundle is just the CA certificate.
  cp "${dir}/secrets/ca/ca.crt" "${dir}/secrets/ca/ca-bundle.pem"

  # 5) Quick sanity checks
  echo "== Bundle BEGIN markers =="
  grep -n "BEGIN CERTIFICATE" "${dir}/secrets/ca/ca-bundle.pem"
  echo "== Verify server against CA =="
  openssl verify -CAfile "${dir}/secrets/ca/ca-bundle.pem" "${dir}/secrets/keycloak/server.crt" || true

  echo "✅ Created:"
  echo "  CA key:   ${dir}/secrets/ca/ca.key"
  echo "  CA cert:  ${dir}/secrets/ca/ca.crt"
  echo "  Bundle:   ${dir}/secrets/ca/ca-bundle.pem"
  echo "  Server key: ${dir}/secrets/keycloak/server.key"
  echo "  Server crt: ${dir}/secrets/keycloak/server.crt"

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

# Return top-level *volume keys* from the rendered compose config.
# e.g. outputs: es-data, es-shared, ...
compose_top_level_volume_keys() {
  local CMD; CMD="$(__compose_cmd)" || return $?
  local FILE="${COMPOSE_FILE:-docker-compose.yml}"
  local -a CMDA; IFS=' ' read -r -a CMDA <<<"$CMD"

  "${CMDA[@]}" -f "$FILE" config 2>/dev/null | awk '
    function indent(s){ match(s, /^[ \t]*/); return RLENGTH }
    BEGIN { in_vols=0; vindent=-1 }
    /^[ \t]*volumes:[ \t]*$/ { in_vols=1; vindent=indent($0); next }
    {
      if (in_vols) {
        line_indent = indent($0)
        if ($0 ~ /^[ \t]*$/) next
        # leave volumes when dedent to top or next top-level key
        if (line_indent <= vindent && $0 !~ /^[ \t]/) { in_vols=0; next }
        # keys under volumes: "  es-data:" → print "es-data"
        if ($0 ~ /^[ \t]*[A-Za-z0-9._-]+:[ \t]*$/ && line_indent > vindent) {
          k=$0; sub(/^[ \t]+/,"",k); sub(/:.*/,"",k); print k
        }
      }
    }'
}



# --- find named volumes for services via normalized compose config ---
compose_named_vols_for_services_cli() {
  local PROFILE="$1"; shift
  local SERVICES=("$@")
  local CMD; CMD="$(__compose_cmd)" || return 0

  # split "podman compose" / "docker compose" into argv
  local -a CMD_ARR; IFS=' ' read -r -a CMD_ARR <<< "$CMD"

  local FILE="${COMPOSE_FILE:-docker-compose.yml}"
  local cfg=""
  if ! cfg="$("${CMD_ARR[@]}" -f "$FILE" --profile "$PROFILE" config 2>/dev/null)"; then
    cfg="$("${CMD_ARR[@]}" -f "$FILE" config 2>/dev/null || true)"
  fi
  [[ -z "$cfg" ]] && return 0

  # ✅ correct way to pass a shell var to BSD awk:
  local list; list="$(printf '%s ' "${SERVICES[@]}")"

  printf '%s\n' "$cfg" | awk -v list="$list" '
    function has(x, s,   i,n,a){ n=split(s,a," "); for(i=1;i<=n;i++) if(a[i]==x) return 1; return 0 }
    function indent(s){ match(s,/^[ \t]*/); return RLENGTH }

    BEGIN { in_services=0; in_target=0; in_vols=0; in_item=0; sind=-1; vind=-1; svc="" }

    /^[ \t]*services:[ \t]*$/ { in_services=1; sind=indent($0); next }

    in_services {
      lin=indent($0)
      # leaving services section
      if (lin <= sind && $0 !~ /^[ \t]*$/) { in_services=0; in_target=0; in_vols=0; in_item=0; next }

      # service header "<name>:"
      if (match($0,/^[ \t]*([A-Za-z0-9._-]+):[ \t]*$/,m)) { svc=m[1]; in_target=has(svc,list); in_vols=0; in_item=0; next }
      if (!in_target) next

      # start of volumes block
      if ($0 ~ /^[ \t]*volumes:[ \t]*$/) { in_vols=1; vind=lin; in_item=0; next }

      # inline volumes: [a:/x, b:/y]
      if ($0 ~ /^[ \t]*volumes:[ \t]*\[/) {
        s=$0; sub(/^[^[]*\[/,"",s); sub(/\].*$/,"",s)
        n=split(s,a,","); for(i=1;i<=n;i++){
          v=a[i]; gsub(/^[ \t]+|[ \t]+$/,"",v)
          split(v,kv,":"); src=kv[1]
          if (src !~ /^(\/|\.\/|\$\{)/ && src!="") print src
        }
        next
      }

      if (in_vols) {
        # end of block when dedent or new key
        if (lin <= vind && $0 !~ /^[ \t]*$/) { in_vols=0; in_item=0; next }

        # short form: "- vol:/path"
        if ($0 ~ /^[ \t]*-[ \t]*[^:]+:[^:]+$/) {
          item=$0; sub(/^[^ -]*-[ \t]*/,"",item)
          split(item,kv,":"); src=kv[1]; gsub(/[ \t]/,"",src)
          if (src !~ /^(\/|\.\/|\$\{)/ && src!="") print src
          next
        }

        # start of long form item "-"
        if ($0 ~ /^[ \t]*-[ \t]*$/) { in_item=1; next }

        # long form field "source: volname"
        if (in_item && $0 ~ /^[ \t]*source:[ \t]*/) {
          src=$0; sub(/^[^:]*:[ \t]*/,"",src); gsub(/^[ \t]+|[ \t]+$/,"",src)
          if (src !~ /^(\/|\.\/|\$\{)/ && src!="") print src
          next
        }

        # next item
        if (in_item && $0 ~ /^[ \t]*-[ \t]*/) { in_item=0 }
      }
    }'
}

# --- remove project volumes for selected services (works even if no containers exist) ---
remove_volumes_for_services() {
  local project="$1"; shift
  local prof="$1"; shift
  local svcs=("$@")

  # Which engine are we talking to?
  local ENGINE; ENGINE="$(get_compose_engine)"

  # 1) Collect attached volumes from existing containers (if any)
  local project_label service_label
  if [[ "$ENGINE" == "podman" ]]; then
    project_label="io.podman.compose.project"
    service_label="io.podman.compose.service"
  else
    project_label="com.docker.compose.project"
    service_label="com.docker.compose.service"
  fi

  local -a ps_args=('ps' '-a' '--format' '{{.ID}}' '--filter' "label=${project_label}=${project}")
  local s
  for s in "${svcs[@]}"; do
    ps_args+=(--filter "label=${service_label}=${s}")
  done

  local CIDS
  CIDS="$(engine_exec "$ENGINE" "${ps_args[@]}" | awk 'NF')" || CIDS=""

  local VOL_ATTACHED=""
  if [[ -n "$CIDS" ]]; then
    VOL_ATTACHED="$(
      engine_exec "$ENGINE" inspect -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{"\n"}}{{end}}{{end}}' $CIDS \
        | awk 'NF && !seen[$0]++'
    )"
  fi

  # 2) Collect named volumes from compose config for the same services
  local -a base_vols=()
  # readarray is shimmed to mapfile in this script for Bash 3.x
  # tolerate awk/parse failure without tripping set -euo pipefail
  if ! readarray -t base_vols < <(compose_named_vols_for_services_cli "$prof" "${svcs[@]}" 2>/dev/null || true); then
    base_vols=()
  fi

  # Elastic-specific safety net (if parsing ever returns empty)
  if [[ "$prof" == "elastic" && ${#base_vols[@]} -eq 0 ]]; then
    base_vols=(es-data es-shared)
  fi

  # 3) Union of everything we’ve found
  local -a to_remove=()
  if [[ -n "$VOL_ATTACHED" ]]; then
    while IFS= read -r v; do
      [[ -n "$v" ]] && to_remove+=("$v")
    done <<<"$VOL_ATTACHED"
  fi

  if ((${#base_vols[@]})); then
    for v in "${base_vols[@]}"; do
      to_remove+=("$v" "${project}_${v}")
    done
  fi

  # 4) Dedup (portable) and remove only those that actually exist
  #    (mapfile is shimmed on macOS Bash 3.x)
  mapfile -t to_remove < <(printf '%s\n' "${to_remove[@]}" | awk 'NF && !seen[$0]++')

  if ((${#to_remove[@]})); then
    local vname
    for vname in "${to_remove[@]}"; do
      # Check existence before removing
      if $ENGINE volume inspect "$vname" >/dev/null 2>&1; then
        echo "🧹 Removing volume: $vname"
        $ENGINE volume rm -f "$vname" >/dev/null 2>&1 || true
      fi
    done
  fi
}



# --- helpers ---------------------------------------------------------------

__compose_label_keys() {
  local CMD; CMD="$(__compose_cmd)" || return 1
  local ENGINE
  ENGINE="$(printf '%s\n' "$CMD" | awk '{print $1}')"  # "podman" or "docker"
  if [[ "$ENGINE" == "podman" ]]; then
    PROJECT_LABEL="io.podman.compose.project"
    SERVICE_LABEL="io.podman.compose.service"
  else
    PROJECT_LABEL="com.docker.compose.project"
    SERVICE_LABEL="com.docker.compose.service"
  fi
}

# --- resolve services in a profile using compose itself ---
compose_services_for_profile() {
  local prof="$1"
  local CMD; CMD="$(__compose_cmd)" || return 1
  local FILE="${COMPOSE_FILE:-docker-compose.yml}"
  "$CMD" -f "$FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF'
}

# -------- Podman reset helper --------
reset_podman_machine() {
  echo "⚠️  This will wipe all Podman machine state and start clean."
  read -rp "Proceed? [y/N] " ans || true
  [[ ! "$ans" =~ ^[Yy]$ ]] && { echo "❌ Cancelled."; prompt_return; return 0; }

  set -euo pipefail

  podman --version || true

  # Decide a machine name: use active if present, else 'default'
  NAME="${PODMAN_MACHINE_NAME:-$(podman machine active 2>/dev/null || echo default)}"

  # 1) Stop if it exists
  if podman machine inspect "$NAME" >/dev/null 2>&1; then
    echo "▶️  Stopping podman machine '$NAME'…"
    podman machine stop "$NAME" || true
    echo "🗑  Removing '$NAME'…"
    podman machine rm -f "$NAME" || true
  else
    echo "(no VM named '$NAME' to stop/remove)"
  fi

  # 2) Drop stale connections (both rootless/root)
  podman system connection rm "$NAME" "$NAME-root" 2>/dev/null || true

  # 3) macOS: clear any leftover local state safely (best-effort)
  if [[ "$(uname -s)" == "Darwin" ]]; then
    rm -rf ~/.config/containers/podman/machine \
           ~/.local/share/containers/podman/machine \
           ~/.ssh/"$NAME"* 2>/dev/null || true
  fi

  # 4) Recreate + start
  echo "🛠  Initializing '$NAME'…"
  podman machine init "$NAME" --cpus 4 --memory 6144 --disk-size 60
  echo "▶️  Starting '$NAME'…"
  podman machine start "$NAME"

  # 5) Make it the default connection if possible
  podman system connection default "$NAME" 2>/dev/null \
    || podman system connection default "$NAME-root" 2>/dev/null \
    || true

  # 6) Sanity test
  podman run --rm quay.io/podman/hello || true
  prompt_return
}


# Return 0 if safe to proceed; nonzero if storage looks broken.
# Logs only; does NOT modify system state. You can opt-in to auto fixes via env flags.
# Preflight: detect Podman graph root robustly, across versions and remote/local.
preflight_podman_storage() {
  echo "[preflight_podman_storage] Running…"

  # 1) Grab JSON info (prefer this over plain text/greps)
  local INFO RC
  INFO="$(podman info --format '{{json .}}' 2>/dev/null)"; RC=$?
  if ((RC!=0)) || [[ -z "$INFO" ]]; then
    echo "[preflight_podman_storage] ❌ Could not run 'podman info' (rc=$RC)"
    return 1
  fi
  echo "[preflight_podman_storage] Successfully retrieved 'podman info'"

  # 2) Detect remote mode (best-effort; schema differs by version)
  # Try top-level remoteClient, fall back to host.remoteSocket.path presence
  local REMOTE=""
  REMOTE="$(printf '%s' "$INFO" | sed -n 's/.*"remoteClient":[[:space:]]*\(true\|false\).*/\1/p')"
  if [[ -z "$REMOTE" ]]; then
    # If we see a remote socket path, assume remote
    if printf '%s\n' "$INFO" | grep -q '"host"[^{]*"remoteSocket"'; then
      REMOTE=true
    fi
  fi
  echo "[preflight_podman_storage] remoteClient (best-effort): ${REMOTE:-unknown}"

  # 3) Get graph root from JSON first
  local GRAPHROOT=""
  GRAPHROOT="$(printf '%s' "$INFO" | sed -n 's/.*"graphRoot":[[:space:]]*"\([^"]*\)".*/\1/p')"

  # 4) If empty, try Go template key (works across many versions)
  if [[ -z "$GRAPHROOT" ]]; then
    GRAPHROOT="$(podman info --format '{{ .Store.GraphRoot }}' 2>/dev/null || true)"
  fi

  # 5) If still empty on macOS, ask inside the VM directly
  if [[ -z "$GRAPHROOT" && "$(uname -s)" == "Darwin" ]] && pm_ssh inspect >/dev/null 2>&1; then
    GRAPHROOT="$(pm_ssh ssh -- podman info --format '{{ .Store.GraphRoot }}' 2>/dev/null || true)"
    echo "[preflight_podman_storage] Queried VM for GraphRoot."
  fi

  # 6) Final check
  if [[ -z "$GRAPHROOT" ]]; then
    echo "[preflight_podman_storage] ⚠️  Could not detect GraphRoot in this Podman build."
    echo "[preflight_podman_storage] Store section follows (for debugging):"
    podman info --format '{{json .Store}}' || true
    echo "   Tip: ensure your default connection is the VM:"
    echo "        podman system connection default podman-machine-default"
    echo "        pm_ssh start"
    return 1
  fi

  echo "[preflight_podman_storage] GraphRoot: $GRAPHROOT"
  return 0
}






# Run a compose command; print only the command's stdout.
# All our wrapper logs go to stderr so they never leak into argv.
compose_exec() {
  # USAGE: compose_exec <cmd> <args...>
  echo "[compose_exec] ${*}" >&2
  "$@"                             # stream stdout as-is
  local rc=$?
  echo "[compose_exec] rc=$rc" >&2
  return $rc
}

# --- main -----------------------------------------------------------------



down_profile_interactive() {
  echo "[down_profile_interactive] Invoked"

  echo "[down_profile_interactive] Determining compose command..."
  local CMD; CMD="$(__compose_cmd)" || {
    echo "[down_profile_interactive] Failed to determine compose command → exiting"
    return $?
  }
  echo "[down_profile_interactive] Using compose command: $CMD"

  echo "[down_profile_interactive] Determining project/file..."
  local PROJECT; PROJECT="$(__compose_project_name)"
  local COMPOSE_FILE_LOCAL="${COMPOSE_FILE:-docker-compose.yml}"
  echo "[down_profile_interactive] Project: $PROJECT"
  echo "[down_profile_interactive] Compose file: $COMPOSE_FILE_LOCAL"

  echo "[down_profile_interactive] Splitting compose command to detect engine..."
  local -a CMD_ARR; IFS=' ' read -r -a CMD_ARR <<< "$CMD"
  local ENGINE="${CMD_ARR[0]}"; [[ "$ENGINE" == "docker-compose" ]] && ENGINE="docker"
  echo "[down_profile_interactive] Engine: $ENGINE | argv: ${CMD_ARR[*]}"

  echo "ℹ️ ---- Podman storage preflight ------------------------------------------"
  if [[ "$ENGINE" == podman* ]]; then
    if ! preflight_podman_storage "$ENGINE"; then
      echo "⚠️  Podman storage/VM looks unhealthy. Aborting teardown to avoid errors." >&2
      echo "   Run: 'pm_ssh start' and/or 'podman system migrate', then retry." >&2
      prompt_return
      return 1
    fi
  fi

  echo "ℹ️  Using compose command: $CMD"
  echo "ℹ️  Compose project: $PROJECT"
  echo "ℹ️  Compose file:    $COMPOSE_FILE_LOCAL"

  echo "[down_profile_interactive] Discovering profiles..."
  mapfile -t PROFILES < <(discover_profiles)
  echo "🔎 Detected profiles: ${PROFILES[*]:-(none)}"
  if [ "${#PROFILES[@]}" -eq 0 ]; then
    echo "⚠️  No profiles found."
    echo "[down_profile_interactive] Exiting early (no profiles)"
    return 0
  fi

  echo "[down_profile_interactive] Presenting interactive menu..."
  echo "Available profiles:"
  local i=1
  for p in "${PROFILES[@]}"; do printf "  %2d) %s\n" "$i" "$p"; i=$((i+1)); done
  echo "  q) Cancel"
  read -r -p "Select a profile to take down: " choice || {
    echo "[down_profile_interactive] Read aborted; exiting"
    return 0
  }
  case "$choice" in
    q|Q) echo "❌ Cancelled."; echo "[down_profile_interactive] User cancelled"; return 0 ;;
  esac
  echo "[down_profile_interactive] Raw selection: '$choice'"

  local prof
  if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#PROFILES[@]}" ]; then
    prof="${PROFILES[$((choice-1))]}"
    echo "✅ Selected by number: $prof"
  else
    prof="$choice"
    echo "✅ Selected by name: $prof"
  fi


  {
    echo "[down_profile_interactive] Entering teardown (set -x enabled for commands)"
    set -x

    echo "ℹ️ Stop and remove via compose first (engine-agnostic)"
    #compose_exec "${CMD_ARR[@]}" -f "$COMPOSE_FILE_LOCAL" stop "${SVCS[@]}" || true

    # On the HOST shell (where $PWD is your project)
      podman machine ssh default -- bash -lc "
        set -euo pipefail
        HOST_PROJ=$HOST_PROJ
        SERVICE=$prof
        PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
        declare -a SVCS=()
        declare -a CIDS=()
        declare -a VOLS=()

        echo \"HOST_PROJ: \${HOST_PROJ}\"
        echo \"PODMAN_OVERLAY_DIR: \${PODMAN_OVERLAY_DIR}\"
        cd \"\$HOST_PROJ\" || { echo '❌ Path not visible inside VM:' \"\$HOST_PROJ\"; exit 1; }

        test -r docker-compose.yml || { echo \"❌ docker-compose.yml not readable here: \$PWD\"; ls -la; exit 1; }


        # Pick compose provider + the correct remove-volumes flag
        if podman compose version >/dev/null 2>&1; then
          COMPOSE=\"podman compose\"
          DOWN_VOL_FLAG=\"--volumes\"
        elif command -v podman-compose >/dev/null 2>&1; then
          COMPOSE=\"podman-compose\"
          DOWN_VOL_FLAG=\"-v\"
        else
          echo \"❌ Neither podman compose nor podman-compose found.\"
          exit 1
        fi

        # Ensure project name matches compose default (lowercased basename)
        PROJECT=\"\${COMPOSE_PROJECT_NAME:-\$(basename \"\$PWD\" | tr '[:upper:]' '[:lower:]')}\"
        export COMPOSE_PROJECT_NAME=\"\$PROJECT\"
        echo \"PROJECT: \$PROJECT\"
        echo \"▶️  Teardown for profile=\$SERVICE (targeted: services & volumes only)\"

        # Services in this profile
        SVCS=()  # ensure declared under set -u
        mapfile -t SVCS < <(\$COMPOSE -f \"\$HOST_PROJ/docker-compose.yml\" --profile \"\$SERVICE\" \
          config --services 2>/dev/null | awk 'NF') || true

        if ((\${#SVCS[@]}==0)); then
          echo \"ℹ️ No services found for profile '\$SERVICE' (nothing to clean).\"
          exit 0
        fi

        # 2) Pick correct compose label keys (keep for logs only)
        # 2) Pick correct compose label keys (keep for logs only)
        project_label=\"io.podman.compose.project\"
        service_label=\"io.podman.compose.service\"
        if ! podman ps -a --filter \"label=\${project_label}=\${PROJECT}\" -q | grep -q .; then
          project_label=\"com.docker.compose.project\"
          service_label=\"com.docker.compose.service\"
        fi

        # Containers for this project + those services (UNION both label namespaces)
        CIDS=() VOLS=()
        tmp_ids=()
        for s in \"\${SVCS[@]}\"; do
          mapfile -t ids1 < <(podman ps -a -q \
            --filter \"label=io.podman.compose.project=\${PROJECT}\" \
            --filter \"label=io.podman.compose.service=\${s}\" 2>/dev/null || true)
          mapfile -t ids2 < <(podman ps -a -q \
            --filter \"label=com.docker.compose.project=\${PROJECT}\" \
            --filter \"label=com.docker.compose.service=\${s}\" 2>/dev/null || true)
          tmp_ids+=(\"\${ids1[@]:-}\" \"\${ids2[@]:-}\")
        done
        # unique
        mapfile -t CIDS < <(printf '%s\n' \"\${tmp_ids[@]:-}\" | awk 'NF && !seen[\$0]++')
        echo \"→ Matched \${#CIDS[@]} container(s) for services: \${SVCS[*]}\"

        if ((\${#CIDS[@]})); then
          # Volumes mounted by those containers
          mapfile -t VOLS < <(
            podman inspect -f '{{range .Mounts}}{{if eq .Type \"volume\"}}{{.Name}}{{\"\n\"}}{{end}}{{end}}' \
              \"\${CIDS[@]}\" | awk 'NF && !seen[\$0]++'
          ) || true

          echo \"⏹  Stopping containers...\"
          podman stop -t 10 \"\${CIDS[@]}\" >/dev/null 2>&1 || true
          echo \"🗑️  Removing containers...\"
          podman rm -f \"\${CIDS[@]}\" >/dev/null 2>&1 || true





          if ((\${#VOLS[@]})); then
            echo \"🧹 Removing profile volumes: \${VOLS[*]}\"
            podman volume rm -f \"\${VOLS[@]}\" >/dev/null 2>&1 || true
          else
            echo \"ℹ️ No named volumes attached to \${SVCS[*]}.\"
          fi
        else
          echo \"ℹ️ No containers found for services: \${SVCS[*]}\"
          echo \"   (Tip: containers may exist under the other label namespace or a different project name)\"
        fi

      "


  }

  echo "ℹ️ Post-teardown hook (optional per-profile cleanup)"
  if type down_profile_clean >/dev/null 2>&1; then
    # Run for all profiles…
    # down_profile_clean "$prof"

    # …or only for elastic:
    case "$prof" in
      elastic) down_profile_clean "elastic" ;;
    esac
  fi


  echo "✅ Done with profile '${prof}'."
  echo "[down_profile_interactive] Returning to menu..."
  prompt_return
  echo "[down_profile_interactive] Finished execution"
  set +x
}



# -------- Podman VM management --------
# Returns the name of a running VM, or "default" if none running
__podman_vm_name() {
  local n
  n="$(pm_ssh list --format '{{.Name}} {{.Running}}' 2>/dev/null \
       | awk '$2=="true"{print $1; exit}')" || true
  echo "${n:-default}"
}

# Run a command inside the VM (nounset-safe)
pm_ssh() {
  local vm; vm="$(__podman_vm_name)"
  podman machine ssh "$vm" -- "$@"
}

podman_vm_stop() {
  if ! command -v podman >/dev/null 2>&1; then
    echo "Podman not installed."
    return 1
  fi
  local NAME; NAME="$(podman_vm_name)"
  echo "▶️  Stopping pm_ssh '$NAME'…"
  pm_ssh stop "$NAME" || {
    echo "(already stopped or not present)"
    return 0
  }
  echo "✅ Stopped."
}
podman_vm_destroy() {
  if ! command -v podman >/dev/null 2>&1; then
    echo "Podman not installed."
    return 1
  fi
  local NAME; NAME="$(podman_vm_name)"
  echo "⚠️  This will remove the Podman VM '$NAME' and its data (images/containers inside the VM)."
  read -rp "Type the machine name '$NAME' to confirm destroy (or leave blank to cancel): " ans || return 1
  if [[ "$ans" != "$NAME" ]]; then
    echo "Cancelled."
    return 1
  fi
  echo "▶️  Stopping (if running)…"; pm_ssh stop "$NAME" >/dev/null 2>&1 || true
  echo "🗑  Removing pm_ssh '$NAME'…"
  pm_ssh rm -f "$NAME"
  echo "✅ Destroyed pm_ssh '$NAME'."
}


# -------- menu --------
refresh_services() { :; } # compatibility no-op

logs_menu() {
  local tail_n="${TAIL:-$DEFAULT_TAIL}"
  local choice svc_count svc
  local __LOG_SERVICES=()

  # Resolve compose command into an ARRAY (handles spaces in "podman compose" or "podman machine ssh -- podman compose")
  local -a C
  IFS=' ' read -r -a C <<< "${COMPOSE:-podman compose}"

  local file="${COMPOSE_FILE:-docker-compose.yml}"
  local project="${COMPOSE_PROJECT_NAME:-$(basename "$PWD")}"

  echo
  echo "[logs_menu] COMPOSE: ${COMPOSE:-podman compose}"
  echo "[logs_menu] COMPOSE_FILE: ${file}"
  echo "[logs_menu] COMPOSE_PROJECT_NAME: ${project}"
  echo "[logs_menu] TAIL lines: ${tail_n}"
  if [[ -n "${SERVICE:-}" ]]; then
    echo "[logs_menu] SERVICE env detected: ${SERVICE}  (note: unrelated to compose services)"
  fi

  while true; do
    # Prefer running services; fall back to all defined services
    if mapfile -t __LOG_SERVICES < <("${C[@]}" -f "$file" ps --services 2>/dev/null); then
      :
    else
      __LOG_SERVICES=()
    fi
    if (( ${#__LOG_SERVICES[@]} == 0 )); then
      mapfile -t __LOG_SERVICES < <("${C[@]}" -f "$file" config --services 2>/dev/null || true)
    fi

    svc_count="${#__LOG_SERVICES[@]}"
    echo
    echo "==== Logs Menu (${project}) ===="
    echo "Enter a number to follow that service's logs."
    echo "a) follow ALL services"
    echo "t) tail ALL services (no follow)"
    echo "s) set default tail (currently ${DEFAULT_TAIL})"
    echo "r) refresh services   b) back   q) quit"
    echo

    if (( svc_count == 0 )); then
      echo "(No services found for project ${project})"
      echo "[diag] '${C[*]} -f \"$file\" config --services' returned:"
      "${C[@]}" -f "$file" config --services 2>&1 | sed 's/^/  > /'
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
        echo "Following logs for ALL services. Ctrl-C to return…"
        ( trap - INT; "${C[@]}" -f "$file" logs -f --tail "$tail_n" ) || true
        ;;
      t|T)
        echo "Tailing (no follow) logs for ALL services…"
        "${C[@]}" -f "$file" logs --tail "$tail_n" || true
        ;;
      *)
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice>=1 && choice<=svc_count )); then
          svc="${__LOG_SERVICES[$((choice-1))]}"
          echo "Following logs for service: ${svc} (Ctrl-C to return)…"
          ( trap - INT; "${C[@]}" -f "$file" logs -f --tail "$tail_n" "$svc" ) || true
        else
          echo "Unknown choice: ${choice}"
        fi
        ;;
    esac
  done
}


# --- Override: start_keycloak_services (ensure network first) ---
ensure_osss_net() {
  if ! podman network exists osss-net 2>/dev/null; then
    echo "➕ Creating external network: osss-net"
    podman network create osss-net >/dev/null || echo "⚠️  Could not create osss-net (continuing)"
  fi
}


# Follow logs for a single container; Ctrl-C cleanly returns to menu
# Follow logs for a single container; Ctrl-C cleanly returns to menu
logs_follow_container() {
  local name="$1"
  local tail_n="${TAIL:-$DEFAULT_TAIL}"

  # Detect VM (macOS) vs host
  local use_vm="0" vm state
  if podman machine --help >/dev/null 2>&1; then
    vm="$(podman machine active 2>/dev/null || echo default)"
    state="$(podman machine inspect "$vm" --format '{{.State}}' 2>/dev/null || echo '')"
    [[ "$state" == "Running" ]] && use_vm="1"
  fi

  # Existence checks (same behavior as before)
  if [[ "$use_vm" == "1" ]]; then
    if ! podman machine ssh "$vm" -- bash -lc "podman container exists \"$name\""; then
      echo "⚠️  Container '$name' not found in VM '$vm'."
      podman machine ssh "$vm" -- podman ps -a --format "table {{.Names}}\t{{.Status}}" | sed 's/^/  > /'
      return 0
    fi
  else
    if ! podman container exists "$name"; then
      echo "⚠️  Container '$name' not found on host."
      podman ps -a --format "table {{.Names}}\t{{.Status}}" | sed 's/^/  > /'
      return 0
    fi
  fi

  echo "Following logs for container: ${name} (Ctrl-C to return)…"

  # Run follower in a subshell; clear INT trap inside child so Ctrl-C stops it,
  # and don't let set -e kill the menu on nonzero exit.
  set +e
  if [[ "$use_vm" == "1" ]]; then
    ( trap - INT; podman machine ssh "$vm" -- bash -lc "podman logs -f --tail ${tail_n} \"$name\"" ) || true
  else
    ( trap - INT; podman logs -f --tail "$tail_n" "$name" ) || true
  fi
  set -e

  echo "↩ Back to menu"
  return 0
}



logs_menu() {
  while true; do
    echo
    echo "==============================================="
    echo " Logs"
    echo "==============================================="
    echo "1) Logs container 'airflow-init'"
    echo "2) Logs container 'airflow-redis'"
    echo "3) Logs container 'airflow-scheduler'"
    echo "4) Logs container 'airflow-webserver'"
    echo "5) Logs container 'api-key-init'"
    echo "6) Logs container 'app'"
    echo "7) Logs container 'consul'"
    echo "8) Logs container 'consul-jwt-init'"
    echo "9) Logs container 'elasticsearch'"
    echo "10) Logs container 'filebeat-podman'"
    echo "11) Logs container 'filebeat-setup'"
    echo "12) Logs container 'kc_postgres'"
    echo "13) Logs container 'keycloak'"
    echo "14) Logs container 'kibana'"
    echo "15) Logs container 'kibana-pass-init'"
    echo "16) Logs container 'openmetadata-ingestion'"
    echo "17) Logs container 'openmetadata-mysql'"
    echo "18) Logs container 'openmetadata-server'"
    echo "19) Logs container 'osss_postgres'"
    echo "20) Logs container 'postgres-airflow'"
    echo "21) Logs container 'postgres-superset'"
    echo "22) Logs container 'redis'"
    echo "23) Logs container 'shared-vol-init'"
    echo "24) Logs container 'superset'"
    echo "25) Logs container 'superset-init'"
    echo "26) Logs container 'superset_redis'"
    echo "27) Logs container 'trino'"
    echo "28) Logs container 'vault'"
    echo "29) Logs container 'vault-oidc-setup'"
    echo "30) Logs container 'vault-seed'"
    echo "31) Logs container 'web'"
    echo "  q) Back"
    echo "-----------------------------------------------"
    read -rp "Select an option: " choice || return 0
    case "$choice" in
      1)  logs_follow_container "airflow-init" ;;
      2)  logs_follow_container "airflow-redis" ;;
      3)  logs_follow_container "airflow-scheduler" ;;
      4)  logs_follow_container "airflow-webserver" ;;
      5)  logs_follow_container "api-key-init" ;;
      6)  logs_follow_container "app" ;;
      7)  logs_follow_container "consul" ;;
      8)  logs_follow_container "consul-jwt-init" ;;
      9)  logs_follow_container "elasticsearch" ;;
      10)  logs_follow_container "filebeat-podman" ;;
      11)  logs_follow_container "filebeat-setup" ;;
      12)  logs_follow_container "kc_postgres" ;;
      13)  logs_follow_container "keycloak" ;;
      14) logs_follow_container "kibana" ;;
      15) logs_follow_container "kibana-pass-init" ;;
      16) logs_follow_container "openmetadata-ingestion" ;;
      17) logs_follow_container "openmetadata-mysql" ;;
      18) logs_follow_container "openmetadata-server" ;;
      19) logs_follow_container "osss_postgres" ;;
      20) logs_follow_container "postgres-airflow" ;;
      21) logs_follow_container "postgres-superset" ;;
      22) logs_follow_container "redis" ;;
      23) logs_follow_container "shared-vol-init" ;;
      24) logs_follow_container "superset" ;;
      25) logs_follow_container "superset-init" ;;
      26) logs_follow_container "superset_redis" ;;
      27) logs_follow_container "trino" ;;
      28) logs_follow_container "vault" ;;
      29) logs_follow_container "vault-oidc-setup" ;;
      30) logs_follow_container "vault-seed" ;;
      31) logs_follow_container "web" ;;
      q|Q|b|B) return 0 ;;
      *) echo "Unknown choice: ${choice}" ;;
    esac
  done
}


down_profiles_menu() {
  while true; do
    echo
    echo "==============================================="
    echo " Utilities"
    echo "==============================================="
    echo " 1) Destroy profile 'keycloak'"
    echo " 2) Destroy profile 'app'"
    echo " 3) Destroy profile 'web-app'"
    echo " 4) Destroy profile 'elastic'"
    echo " 5) Destroy profile 'vault'"
    echo " 6) Destroy profile 'consul'"
    echo " 7) Destroy profile 'trino'"
    echo " 8) Destroy profile 'airflow'"
    echo "9) Destroy profile 'superset'"
    echo "10) Destroy profile 'openmetadata'"
    echo "  q) Back"
    echo "-----------------------------------------------"
    read -rp "Select an option: " choice || return 0
    case "$choice" in
      1)
        # Destroy keycloak'
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          SERVICE=\"keycloak\"
          PROJECT_ELASTIC=\"osss-keycloak\"

          cd \"\$HOST_PROJ\" || { echo \"❌ Path not visible inside VM:\" \"\$HOST_PROJ\"; exit 1; }

          # Pick compose provider + correct remove-volumes flag
          COMPOSE=() ; DOWN_VOL_FLAG=\"\"
          if podman compose version >/dev/null 2>&1; then
            COMPOSE=(podman compose)
            DOWN_VOL_FLAG=\"--volumes\"
          elif command -v podman-compose >/dev/null 2>&1; then
            COMPOSE=(podman-compose)
            DOWN_VOL_FLAG=\"-v\"
          else
            echo \"❌ Neither podman compose nor podman-compose found.\"
            exit 1
          fi

          for cname in keycloak kc_postgres; do
            echo \"🗑️  Attempting to remove container '\$cname' (with volumes)…\"

            # First stop it if running
            if podman inspect \"\$cname\" --format '{{.State.Running}}' 2>/dev/null | grep -qi true; then
              echo \"⏹️  Container '\$cname' is running, stopping it first…\"
              if podman stop -t 15 \"\$cname\" >/dev/null 2>&1; then
                echo \"✅ Stopped container: \$cname\"
              else
                echo \"⚠️  Failed to stop container '\$cname' (continuing anyway)\"
              fi
            else
              echo \"ℹ️  Container '\$cname' is not running (or does not exist)\"
            fi

            # Then remove with volumes
            if podman rm -v \"\$cname\" >/dev/null 2>&1; then
              echo \"✅ Successfully removed container: \$cname (including anonymous volumes)\"
              continue
            else
              echo \"⚠️  Could not remove container '\$cname'.\"
              echo \"   - It may not exist, or it may still be running under a different name.\"
              echo \"   - Current container list (filtered for \$cname):\"
              podman ps -a --format \"table {{.Names}}\\t{{.Status}}\\t{{.CreatedAt}}\" | grep -E \"NAMES|\$cname\" || true
            fi
          done

          for cid in \$(podman ps -a -q --filter volume=osss-elastic_es-data); do
            echo \"Removing container \$cid using volume…\"
            podman stop \"\$cid\" || true
            podman rm -f \"\$cid\"
          done
          podman volume rm  osss-keycloak_kc_postgres_data
        "

        prompt_return
        ;;
      2)
        # Destroy app'
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          SERVICE=\"app\"
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
        "
        prompt_return
        ;;
      3)
        # Destroy web-app'
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          SERVICE=\"web-app\"
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
        "
        prompt_return
        ;;
      4)
        # Destroy elastic
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          SERVICE=\"elastic\"
          PROJECT_ELASTIC=\"osss-elastic\"

          cd \"\$HOST_PROJ\" || { echo \"❌ Path not visible inside VM:\" \"\$HOST_PROJ\"; exit 1; }

          # Pick compose provider + correct remove-volumes flag
          COMPOSE=() ; DOWN_VOL_FLAG=\"\"
          if podman compose version >/dev/null 2>&1; then
            COMPOSE=(podman compose)
            DOWN_VOL_FLAG=\"--volumes\"
          elif command -v podman-compose >/dev/null 2>&1; then
            COMPOSE=(podman-compose)
            DOWN_VOL_FLAG=\"-v\"
          else
            echo \"❌ Neither podman compose nor podman-compose found.\"
            exit 1
          fi

          for cname in kibana-pass-init elasticsearch kibana; do
            echo \"🗑️  Attempting to remove container '\$cname' (with volumes)…\"

            # First stop it if running
            if podman inspect \"\$cname\" --format '{{.State.Running}}' 2>/dev/null | grep -qi true; then
              echo \"⏹️  Container '\$cname' is running, stopping it first…\"
              if podman stop -t 15 \"\$cname\" >/dev/null 2>&1; then
                echo \"✅ Stopped container: \$cname\"
              else
                echo \"⚠️  Failed to stop container '\$cname' (continuing anyway)\"
              fi
            else
              echo \"ℹ️  Container '\$cname' is not running (or does not exist)\"
            fi

            # Then remove with volumes
            if podman rm -v \"\$cname\" >/dev/null 2>&1; then
              echo \"✅ Successfully removed container: \$cname (including anonymous volumes)\"
              continue
            else
              echo \"⚠️  Could not remove container '\$cname'.\"
              echo \"   - It may not exist, or it may still be running under a different name.\"
              echo \"   - Current container list (filtered for \$cname):\"
              podman ps -a --format \"table {{.Names}}\\t{{.Status}}\\t{{.CreatedAt}}\" | grep -E \"NAMES|\$cname\" || true
            fi
          done

          for cid in \$(podman ps -a -q --filter volume=osss-elastic_es-data); do
            echo \"Removing container \$cid using volume…\"
            podman stop \"\$cid\" || true
            podman rm -f \"\$cid\"
          done
          podman volume rm osss-elastic_es-data
        "
        prompt_return
        ;;
      5)
        # Destroy vault'
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          SERVICE=\"vault\"
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          PROJECT_ELASTIC=\"osss-vault\"

          cd \"\$HOST_PROJ\" || { echo \"❌ Path not visible inside VM:\" \"\$HOST_PROJ\"; exit 1; }

          # Pick compose provider + correct remove-volumes flag
          COMPOSE=() ; DOWN_VOL_FLAG=\"\"
          if podman compose version >/dev/null 2>&1; then
            COMPOSE=(podman compose)
            DOWN_VOL_FLAG=\"--volumes\"
          elif command -v podman-compose >/dev/null 2>&1; then
            COMPOSE=(podman-compose)
            DOWN_VOL_FLAG=\"-v\"
          else
            echo \"❌ Neither podman compose nor podman-compose found.\"
            exit 1
          fi

          for cname in vault vault-oidc-setup vault-seed; do
            echo \"🗑️  Attempting to remove container '\$cname' (with volumes)…\"

            # First stop it if running
            if podman inspect \"\$cname\" --format '{{.State.Running}}' 2>/dev/null | grep -qi true; then
              echo \"⏹️  Container '\$cname' is running, stopping it first…\"
              if podman stop -t 15 \"\$cname\" >/dev/null 2>&1; then
                echo \"✅ Stopped container: \$cname\"
              else
                echo \"⚠️  Failed to stop container '\$cname' (continuing anyway)\"
              fi
            else
              echo \"ℹ️  Container '\$cname' is not running (or does not exist)\"
            fi

            # Then remove with volumes
            if podman rm -v \"\$cname\" >/dev/null 2>&1; then
              echo \"✅ Successfully removed container: \$cname (including anonymous volumes)\"
              continue
            else
              echo \"⚠️  Could not remove container '\$cname'.\"
              echo \"   - It may not exist, or it may still be running under a different name.\"
              echo \"   - Current container list (filtered for \$cname):\"
              podman ps -a --format \"table {{.Names}}\\t{{.Status}}\\t{{.CreatedAt}}\" | grep -E \"NAMES|\$cname\" || true
            fi
          done

          for cid in \$(podman ps -a -q --filter volume=osss-elastic_es-data); do
            echo \"Removing container \$cid using volume…\"
            podman stop \"\$cid\" || true
            podman rm -f \"\$cid\"
          done
        "
        prompt_return
        ;;
      6)
        # Destroy consol'
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          SERVICE=\"consul\"
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          cd \"\$HOST_PROJ\" || { echo \"❌ Path not visible inside VM:\" \"\$HOST_PROJ\"; exit 1; }

          # Pick compose provider + correct remove-volumes flag
          COMPOSE=() ; DOWN_VOL_FLAG=\"\"
          if podman compose version >/dev/null 2>&1; then
            COMPOSE=(podman compose)
            DOWN_VOL_FLAG=\"--volumes\"
          elif command -v podman-compose >/dev/null 2>&1; then
            COMPOSE=(podman-compose)
            DOWN_VOL_FLAG=\"-v\"
          else
            echo \"❌ Neither podman compose nor podman-compose found.\"
            exit 1
          fi

          for cname in consul consul-jwt-init; do
            echo \"🗑️  Attempting to remove container '\$cname' (with volumes)…\"

            # First stop it if running
            if podman inspect \"\$cname\" --format '{{.State.Running}}' 2>/dev/null | grep -qi true; then
              echo \"⏹️  Container '\$cname' is running, stopping it first…\"
              if podman stop -t 15 \"\$cname\" >/dev/null 2>&1; then
                echo \"✅ Stopped container: \$cname\"
              else
                echo \"⚠️  Failed to stop container '\$cname' (continuing anyway)\"
              fi
            else
              echo \"ℹ️  Container '\$cname' is not running (or does not exist)\"
            fi

            # Then remove with volumes
            if podman rm -v \"\$cname\" >/dev/null 2>&1; then
              echo \"✅ Successfully removed container: \$cname (including anonymous volumes)\"
              continue
            else
              echo \"⚠️  Could not remove container '\$cname'.\"
              echo \"   - It may not exist, or it may still be running under a different name.\"
              echo \"   - Current container list (filtered for \$cname):\"
              podman ps -a --format \"table {{.Names}}\\t{{.Status}}\\t{{.CreatedAt}}\" | grep -E \"NAMES|\$cname\" || true
            fi
          done

          for cid in \$(podman ps -a -q --filter volume=osss-consul_dat); do
            echo \"Removing container \$cid using volume…\"
            podman stop \"\$cid\" || true
            podman rm -f \"\$cid\"
          done

        "
        prompt_return
        ;;
      7)
        # Destroy trino'
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          SERVICE=\"trino\"
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          PROJECT_ELASTIC=\"osss-trino\"

          cd \"\$HOST_PROJ\" || { echo \"❌ Path not visible inside VM:\" \"\$HOST_PROJ\"; exit 1; }

          # Pick compose provider + correct remove-volumes flag
          COMPOSE=() ; DOWN_VOL_FLAG=\"\"
          if podman compose version >/dev/null 2>&1; then
            COMPOSE=(podman compose)
            DOWN_VOL_FLAG=\"--volumes\"
          elif command -v podman-compose >/dev/null 2>&1; then
            COMPOSE=(podman-compose)
            DOWN_VOL_FLAG=\"-v\"
          else
            echo \"❌ Neither podman compose nor podman-compose found.\"
            exit 1
          fi

          for cname in trino; do
            echo \"🗑️  Attempting to remove container '\$cname' (with volumes)…\"

            # First stop it if running
            if podman inspect \"\$cname\" --format '{{.State.Running}}' 2>/dev/null | grep -qi true; then
              echo \"⏹️  Container '\$cname' is running, stopping it first…\"
              if podman stop -t 15 \"\$cname\" >/dev/null 2>&1; then
                echo \"✅ Stopped container: \$cname\"
              else
                echo \"⚠️  Failed to stop container '\$cname' (continuing anyway)\"
              fi
            else
              echo \"ℹ️  Container '\$cname' is not running (or does not exist)\"
            fi

            # Then remove with volumes
            if podman rm -v \"\$cname\" >/dev/null 2>&1; then
              echo \"✅ Successfully removed container: \$cname (including anonymous volumes)\"
              continue
            else
              echo \"⚠️  Could not remove container '\$cname'.\"
              echo \"   - It may not exist, or it may still be running under a different name.\"
              echo \"   - Current container list (filtered for \$cname):\"
              podman ps -a --format \"table {{.Names}}\\t{{.Status}}\\t{{.CreatedAt}}\" | grep -E \"NAMES|\$cname\" || true
            fi
          done
        "
        prompt_return
        ;;
      8)
        # Destroy airflow'
        podman machine ssh default -- bash -lc  "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          SERVICE=\"trino\"
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          PROJECT_ELASTIC=\"osss-airflow\"

          cd \"\$HOST_PROJ\" || { echo \"❌ Path not visible inside VM:\" \"\$HOST_PROJ\"; exit 1; }

          # Pick compose provider + correct remove-volumes flag
          COMPOSE=() ; DOWN_VOL_FLAG=\"\"
          if podman compose version >/dev/null 2>&1; then
            COMPOSE=(podman compose)
            DOWN_VOL_FLAG=\"--volumes\"
          elif command -v podman-compose >/dev/null 2>&1; then
            COMPOSE=(podman-compose)
            DOWN_VOL_FLAG=\"-v\"
          else
            echo \"❌ Neither podman compose nor podman-compose found.\"
            exit 1
          fi

          for cname in airflow-webserver airflow-scheduler airflow-init postgres-airflow airflow-redis; do
            echo \"🗑️  Attempting to remove container '\$cname' (with volumes)…\"

            # First stop it if running
            if podman inspect \"\$cname\" --format '{{.State.Running}}' 2>/dev/null | grep -qi true; then
              echo \"⏹️  Container '\$cname' is running, stopping it first…\"
              if podman stop -t 15 \"\$cname\" >/dev/null 2>&1; then
                echo \"✅ Stopped container: \$cname\"
              else
                echo \"⚠️  Failed to stop container '\$cname' (continuing anyway)\"
              fi
            else
              echo \"ℹ️  Container '\$cname' is not running (or does not exist)\"
            fi

            # Then remove with volumes
            if podman rm -v \"\$cname\" >/dev/null 2>&1; then
              echo \"✅ Successfully removed container: \$cname (including anonymous volumes)\"
              continue
            else
              echo \"⚠️  Could not remove container '\$cname'.\"
              echo \"   - It may not exist, or it may still be running under a different name.\"
              echo \"   - Current container list (filtered for \$cname):\"
              podman ps -a --format \"table {{.Names}}\\t{{.Status}}\\t{{.CreatedAt}}\" | grep -E \"NAMES|\$cname\" || true
            fi
          done
        "
        prompt_return
        ;;
      9)
        # Destroy superset'
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          SERVICE=\"trino\"
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          PROJECT_ELASTIC=\"osss-superset\"

          cd \"\$HOST_PROJ\" || { echo \"❌ Path not visible inside VM:\" \"\$HOST_PROJ\"; exit 1; }

          # Pick compose provider + correct remove-volumes flag
          COMPOSE=() ; DOWN_VOL_FLAG=\"\"
          if podman compose version >/dev/null 2>&1; then
            COMPOSE=(podman compose)
            DOWN_VOL_FLAG=\"--volumes\"
          elif command -v podman-compose >/dev/null 2>&1; then
            COMPOSE=(podman-compose)
            DOWN_VOL_FLAG=\"-v\"
          else
            echo \"❌ Neither podman compose nor podman-compose found.\"
            exit 1
          fi

          for cname in superset superset-init superset_redis postgres-superset ; do
            echo \"🗑️  Attempting to remove container '\$cname' (with volumes)…\"

            # First stop it if running
            if podman inspect \"\$cname\" --format '{{.State.Running}}' 2>/dev/null | grep -qi true; then
              echo \"⏹️  Container '\$cname' is running, stopping it first…\"
              if podman stop -t 15 \"\$cname\" >/dev/null 2>&1; then
                echo \"✅ Stopped container: \$cname\"
              else
                echo \"⚠️  Failed to stop container '\$cname' (continuing anyway)\"
              fi
            else
              echo \"ℹ️  Container '\$cname' is not running (or does not exist)\"
            fi

            # Then remove with volumes
            if podman rm -v \"\$cname\" >/dev/null 2>&1; then
              echo \"✅ Successfully removed container: \$cname (including anonymous volumes)\"
              continue
            else
              echo \"⚠️  Could not remove container '\$cname'.\"
              echo \"   - It may not exist, or it may still be running under a different name.\"
              echo \"   - Current container list (filtered for \$cname):\"
              podman ps -a --format \"table {{.Names}}\\t{{.Status}}\\t{{.CreatedAt}}\" | grep -E \"NAMES|\$cname\" || true
            fi
          done
        "
        prompt_return
        ;;
      10)
        # Destroy openmetadata'
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          SERVICE=\"trino\"
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          PROJECT_ELASTIC=\"osss-openmetadata\"

          cd \"\$HOST_PROJ\" || { echo \"❌ Path not visible inside VM:\" \"\$HOST_PROJ\"; exit 1; }

          # Pick compose provider + correct remove-volumes flag
          COMPOSE=() ; DOWN_VOL_FLAG=\"\"
          if podman compose version >/dev/null 2>&1; then
            COMPOSE=(podman compose)
            DOWN_VOL_FLAG=\"--volumes\"
          elif command -v podman-compose >/dev/null 2>&1; then
            COMPOSE=(podman-compose)
            DOWN_VOL_FLAG=\"-v\"
          else
            echo \"❌ Neither podman compose nor podman-compose found.\"
            exit 1
          fi

          for cname in superset openmetadata-server mysql ; do
            echo \"🗑️  Attempting to remove container '\$cname' (with volumes)…\"

            # First stop it if running
            if podman inspect \"\$cname\" --format '{{.State.Running}}' 2>/dev/null | grep -qi true; then
              echo \"⏹️  Container '\$cname' is running, stopping it first…\"
              if podman stop -t 15 \"\$cname\" >/dev/null 2>&1; then
                echo \"✅ Stopped container: \$cname\"
              else
                echo \"⚠️  Failed to stop container '\$cname' (continuing anyway)\"
              fi
            else
              echo \"ℹ️  Container '\$cname' is not running (or does not exist)\"
            fi

            # Then remove with volumes
            if podman rm -v \"\$cname\" >/dev/null 2>&1; then
              echo \"✅ Successfully removed container: \$cname (including anonymous volumes)\"
              continue
            else
              echo \"⚠️  Could not remove container '\$cname'.\"
              echo \"   - It may not exist, or it may still be running under a different name.\"
              echo \"   - Current container list (filtered for \$cname):\"
              podman ps -a --format \"table {{.Names}}\\t{{.Status}}\\t{{.CreatedAt}}\" | grep -E \"NAMES|\$cname\" || true
            fi
          done
        "
        prompt_return
        ;;
      q|Q|b|B) return 0 ;;
      *) echo "Unknown choice: ${choice}" ;;
    esac
  done
}


utilities_menu() {
  while true; do
    echo
    echo "==============================================="
    echo " Utilities"
    echo "==============================================="
    echo " 1) Show Podman version inside the VM"
    echo " 2) Show Podman GraphRoot inside the VM"
    echo " 3) Install podman-compose inside the VM"
    echo " 4) Stop podman machine default"
    echo " 5) Remove podman machine default"
    echo " 6) Connect to default machine"
    echo "  q) Back"
    echo "-----------------------------------------------"
    read -rp "Select an option: " choice || return 0
    case "$choice" in
      1)
        # Pick an active VM if available, otherwise use 'default'
        local vm
        vm="$(podman machine active 2>/dev/null || echo default)"
        echo "▶️ Podman version in VM '${vm}':"
        podman machine ssh "$vm" -- bash -lc 'podman --version || podman version' || \
          echo "⚠️ Could not get Podman version inside VM '${vm}'."
        prompt_return
        ;;
      2)
        local vm
        vm="$(podman machine active 2>/dev/null || echo default)"
        echo "▶️ Podman version in VM '${vm}':"
        PODMAN_GRAPHROOT="$(
        podman machine ssh default -- podman info | awk -F': *' 'tolower($1) ~ /graphroot/ { print $2; exit }')" && echo "PODMAN_GRAPHROOT=$PODMAN_GRAPHROOT" || \
        echo "⚠️ Could not get Podman GraphRoot inside VM '${vm}'."
        prompt_return
        ;;
      3)
        local vm
        vm="$(podman machine active 2>/dev/null || echo default)"
        echo "▶️ Podman version in VM '${vm}':"
        podman machine ssh default -- sudo rpm-ostree install podman-compose
        podman machine stop default && podman machine start default
        prompt_return
        ;;
      4)
        podman machine stop default
        prompt_return
        ;;
      5)
        podman machine rm -f default
        prompt_return
        ;;
      6)
        podman system connection default default
        prompt_return
        ;;
      q|Q|b|B) return 0 ;;
      *) echo "Unknown choice: ${choice}" ;;
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
    echo " 7) Start profile 'trino' (keycloak must be up)"
    echo " 8) Start profile 'airflow' (keycloak must be up)"
    echo "9) Start profile 'superset' (keycloak must be up)"
    echo "10) Start profile 'openmetadata' (elastic+keycloak should be up)"
    echo "11) Down a profile (remove-orphans, volumes)"
    echo "12) Down ALL (remove-orphans, volumes)"
    echo "13) Show status"
    echo "14) Logs submenu"
    echo "15) Create Trino server certificate + keystore"
    echo "16) Create Keycloak server certificate"
    echo "17) Reset Podman machine (wipe & restart)"
    echo "18) Stop Podman VM"
    echo "19) Destroy Podman VM"
    echo "20) Run tests with Keycloak CA bundle"
    echo "21) Utilities"
    echo "22) Create Trino truststore"
    echo "  q) Quit"
    echo "-----------------------------------------------"
    read -rp "Select an option: " ans || exit 0
    case "${ans}" in
      1)
        # Deploy keycloak
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          cd \"\$HOST_PROJ\" || { echo '❌ Path not visible inside VM:' \"\$HOST_PROJ\"; exit 1; }
          # (optional) show which provider we’re using
          command -v podman-compose >/dev/null && podman-compose --version || true

          podman network exists osss-net >/dev/null 2>&1 || podman network create osss-net

          # run compose (use podman-compose explicitly to avoid provider lookup noise)
          COMPOSE_PROJECT_NAME=osss-keycloak podman-compose -f docker-compose.yml --profile keycloak up -d
        "
        ;;
      2)
        # Deploy app
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          cd \"\$HOST_PROJ\" || { echo '❌ Path not visible inside VM:' \"\$HOST_PROJ\"; exit 1; }
          # (optional) show which provider we’re using
          command -v podman-compose >/dev/null && podman-compose --version || true

          podman network exists osss-net >/dev/null 2>&1 || podman network create osss-net

          # run compose (use podman-compose explicitly to avoid provider lookup noise)
          COMPOSE_PROJECT_NAME=osss-app podman-compose -f docker-compose.yml --profile app up -d
        "
        ;;
      3)
        # Deploy webapp
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          cd \"\$HOST_PROJ\" || { echo '❌ Path not visible inside VM:' \"\$HOST_PROJ\"; exit 1; }
          # (optional) show which provider we’re using
          command -v podman-compose >/dev/null && podman-compose --version || true

          podman network exists osss-net >/dev/null 2>&1 || podman network create osss-net

          # run compose (use podman-compose explicitly to avoid provider lookup noise)
          COMPOSE_PROJECT_NAME=osss-web-app podman-compose -f docker-compose.yml --profile web-app up -d --no-deps --no-recreate
        "
        ;;
      4)
        # Deploy elastic
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=\$HOST_PROJ
          PODMAN_OVERLAY_DIR=\$PODMAN_OVERLAY_DIR

          echo \"🔧 [elastic-start] Entered elastic stack startup script\"
          echo \"   HOST_PROJ=\$HOST_PROJ\"
          echo \"   PODMAN_OVERLAY_DIR=\$PODMAN_OVERLAY_DIR\"
          echo

          # --- change dir ---
          if cd \"\$HOST_PROJ\"; then
            echo \"📂 Changed directory to: \$HOST_PROJ\"
          else
            echo \"❌ Path not visible inside VM: \$HOST_PROJ\"
            exit 1
          fi

          # --- Base stack ---
          echo
          echo \"🚀 [elastic-start] Starting base stack (elasticsearch + kibana + kibana-pass-init + api-key-init)\"
          echo \"    Using compose file: \$HOST_PROJ/docker-compose.yml\"
          COMPOSE_PROJECT_NAME=osss-elastic podman compose -f \"\$HOST_PROJ/docker-compose.yml\" --profile elastic up -d \\
            --force-recreate --remove-orphans \\
            elasticsearch kibana kibana-pass-init api-key-init
          echo \"✅ Base stack containers launched\"

          # --- Setup job ---
          echo
          echo \"🛠️  [elastic-start] Running setup job: filebeat-setup\"
          COMPOSE_PROJECT_NAME=osss-elastic podman compose -f \"\$HOST_PROJ/docker-compose.yml\" --profile elastic up -d \\
            --no-deps --no-recreate filebeat-setup

          echo \"📜 Logs (last 2m) for filebeat-setup:\"
          if ! podman logs --since 2m filebeat-setup; then
            echo \"⚠️  No recent logs found for filebeat-setup (container may have exited too fast)\"
          else
            echo \"✅ filebeat-setup logs captured\"
          fi

          # --- Running filebeat ---
          echo
          echo \"📡 [elastic-start] Starting filebeat (no deps, no recreate)\"
          COMPOSE_PROJECT_NAME=osss-elastic podman compose -f \"\$HOST_PROJ/docker-compose.yml\" --profile elastic up -d \\
            --no-deps --no-recreate filebeat
          echo \"✅ filebeat launched\"

          # --- show running containers ---
          echo
          echo \"== 📋 Running containers (name | status | ports) ==\"
          if ! podman ps --format \"table {{.Names}}\\t{{.Status}}\\t{{.Ports}}\"; then
            echo \"❌ Failed to list containers\"
          fi
          echo \"== End of container list ==\"
        " || true
        prompt_return
        ;;
      5)
        # Deploy vault
        # Ask on host whether to rebuild the setup images
        REBUILD_FLAG=0
        if [ -t 0 ]; then
          read -r -p "🔧 Rebuild images for 'vault-oidc-setup' and 'vault-seed' before running? [y/N] " ans || true
          [[ ${ans:-} =~ ^[Yy]$ ]] && REBUILD_FLAG=1
        fi

        podman machine ssh default -- bash -lc "
        set -euo pipefail
        HOST_PROJ=$HOST_PROJ
        PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
        cd \"\$HOST_PROJ\" || { echo '❌ Path not visible inside VM:' \"\$HOST_PROJ\"; exit 1; }
        # (optional) show which provider we’re using
        command -v podman-compose >/dev/null && podman-compose --version || true

        # Optional image rebuild for setup jobs (guarded by service presence)
        if [ \"$REBUILD_FLAG\" = 1 ]; then
          have_oidc=\$(podman-compose -f docker-compose.yml config --services | grep -qx 'vault-oidc-setup' && echo 1 || echo 0)
          have_seed=\$(podman-compose -f docker-compose.yml config --services | grep -qx 'vault-seed' && echo 1 || echo 0)
          if [ \$have_oidc -eq 0 ] && [ \$have_seed -eq 0 ]; then
            echo '⚠️  Compose file has no services named vault-oidc-setup or vault-seed here; skipping build.'
          else
            echo '▶️  Building images: vault-oidc-setup vault-seed'
            podman-compose -f docker-compose.yml build \
              \$( [ \$have_oidc -eq 1 ] && echo vault-oidc-setup ) \
              \$( [ \$have_seed -eq 1 ] && echo vault-seed ) || true
          fi
        fi

        # run compose (use podman-compose explicitly to avoid provider lookup noise)
        COMPOSE_PROJECT_NAME=osss-vault podman-compose -f docker-compose.yml --profile vault up -d --no-deps --no-recreate vault

        # Wait for Vault container health=healthy
        echo \"[wait] Vault (container=vault) healthcheck...\"
        i=0
        while :; do
          # if inspect fails, treat as not ready
          status=\"\$(podman inspect -f '{{.State.Health.Status}}' vault 2>/dev/null || echo \\\"unknown\\\")\"
          running=\"\$(podman inspect -f '{{.State.Running}}' vault 2>/dev/null || echo \\\"false\\\")\"

          if [ \"\$running\" != \"true\" ]; then
            echo \"❌ vault container is not running\"; podman ps -a --filter name='^vault$' --format 'table {{.ID}}\\t{{.Names}}\\t{{.Status}}'; exit 1
          fi

          if [ \"\$status\" = \"healthy\" ]; then
            echo \"[ok] Vault is healthy\"
            break
          fi

          i=\$((i+1))
          [ \"\$i\" -le 180 ] || { echo \"❌ timed out waiting for Vault health (last=\$status)\"; podman logs --tail 200 vault || true; exit 1; }
          sleep 2
        done

        COMPOSE_PROJECT_NAME=osss-vault podman-compose -f docker-compose.yml --profile vault up -d --no-deps --no-recreate vault-oidc-setup
        COMPOSE_PROJECT_NAME=osss-vault podman-compose -f docker-compose.yml --profile vault up -d --no-deps --no-recreate vault-seed
        "

        ;;
      6)
        # Deploy consul
        podman machine ssh default -- bash -lc '
        set -e
        cd '"$(printf %q "$HOST_PROJ")"'
        # (optional) show which provider we’re using
        command -v podman-compose >/dev/null && podman-compose --version || true
        # run compose (use podman-compose explicitly to avoid provider lookup noise)
        COMPOSE_PROJECT_NAME=osss-consul podman-compose -f docker-compose.yml --profile consul up -d --no-deps --no-recreate consul
        '
        ;;
      7)
        # Deploy trino

        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR

          cd \"\$HOST_PROJ\" || { echo '❌ Path not visible inside VM:' \"\$HOST_PROJ\"; exit 1; }
          # (optional) show which provider we’re using
          command -v podman-compose >/dev/null && podman-compose --version || true



          echo \"# run compose (use podman-compose explicitly to avoid provider lookup noise)\"
          COMPOSE_PROJECT_NAME=osss-trino podman-compose -f docker-compose.yml --profile trino up -d --no-deps trino
        "
        ;;
      8)
        # Deploy airflow
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          cd \"\$HOST_PROJ\" || { echo '❌ Path not visible inside VM:' \"\$HOST_PROJ\"; exit 1; }
          # (optional) show which provider we’re using
          command -v podman-compose >/dev/null && podman-compose --version || true

          podman network exists osss-net >/dev/null 2>&1 || podman network create osss-net

          # run compose (use podman-compose explicitly to avoid provider lookup noise)
          COMPOSE_PROJECT_NAME=osss-airflow podman-compose -f docker-compose.yml --profile airflow up -d
        "
        ;;
      9)
        # Deploy superset
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          cd \"\$HOST_PROJ\" || { echo '❌ Path not visible inside VM:' \"\$HOST_PROJ\"; exit 1; }
          # (optional) show which provider we’re using
          command -v podman-compose >/dev/null && podman-compose --version || true

          podman network exists osss-net >/dev/null 2>&1 || podman network create osss-net

          # run compose (use podman-compose explicitly to avoid provider lookup noise)
          COMPOSE_PROJECT_NAME=osss-superset COMPOSE_PROFILES=superset podman-compose -f docker-compose.yml config --services
          COMPOSE_PROJECT_NAME=osss-superset podman-compose -f docker-compose.yml --profile superset up --build superset-build --force-recreate
          COMPOSE_PROJECT_NAME=osss-superset podman-compose -f docker-compose.yml --profile superset up -d postgres-superset --no-deps
          COMPOSE_PROJECT_NAME=osss-superset podman-compose -f docker-compose.yml --profile superset up -d superset_redis --no-deps

          COMPOSE_PROJECT_NAME=osss-superset podman-compose -f docker-compose.yml --profile superset up superset-init --force-recreate --no-deps
          COMPOSE_PROJECT_NAME=osss-superset podman-compose -f docker-compose.yml --profile superset up -d superset --force-recreate --no-deps
        "
        ;;
      10)
        # Deploy openmetadata
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          HOST_PROJ=$HOST_PROJ
          PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
          cd \"\$HOST_PROJ\" || { echo '❌ Path not visible inside VM:' \"\$HOST_PROJ\"; exit 1; }
          # (optional) show which provider we’re using
          command -v podman-compose >/dev/null && podman-compose --version || true

          podman network exists osss-net >/dev/null 2>&1 || podman network create osss-net

          # run compose (use podman-compose explicitly to avoid provider lookup noise)
          COMPOSE_PROJECT_NAME=osss-openmetadata podman-compose -f docker-compose.yml --profile openmetadata up -d
        "
        ;;
      11) down_profiles_menu ;;
      12) down_all ;;
      13) show_status; prompt_return ;;
      14) logs_menu ;;
      15) create_trino_cert ;;
      16) create_keycloak_cert ;;
      17) reset_podman_machine ;;
      18) podman_vm_stop ;;
      19) podman_vm_destroy ;;
      20)
        echo "▶️ Running pytest with OSSS Keycloak CA bundle..."
        export REQUESTS_CA_BUNDLE="$(pwd)/config_files/keycloak/secrets/ca/ca.crt"
        export OSSS_CA_BUNDLE="$REQUESTS_CA_BUNDLE"

        export OSSS_TEST_CA_BUNDLE=config_files/keycloak/secrets/keycloak/server.crt
        export REQUESTS_CA_BUNDLE=config_files/keycloak/secrets/keycloak/server.crt

        # make sure nothing forces container-only hostnames or HTTP defaults
        unset KEYCLOAK_BASE_URL

        # Run pytest but don't fail the script if tests fail
        PYTEST_RC=0
        pytest -q || PYTEST_RC=$?

        if [ "$PYTEST_RC" -ne 0 ]; then
          echo "⚠️  pytest failed (exit $PYTEST_RC), continuing…"
        fi
        prompt_return
        ;;
      21) utilities_menu ;;
      22)
        echo "🛠️  Building Trino truststore..."
        build_trino_truststore
        prompt_return
        ;;

      q|Q) echo "Bye!"; exit 0 ;;
      *)   echo "Unknown choice: ${ans}"; prompt_return ;;
    esac
  done
}

menu






