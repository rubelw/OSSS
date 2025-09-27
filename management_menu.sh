#!/usr/bin/env bash
# management_menu.sh (Podman-only)
# - Uses Podman + Podman Compose exclusively
# - Adds 127.0.0.1 keycloak.local to /etc/hosts if missing
# - Has helpers to start profiles and view logs
# - Runs build_realm.py after Keycloak is up

set -Eeuo pipefail

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


# --- External networks create-only helper (called by start_* funcs) ---
ensure_external_networks_exist() {
  # Ensure external networks referenced by compose exist.
  # For now we only create 'osss-net' if missing (create-only; no deletes).
  if ! podman network exists osss-net 2>/dev/null; then
    echo "➕ Creating external network: osss-net"
    podman network create osss-net >/dev/null || echo "⚠️  Could not create osss-net (continuing)"
  fi
}


# -------- Podman install/start checks --------
ensure_podman_installed() {
  # If podman isn't installed, nothing to do here.
  if ! command -v podman >/dev/null 2>&1; then
    return 0
  fi

  # If Podman is already responding, we're good.
  if podman info --debug >/dev/null 2>&1; then
    return 0
  fi

  echo "⚠️  Podman not reachable; attempting to (init|start) podman machine…"

  local NAME="${PODMAN_MACHINE_NAME:-default}"
  local CPUS="${PODMAN_MACHINE_CPUS:-12}"
  local MEM_MB="${PODMAN_MACHINE_MEM_MB:-40960}"
  local DISK_GB="${PODMAN_MACHINE_DISK_GB:-100}"

  # On macOS/Windows, podman uses a VM ("podman machine").
  if podman machine list >/dev/null 2>&1; then
    # If the machine doesn't exist, init it; otherwise start it.
    if ! podman machine inspect "$NAME" >/dev/null 2>&1; then
      echo "+ podman machine init --cpus $CPUS --memory $MEM_MB --disk-size $DISK_GB $NAME"
      podman machine init --cpus "$CPUS" --memory "$MEM_MB" --disk-size "$DISK_GB" "$NAME"
    fi
    echo "+ podman machine start $NAME"
    podman machine start "$NAME"
  fi

  # One more try after starting
  if podman info --debug >/dev/null 2>&1; then
    echo "✅ Podman is up."
    return 0
  fi

  echo "❌ Podman still unreachable. Try: 'podman system connection list' or restart Podman Desktop."
  return 1
}

# Ensures Podman is ready. On macOS/Windows, ensures a Podman machine exists and is running.
# On Linux, Podman is daemonless; we just verify `podman info`. If the user session has
# systemd, we try starting the user socket as a convenience.
ensure_podman_started() {
  # Already healthy?
  if podman info >/dev/null 2>&1; then
    return 0
  fi

  # --- If there are existing connections, let user choose one ---
  local has_connections=0
  local -a CONN_NAMES=()
  local -a CONN_URIS=()
  local -a CONN_DEFAULT=()

  if podman system connection list >/dev/null 2>&1; then
    has_connections=1
    # Collect connections (name, default flag, uri)
    # Format: "{{.Name}}\t{{.Default}}\t{{.URI}}"
    while IFS=$'\t' read -r cname cdef curi; do
      [[ -z "$cname" ]] && continue
      CONN_NAMES+=("$cname")
      CONN_DEFAULT+=("$cdef")
      CONN_URIS+=("$curi")
    done < <(podman system connection list --format '{{.Name}}\t{{.Default}}\t{{.URI}}' 2>/dev/null || true)

    if ((${#CONN_NAMES[@]} > 0)); then
      local sel=""
      if [[ -t 0 ]]; then
        echo "🔌 Available Podman connections:"
        local i
        for ((i=0; i<${#CONN_NAMES[@]}; i++)); do
          local mark=""
          [[ "${CONN_DEFAULT[$i]}" == "true" ]] && mark=" (default)"
          printf "  %2d) %s%s\n      ↳ %s\n" "$((i+1))" "${CONN_NAMES[$i]}" "$mark" "${CONN_URIS[$i]}"
        done
        echo "  q) Cancel selection (keep current)"
        read -r -p "Select a connection by number (Enter to keep current): " sel || true
      fi

      # Non-TTY or empty input → keep current default if any
      if [[ -z "${sel:-}" ]]; then
        : # do nothing; keep current default
      elif [[ "$sel" =~ ^[Qq]$ ]]; then
        : # do nothing; keep current default
      elif [[ "$sel" =~ ^[0-9]+$ ]] && (( sel>=1 && sel<=${#CONN_NAMES[@]} )); then
        local chosen="${CONN_NAMES[$((sel-1))]}"
        echo "✅ Setting default connection: ${chosen}"
        podman system connection default "$chosen" >/dev/null 2>&1 || true
      else
        echo "⚠️  Invalid selection. Keeping current default."
      fi
    fi
  fi

  # Try again after potential default switch
  if podman info >/dev/null 2>&1; then
    return 0
  fi

  # --- macOS/Windows: ensure a machine is running for the chosen/default connection ---
  if podman machine -h >/dev/null 2>&1; then
    # Infer which machine to start from the default connection, if any
    local def_name=""
    def_name="$(podman system connection list --format '{{if .Default}}{{.Name}}{{end}}' 2>/dev/null | awk 'NF' | head -n1 || true)"

    # Heuristic: connection names commonly equal machine name or end with "-root"
    local mname=""
    if [[ -n "$def_name" ]]; then
      mname="${def_name%-root}"
    else
      # Fall back to first machine name if no default conn
      mname="$(podman machine ls --format '{{.Name}}' 2>/dev/null | head -n1 || true)"
    fi

    # If no machines exist, create one
    if ! podman machine ls --format '{{.Name}}' 2>/dev/null | awk 'NF' | grep -q .; then
      echo "🖥️  No Podman machine found. Initializing a default machine…"
      if ! podman machine init --now 2>/dev/null; then
        podman machine init || true
        podman machine start || true
      fi
    else
      # Ensure the inferred/first machine is running
      if [[ -z "$mname" ]]; then
        mname="$(podman machine ls --format '{{.Name}}' | head -n1)"
      fi
      # Start if not running
      if ! podman machine ls --format '{{.Name}} {{.Running}}' | awk -v n="$mname" '$1==n && $2=="true"{f=1} END{exit !f}'; then
        echo "▶️  Starting Podman machine '${mname}'…"
        podman machine start "$mname" || true
      fi
    fi

    # After machine start, ensure we have a sensible default connection
    if ! podman info >/dev/null 2>&1; then
      # Prefer a conn matching the machine name (rootless first)
      local cand=""
      cand="$(podman system connection list --format '{{.Name}}' | awk -v n="$mname" '$0==n{print; exit}')" || true
      if [[ -z "$cand" ]]; then
        cand="$(podman system connection list --format '{{.Name}}' | awk -v n="$mname-root" '$0==n{print; exit}')" || true
      fi
      if [[ -n "$cand" ]]; then
        echo "✅ Setting default connection: ${cand}"
        podman system connection default "$cand" >/dev/null 2>&1 || true
      fi
    fi

    # Re-check health
    if podman info >/dev/null 2>&1; then
      return 0
    fi
  fi

  # --- Linux/systemd convenience: try user socket (ignore failures) ---
  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user start podman.socket >/dev/null 2>&1 || true
  fi

  # Final health check
  if ! podman info >/dev/null 2>&1; then
    echo "⚠️  Podman is installed but not ready (cannot connect)."
    echo "   • macOS/Windows: try 'podman machine start' or pick a valid connection:"
    echo "       podman system connection list"
    echo "       podman system connection default <NAME>"
    echo "   • Linux: verify your user can run Podman; user socket may help:"
    echo "       systemctl --user start podman.socket"
    podman system connection list 2>/dev/null || true
    if [[ -t 0 ]]; then
      read -rp "Press Enter to continue anyway, or type 'exit' to quit: " ans || true
      [[ "${ans:-}" == "exit" ]] && exit 1
    fi
  fi
}


# --- Podman preflight (idempotent) ---
podman_ready_once() {
  # Only run once per process
  [[ "${__OSSS_PODMAN_READY:-}" == "1" ]] && return 0
  command -v podman >/dev/null 2>&1 || { __OSSS_PODMAN_READY=1; export __OSSS_PODMAN_READY; return 0; }

  # Fast path: if the VM is already running, don't touch it
  if podman machine -h >/dev/null 2>&1; then
    local NAME="${PODMAN_MACHINE_NAME:-default}"
    if podman machine ls --format '{{.Name}} {{.Running}}' \
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
  if podman machine -h >/dev/null 2>&1; then
    if ! podman machine inspect "$NAME" >/dev/null 2>&1; then
      podman machine init \
        --cpus  "${PODMAN_MACHINE_CPUS:-6}" \
        --memory "${PODMAN_MACHINE_MEM_MB:-8192}" \
        --disk-size "${PODMAN_MACHINE_DISK_GB:-50}" \
        "$NAME"
    fi
    podman machine start "$NAME"

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

# --- Require Podman to be reachable (macOS: init/start VM, fix default connection) ---
podman_require_ready_or_die() {
  # If podman not installed, nothing to enforce here.
  command -v podman >/dev/null 2>&1 || return 0

  # Already healthy?
  if podman info --debug >/dev/null 2>&1; then
    return 0
  fi

  local NAME="${PODMAN_MACHINE_NAME:-default}"
  local CPUS="${PODMAN_MACHINE_CPUS:-6}"
  local MEM_MB="${PODMAN_MACHINE_MEM_MB:-8192}"
  local DISK_GB="${PODMAN_MACHINE_DISK_GB:-50}"

  # On macOS/Windows, ensure a VM exists and is running
  if podman machine -h >/dev/null 2>&1; then
    if ! podman machine inspect "$NAME" >/dev/null 2>&1; then
      echo "+ podman machine init --cpus $CPUS --memory $MEM_MB --disk-size $DISK_GB $NAME"
      podman machine init --cpus "$CPUS" --memory "$MEM_MB" --disk-size "$DISK_GB" "$NAME"
    fi
    echo "+ podman machine start $NAME"
    podman machine start "$NAME" >/dev/null 2>&1 || true

    # Make the connection that matches this machine the default (rootless preferred)
    if podman system connection list --format '{{.Name}}' | grep -qx "$NAME"; then
      podman system connection default "$NAME" >/dev/null 2>&1 || true
    elif podman system connection list --format '{{.Name}}' | grep -qx "${NAME}-root"; then
      podman system connection default "${NAME}-root" >/dev/null 2>&1 || true
    fi
  fi

  # Wait for port forward / service to come up
  for i in {1..30}; do
    if podman info --debug >/dev/null 2>&1; then return 0; fi
    sleep 1
  done

  echo "❌ Podman connection is not ready (default connection likely stale).
     Try:  podman system connection list
           podman system connection default <VALID_NAME>" >&2
  exit 1
}


# Extra services to remove when downing a given profile (Bash 3–friendly).
# Extend this case list as needed.
cascade_services_for_profile() {
  case "$1" in
    airflow)
      # OpenMetadata's MySQL that you want removed with Airflow
      echo "mysql"
      ;;
    # Add more cascades here if you like, e.g.:
    # openmetadata) echo "mysql elasticsearch" ;;
  esac
}

# Parse docker-compose.yml and list services that include a given profile, without needing compose on the host.
# Usage: services_for_profile_from_yaml "elastic"
services_for_profile_from_yaml() {
  local prof="$1" file="${COMPOSE_FILE:-docker-compose.yml}"
  awk -v prof="$prof" '
    BEGIN{in_services=0; svc=""; in_prof=0}
    /^[[:space:]]*services[[:space:]]*:/ {in_services=1; next}
    in_services {
      # end of services block if dedented to column 0
      if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) {in_services=0; next}
      # service header at 2 spaces indentation: "  name:"
      if ($0 ~ /^[[:space:]]{2}[A-Za-z0-9._-]+:[[:space:]]*$/) {
        line=$0; sub(/^[[:space:]]+/, "", line); sub(/:.*/, "", line)
        svc=line; in_prof=0; next
      }
      # inline list: profiles: [ "elastic", "foo" ]
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*\[/) {
        s=$0; sub(/^[^[]*\[/, "", s); sub(/\].*$/, "", s)
        gsub(/[[:space:]"\047]/, "", s)
        n=split(s, arr, ",")
        for (i=1;i<=n;i++) if (arr[i]==prof) { print svc; break }
        next
      }
      # block list start: profiles:
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*$/) { in_prof=1; next }
      # list item lines:       - elastic
      if (in_prof && $0 ~ /^[[:space:]]{6}-[[:space:]]*[^[:space:]]+/) {
        p=$0; sub(/^[^ -]*-/, "", p); gsub(/^[[:space:]]+|[[:space:]]+$/, "", p)
        if (p==prof) print svc; next
      }
      # next service / end of profiles block
      if (in_prof && $0 ~ /^[[:space:]]{4}[A-Za-z0-9._-]+:/) { in_prof=0 }
    }
  ' "$file" | sort -u
}


# -------- Podman compose selection --------
compose_cmd() {
  # Prefer podman compose; fall back to podman-compose or docker compose.
  if command -v podman >/dev/null 2>&1 && podman --help | grep -qE '\bcompose\b'; then
    echo "podman compose"
  elif command -v podman-compose >/dev/null 2>&1; then
    echo "podman-compose"
  else
    echo "❌ Neither podman-compose nor podman compose was found." >&2
    return 127
  fi
}

__compose_cmd() {
  if command -v podman >/dev/null 2>&1 && podman --help | grep -qE '\bcompose\b'; then
    echo "podman compose"
  elif command -v podman-compose >/dev/null 2>&1; then
    echo "podman-compose"
  else
    echo "❌ Neither podman-compose nor podman compose found." >&2
    return 127
  fi
}

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
show_status(){
  # Derive the project exactly as compose will
  local PROJECT; PROJECT="$(__compose_project_name)"

  # Show connection/debug info
  local CONN; CONN="$(podman system connection list --format '{{if .Default}}{{.Name}}{{end}}' 2>/dev/null | awk 'NF' || true)"
  echo "▶️  Containers (project ${PROJECT})  [conn: ${CONN:-unknown}]"
  printf "NAMES\tSTATUS\tNETWORKS\n"

  # Match by labels (authoritative), covering both podman-compose and docker compose labels
  {
    podman ps -a \
      --filter "label=io.podman.compose.project=${PROJECT}" \
      --format '{{.Names}}\t{{.Status}}\t{{.Networks}}' 2>/dev/null
    podman ps -a \
      --filter "label=com.docker.compose.project=${PROJECT}" \
      --format '{{.Names}}\t{{.Status}}\t{{.Networks}}' 2>/dev/null
  } | awk 'NF' || true

  echo
  echo "▶️  Networks containing '${PROJECT}_':"
  podman network ls | (head -n1; grep -E " ${PROJECT}_" || true)

  # Fallback hint: if nothing matched, show a quick glance at everything
  if ! podman ps -a --filter "label=io.podman.compose.project=${PROJECT}" -q | awk 'NF' \
     && ! podman ps -a --filter "label=com.docker.compose.project=${PROJECT}" -q | awk 'NF'; then
    echo
    echo "ℹ️  No containers found for project='${PROJECT}'. Showing all containers for reference:"
    podman ps -a --format '{{.Names}}\t{{.Status}}\t{{.Networks}}' | sed 's/^/  /' || true
  fi
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
  echo "[prompt_return] Function invoked"
  # don’t die if stdin isn’t a tty; just sleep briefly so users see output
  if [[ -t 0 ]]; then
    echo "[prompt_return] stdin is a TTY → waiting for user input"
    read -r -p "✅ Done. Press Enter to return to the menu..." _
    echo "[prompt_return] User pressed Enter → returning to menu"
  else
    echo "[prompt_return] stdin is NOT a TTY → skipping interactive prompt"
    echo "✅ Done. Returning to menu…"
    echo "[prompt_return] Sleeping briefly so user can see output"
    sleep 1
  fi
  echo "[prompt_return] Completed"
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

# -------- profile helpers --------
start_profiles_blind() {
  local args=( -f "$COMPOSE_FILE" )
  echo "[start_profiles_blind] Invoked with profiles: $*"
  echo "▶️  Starting services for profiles: $* …"
  echo "[start_profiles_blind] Using compose file: $COMPOSE_FILE"

  if compose_supports_profile; then
    echo "[start_profiles_blind] Backend supports profiles"
    for p in "$@"; do
      echo "[start_profiles_blind] Preparing profile: $p"
      maybe_build_profile "$p"
      echo "[start_profiles_blind] Adding profile '$p' to compose args"
      args+=( --profile "$p" )
    done
    echo "[start_profiles_blind] Final compose command: $COMPOSE ${args[*]} up -d"
    run $COMPOSE "${args[@]}" up -d
    echo "[start_profiles_blind] Compose up complete (with profile support)"
  else
    echo "[start_profiles_blind] Backend does NOT support profiles → falling back to manual service resolution"
    local all_svcs=()
    for p in "$@"; do
      echo "[start_profiles_blind] Resolving services for profile: $p"
      maybe_build_profile "$p"
      while read -r s; do
        if [[ -n "$s" ]]; then
          echo "[start_profiles_blind] Found service '$s' for profile '$p'"
          all_svcs+=("$s")
        fi
      done < <(compose_services_for_profile "$p")
    done

    echo "[start_profiles_blind] Deduplicating resolved services..."
    mapfile -t all_svcs < <(printf '%s\n' "${all_svcs[@]}" | awk 'NF && !seen[$0]++')

    if ((${#all_svcs[@]}==0)); then
      echo "⚠️  No services resolved for given profiles: $*"
    else
      echo "⚠️  Backend lacks profile support; starting services only: ${all_svcs[*]}"
      echo "[start_profiles_blind] Running compose_up_services with: ${all_svcs[*]}"
      compose_up_services "${all_svcs[@]}"
      echo "[start_profiles_blind] Compose up complete (manual fallback)"
    fi
  fi

  echo "[start_profiles_blind] Finished execution"
}



start_profile_with_build_prompt() {
  local prof="$1"
  echo "[start_profile_with_build_prompt] Invoked with profile: '$prof'"

  echo "[start_profile_with_build_prompt] Ensuring hosts entry for keycloak..."
  ensure_hosts_keycloak
  echo "[start_profile_with_build_prompt] Done ensuring hosts"

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

  echo "[start_keycloak_services] Ensuring hosts entry for keycloak..."
  ensure_hosts_keycloak
  echo "[start_keycloak_services] Done ensuring hosts"

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
  ensure_external_networks_exist
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
vm_compose_in_dir() {
  local host_dir="$1"; shift
  local q_dir; q_dir="$(printf %q "$host_dir")"
  local q_args=""; while (($#)); do q_args+=$(printf " %q" "$1"); shift; done

  # Remote script: ensure a working compose provider (prefer docker-compose plugin),
  # then exec with the ARGS we passed.
  local remote='
set -Eeuo pipefail
cd '"$q_dir"'

have_podman_compose() { podman compose version >/dev/null 2>&1; }
install_compose_plugin() {
  # Install docker-compose v2 plugin into ~/.docker/cli-plugins/docker-compose
  # Pick arch automatically; allow override via COMPOSE_PLUGIN_VERSION env.
  local ver="${COMPOSE_PLUGIN_VERSION:-v2.29.7}"
  local arch="$(uname -m)"
  case "$arch" in
    x86_64|amd64) arch="x86_64" ;;
    aarch64|arm64) arch="aarch64" ;;
    *) echo "❌ Unsupported arch: $arch"; return 1 ;;
  esac
  local url="https://github.com/docker/compose/releases/download/${ver}/docker-compose-linux-${arch}"
  local dst="$HOME/.docker/cli-plugins/docker-compose"
  mkdir -p "$(dirname "$dst")"
  echo "⬇️  Installing docker-compose plugin ${ver} for ${arch} -> $dst"
  curl -fsSL "$url" -o "$dst"
  chmod +x "$dst"
}

install_podman_compose_py() {
  # Last resort: get pip, then podman-compose (Python)
  echo "ℹ️  Installing podman-compose via pip (user)…"
  if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "ℹ️  Bootstrapping pip (user)…"
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    python3 /tmp/get-pip.py --user
    export PATH="$HOME/.local/bin:$PATH"
  fi
  python3 -m pip install --user --upgrade podman-compose
  export PATH="$HOME/.local/bin:$PATH"
}

PROVIDER=""
if have_podman_compose; then
  PROVIDER="podman compose"
else
  # Try installing the compose v2 plugin first (no root required)
  if install_compose_plugin && have_podman_compose; then
    PROVIDER="podman compose"
  else
    # Fallback to python podman-compose (needs pip)
    if command -v podman-compose >/dev/null 2>&1; then
      PROVIDER="podman-compose"
    else
      install_podman_compose_py
      PROVIDER="podman-compose"
    fi
  fi
fi

echo "ℹ️  Compose provider in VM: $PROVIDER"
exec $PROVIDER '"${q_args# }"'
'
  echo "+ podman machine ssh -- bash -lc \"$remote\""
  podman machine ssh -- bash -lc "$remote"
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
  ensure_hosts_keycloak
  echo "[start_profile_elastic] Hosts entry ensured"

  # Ensure external networks exist (create-only)
  ensure_external_networks_exist

  # Start elastic stack in one shot
  up_profile_with_podman elastic || { echo "❌ compose up failed (elastic)"; prompt_return; return 1; }
  prompt_return
}



start_profile_app()          { start_profile_with_build_prompt app; }
start_profile_web_app()      { start_profile_with_build_prompt web-app; }
start_profile_vault()        { start_profile_with_build_prompt vault; }

start_profile_trino() {
  ensure_hosts_keycloak
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

  # Targeted cleanup: remove only containers/pods for these services (by label)
  local s ids pods
  for s in "${SVCS[@]}"; do
    ids="$(podman ps -a --filter "label=io.podman.compose.project=${PROJECT}" \
                      --filter "label=io.podman.compose.service=${s}" -q 2>/dev/null || true)"
    if [[ -n "$ids" ]]; then
      pods="$(podman inspect -f '{{.PodName}}' $ids 2>/dev/null | awk 'NF && $0!="<no value>" && !seen[$0]++' || true)"
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

    # phase 1: core
    "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps shared-vol-init elasticsearch
    _wait_health "elasticsearch" 180

    # phase 2: init + kibana
    "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps kibana-pass-init
    _wait_exit0 "kibana-pass-init" 180
    "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps kibana

    # phase 3: api key init
    if "${CMDA[@]}" -f "$FILE" --profile elastic config --services 2>/dev/null | grep -qx 'api-key-init'; then
      "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps api-key-init
      _wait_exit0 "api-key-init" 180
    fi

    # phase 4: filebeat (optional)
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
  podman machine ssh -- bash -lc "
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
compose_stop_rm_profile() {
  local prof="$1"
  local CMD; CMD="$(__compose_cmd)" || return $?

  # Which services are in this profile?
  mapfile -t SVCS < <($CMD -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF')
  ((${#SVCS[@]})) || { echo "No services found for profile '$prof'."; return 0; }

  echo "+ $CMD -f \"$COMPOSE_FILE\" stop ${SVCS[*]}"

  # --- remove containers belonging to this profile ---
  # Split "__compose_cmd" into array so we can detect "podman compose" vs "podman-compose"
  local -a CMDA
  IFS=' ' read -r -a CMDA <<< "$CMD"

  # Try a native "rm" if available (docker compose / podman compose)
  if $CMD rm -h >/dev/null 2>&1; then
    echo "+ $CMD -f \"$COMPOSE_FILE\" --profile \"$prof\" rm -s -f -v ${SVCS[*]}"
    $CMD -f "$COMPOSE_FILE" --profile "$prof" rm -s -f -v "${SVCS[@]}" || true

  # Fallback for podman-compose (no 'rm' subcommand): remove by labels
  else
    echo "ℹ️  Using label-based cleanup (podman-compose has no 'rm')"
    # Determine correct label keys for engine
    local project_label service_label
    if [[ "${CMDA[0]}" == "podman" && "${CMDA[1]:-}" == "compose" ]]; then
      project_label="io.podman.compose.project"
      service_label="io.podman.compose.service"
    else
      # When $CMD actually invokes 'podman-compose'
      project_label="io.podman.compose.project"
      service_label="io.podman.compose.service"
    fi

    # Remove containers service-by-service using labels
    for s in "${SVCS[@]}"; do
      ids="$(podman ps -a \
        --filter "label=${project_label}=${COMPOSE_PROJECT_NAME}" \
        --filter "label=${service_label}=${s}" \
        -q 2>/dev/null || true)"
      [[ -n "$ids" ]] && podman rm -f -v $ids >/dev/null 2>&1 || true
    done
  fi
}


# --- Override: start_keycloak_services (ensure network first) ---
ensure_osss_net() {
  # If COMPOSE_FILE declares osss-net as external, make sure it's present.
  # We only create if missing; we never modify or remove existing networks.
  if ! podman network exists osss-net 2>/dev/null; then
    echo "➕ Creating external network: osss-net"
    podman network create osss-net >/dev/null || echo "⚠️  Could not create osss-net (continuing)"
  fi
}
start_keycloak_services() {
  echo "[start_keycloak_services] Invoked"

  echo "[start_keycloak_services] Ensuring hosts entry for keycloak..."
  ensure_hosts_keycloak
  echo "[start_keycloak_services] Hosts entry ensured"

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

  echo "[start_keycloak_services] Ensuring external 'osss-net' exists (create-only)..."
  ensure_osss_net
  echo "[start_keycloak_services] 'osss-net' checked/created"

  # Query services under the profile (or fallback to service names)
  local svcs=()
  if compose_supports_profile; then
    echo "[start_keycloak_services] Backend supports profiles, querying profile 'keycloak'..."
    mapfile -t svcs < <($CMD -f "$COMPOSE_FILE" --profile "keycloak" config --services 2>/dev/null | awk 'NF')
    echo "[start_keycloak_services] Found ${#svcs[@]} service(s) from CLI: ${svcs[*]:-<none>}"

    if [ "${#svcs[@]}" -eq 0 ]; then
      echo "[start_keycloak_services] Falling back to compose_services_for_profile..."
      mapfile -t svcs < <(compose_services_for_profile "keycloak" 2>/dev/null || true)
      echo "[start_keycloak_services] Found ${#svcs[@]} service(s) via fallback: ${svcs[*]:-<none>}"
    fi
  else
    echo "[start_keycloak_services] Backend does NOT support profiles → skipping profile query"
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

  echo "[start_keycloak_services] No profile 'keycloak' found → falling back to direct service detection"
  mapfile -t ALL_SERVS < <(compose_list_services)
  echo "[start_keycloak_services] All services discovered: ${ALL_SERVS[*]:-<none>}"

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
    -ext "SAN=dns:localhost,dns:trino,dns:trino.local,ip:127.0.0.1" \
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
  local dir="config_files/keycloak/"

  # CA
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -keyout config_files/keycloak/secrets/ca/ca.key -out config_files/keycloak/secrets/ca/ca.crt \
    -subj "/CN=osss-dev-ca"

  # Keycloak CSR (SAN: keycloak)
  openssl req -new -nodes -newkey rsa:2048 \
    -keyout config_files/keycloak/secrets/keycloak/server.key \
    -out config_files/keycloak/secrets/keycloak/server.csr \
    -subj "/CN=keycloak" \
    -addext "subjectAltName=DNS:keycloak,DNS:localhost,DNS:keycloak.local,IP:127.0.0.1"

  # Sign server cert with our CA
  openssl x509 -req -in config_files/keycloak/secrets/keycloak/server.csr \
    -CA config_files/keycloak/secrets/ca/ca.crt -CAkey config_files/keycloak/secrets/ca/ca.key -CAcreateserial \
    -out config_files/keycloak/secrets/keycloak/server.crt -days 365 \
    -extfile <(printf "subjectAltName=DNS:keycloak")


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
  local FILE="${COMPOSE_FILE:-docker-compose.yml}"

  # Pull normalized config once (services + expanded volumes)
  local cfg
  if ! cfg="$("$CMD" -f "$FILE" --profile "$PROFILE" config 2>/dev/null)"; then
    return 0
  fi

  # awk: collect 'volumes:' sources for the target services (ignore bind mounts)
  awk -v list="$(printf '%s ' "${SERVICES[@]}")" '
    function has(x, s,   i,n,a){ n=split(s,a," "); for(i=1;i<=n;i++) if(a[i]==x) return 1; return 0 }
    function indent(s){ match(s, /^[ \t]*/); return RLENGTH }
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
    }
  ' <<<"$cfg" | awk 'NF && !seen[$0]++'
}

# --- remove project volumes for selected services (works even if no containers exist) ---
remove_volumes_for_services() {
  local project="$1"; shift
  local prof="$1"; shift
  local svcs=("$@")

  # 1) Collect attached volumes from existing containers (if any)
  local project_label service_label
  if [[ "$(get_compose_engine)" == "podman" ]]; then
    project_label="io.podman.compose.project"
    service_label="io.podman.compose.service"
  else
    project_label="com.docker.compose.project"
    service_label="com.docker.compose.service"
  fi

  local -a ps_args=('ps' '-a' '--format' '{{.ID}}' '--filter' "label=${project_label}=${project}")
  for s in "${svcs[@]}"; do ps_args+=('--filter' "label=${service_label}=${s}"); done

  local CIDS
  CIDS="$(engine_exec "$(get_compose_engine)" "${ps_args[@]}" | awk 'NF')" || CIDS=""

  local VOL_ATTACHED=""
  if [[ -n "$CIDS" ]]; then
    VOL_ATTACHED="$(engine_exec "$(get_compose_engine)" inspect -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{"\n"}}{{end}}{{end}}' $CIDS \
                    | awk 'NF && !seen[$0]++')"
  fi

  # 2) Collect named volumes from compose config for the same services
  local -a base_vols
  readarray -t base_vols < <(compose_named_vols_for_services_cli "$prof" "${svcs[@]}")
  # Elastic-specific safety net (if parsing ever returns empty)
  if [[ "${prof}" == "elastic" && ${#base_vols[@]} -eq 0 ]]; then
    base_vols=(es-data es-shared)
  fi

  # 3) Union of everything we’ve found
  local -a to_remove=()
  if [[ -n "$VOL_ATTACHED" ]]; then
    while IFS= read -r v; do [[ -n "$v" ]] && to_remove+=("$v"); done <<<"$VOL_ATTACHED"
  fi
  for v in "${base_vols[@]}"; do
    to_remove+=("$v" "${project}_${v}")
  done

  # 4) Dedup and remove only those that actually exist
  local -A seen; local vname
  for vname in "${to_remove[@]}"; do
    [[ -n "$vname" && -z "${seen[$vname]:-}" ]] || continue
    seen[$vname]=1
    # Check existence before removing
    if podman volume inspect "$vname" >/dev/null 2>&1; then
      echo "🧹 Removing volume: $vname"
      podman volume rm -f "$vname" >/dev/null 2>&1 || true
    fi
  done
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

  # 0) Show versions (optional, for sanity)
  podman --version || true
  podman machine --help | head -n 1 || true

  # 1) Stop machine if Podman thinks it exists
  podman machine stop podman-machine-default || true
  podman machine stop || true

  # 2) Drop stale connections
  for c in podman-machine-default podman-machine-default-root; do
    podman system connection rm "$c" 2>/dev/null || true
  done

  # 3) Try to remove any machine records
  podman machine rm -f podman-machine-default 2>/dev/null || true
  podman machine rm -f 2>/dev/null || true

  # 4) Nuke leftover local state (macOS)
  rm -rf \
    ~/.config/containers/podman/machine \
    ~/.local/share/containers/podman/machine \
    ~/.local/share/containers/podman/machine/qemu/podman-machine-default \
    ~/.ssh/podman-machine-default* 2>/dev/null || true

  # 5) Recreate the VM
  if podman machine init --help | grep -qE 'machine init.*\[NAME\]'; then
    podman machine init podman-machine-default --cpus 4 --memory 6144 --disk-size 60
  else
    podman machine init --cpus 4 --memory 6144 --disk-size 60
  fi

  # 6) Start the VM
  podman machine start

  # 7) Make it the default connection if needed
  podman system connection default podman-machine-default 2>/dev/null || true

  # 8) Quick test
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
  if [[ -z "$GRAPHROOT" && "$(uname -s)" == "Darwin" ]] && podman machine inspect >/dev/null 2>&1; then
    GRAPHROOT="$(podman machine ssh -- podman info --format '{{ .Store.GraphRoot }}' 2>/dev/null || true)"
    echo "[preflight_podman_storage] Queried VM for GraphRoot."
  fi

  # 6) Final check
  if [[ -z "$GRAPHROOT" ]]; then
    echo "[preflight_podman_storage] ⚠️  Could not detect GraphRoot in this Podman build."
    echo "[preflight_podman_storage] Store section follows (for debugging):"
    podman info --format '{{json .Store}}' || true
    echo "   Tip: ensure your default connection is the VM:"
    echo "        podman system connection default podman-machine-default"
    echo "        podman machine start"
    return 1
  fi

  echo "[preflight_podman_storage] GraphRoot: $GRAPHROOT"
  return 0
}



# --- engine_exec: trace to STDERR, emit only command STDOUT to caller ---
engine_exec() {
  local ENGINE="$1"; shift
  # Trace → STDERR (so callers reading STDOUT only see command output)
  >&2 echo "[engine_exec] Invoked with ENGINE='${ENGINE}' and args: $*"
  >&2 echo "[engine_exec] Running dry run (stderr only) to capture errors..."
  # Dry run just to surface errors to the logs; discard stdout, keep rc
  local drc=0
  { "$ENGINE" "$@" 1>/dev/null; } 2> >(cat >&2) || drc=$?
  >&2 echo "[engine_exec] Dry run exit code: $drc"
  [[ $drc -ne 0 ]] && {
    >&2 echo "[engine_exec] Captured stderr above (if any)"
  }
  >&2 echo "[engine_exec] Running command for real..."
  # REAL run: forward stdout (for callers) and stderr (for logs)
  local rc=0
  "$ENGINE" "$@" 2> >(cat >&2) || rc=$?
  >&2 echo "[engine_exec] Final exit code: $rc"
  return $rc
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

down_profile_clean() {
  set -Eeuo pipefail
  local PROFILE="$1"
  local CMD; CMD="$(__compose_cmd)"
  local FILE="${COMPOSE_FILE:-docker-compose.yml}"
  local PROJECT; PROJECT="$(__compose_project_name 2>/dev/null || echo "${COMPOSE_PROJECT_NAME:-osss}")"

  echo "ℹ️  Using compose: $CMD   project=$PROJECT   file=$FILE"

  # Resolve services cleanly (no debug noise)
  mapfile -t SVCS < <(compose_services_for_profile "$CMD" "$FILE" "$PROFILE")
  if ((${#SVCS[@]}==0)); then
    echo "⚠️  No services for profile '$PROFILE' in $FILE"; return 1
  fi
  echo "🔎 Services in '$PROFILE': ${SVCS[*]}"

  # 1) Ask compose to stop, then rm (labels-aware)
  echo "▶️  compose stop ${SVCS[*]}"
  compose_exec "$CMD" -f "$FILE" stop "${SVCS[@]}" || true

  echo "🗑️  compose rm -f ${SVCS[*]}"
  compose_exec "$CMD" -f "$FILE" rm -f "${SVCS[@]}" || true

  # 2) Fallback: if any service containers still exist *without* compose labels, remove them.
  #    We match by BOTH typical compose names and raw service names.
  echo "🔍 Fallback sweep for unlabeled containers…"
  for s in "${SVCS[@]}"; do
    # Common compose name patterns:
    #   <project>_<service>_1, <project>-<service>-1, exact <service>
    local patt1="^/${PROJECT}[._-]${s}(_|-)??[0-9]*$"
    local patt2="^/${s}$"
    # list candidate IDs
    local ids id
    ids="$(podman ps -a --format '{{.ID}}\t{{.Names}}\t{{.Image}}' | awk -v p1="$patt1" -v p2="$patt2" '
      $2 ~ p1 || $2 ~ p2 { print $1 }')"
    # filter out ones that DO have compose labels already (compose handled them)
    if [[ -n "$ids" ]]; then
      while IFS= read -r id; do
        [[ -z "$id" ]] && continue
        # If container has compose project label matching ours, skip (already handled)
        if podman inspect "$id" --format '{{index .Config.Labels "com.docker.compose.project"}}' 2>/dev/null | grep -qx "$PROJECT"; then
          continue
        fi
        echo "🧹 Removing leftover container (no compose label): $id ($s)"
        podman rm -f "$id" || true
      done <<<"$ids"
    fi
  done

  # 3) Optional: volumes attached to those containers (named volumes only)
  echo "🧹 Pruning named volumes attached to just-removed containers (best effort)…"
  # Safe no-op if none:
  podman volume prune -f >/dev/null || true

  echo "✅ Done with profile '$PROFILE'."
}


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
      echo "   Run: 'podman machine start' and/or 'podman system migrate', then retry." >&2
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

  # Normalize quotes
  prof="${prof%\"}"; prof="${prof#\"}"; prof="${prof%\'}"; prof="${prof#\'}"
  echo "ℹ️  Normalized profile: $prof"

  echo "[down_profile_interactive] Resolving services for profile '$prof' (authoritative via compose)..."
  mapfile -t SVCS < <(compose_exec "${CMD_ARR[@]}" -f "$COMPOSE_FILE_LOCAL" --profile "$prof" config --services 2>/dev/null | awk 'NF')
  # If compose_exec returned the sentinel 200, the pipeline will be empty; we still proceed to fallback
  echo "[down_profile_interactive] Services from CLI: ${SVCS[*]:-<none>}"
  if [ "${#SVCS[@]}" -eq 0 ]; then
    echo "[down_profile_interactive] Falling back to compose_services_for_profile '$prof'..."
    mapfile -t SVCS < <(compose_services_for_profile "$prof" 2>/dev/null || true)
    echo "[down_profile_interactive] Services via fallback: ${SVCS[*]:-<none>}"
  fi

  echo "🔎 Services in profile '$prof': ${SVCS[*]:-(none)}"
  if [ "${#SVCS[@]}" -eq 0 ]; then
    echo "⚠️  No services declare profile '${prof}'. Nothing to do."
    echo "[down_profile_interactive] Exiting (no services)"
    return 0
  fi

  echo "[down_profile_interactive] Computing cascade (linked services)..."
  mapfile -t __CASCADE < <(cascade_services_for_profile "$prof" || true)
  if ((${#__CASCADE[@]})); then
    echo "🔗 Cascade: also including linked service(s): ${__CASCADE[*]}"
    SVCS+=("${__CASCADE[@]}")
  else
    echo "[down_profile_interactive] No cascade services detected"
  fi

  echo "🚧 Taking down profile '${prof}' services: ${SVCS[*]}"

  {
    echo "[down_profile_interactive] Entering teardown (set -x enabled for commands)"
    set -x

    echo "ℹ️ Stop and remove via compose first (engine-agnostic)"
    compose_exec "${CMD_ARR[@]}" -f "$COMPOSE_FILE_LOCAL" stop "${SVCS[@]}" || true

    if "${CMD_ARR[@]}" rm -h >/dev/null 2>&1; then
      compose_exec "${CMD_ARR[@]}" -f "$COMPOSE_FILE_LOCAL" rm -s -f -v "${SVCS[@]}" || true
    fi

    echo "ℹ️ Label-based cleanup with engine; catch statfs and abort gracefully"
    # Build ps args safely by array to avoid "--filter--filter" concatenation bug
    local project_label service_label
    if [[ "$ENGINE" == "podman" ]]; then
      project_label="io.podman.compose.project"
      service_label="io.podman.compose.service"
    else
      project_label="com.docker.compose.project"
      service_label="com.docker.compose.service"
    fi

    # Collect container IDs for these services
    local -a ps_args=(ps -a --format '{{.ID}}')
    ps_args+=(--filter "label=${project_label}=${PROJECT}")
    for s in "${SVCS[@]}"; do
      ps_args+=(--filter "label=${service_label}=${s}")
    done

    CIDS=()
    while read -r id; do
      [[ -n "$id" ]] && CIDS+=("$id")
    done < <(engine_exec "$ENGINE" "${ps_args[@]}" 2>/dev/null || true)

    # If we found any, inspect them (in array form) to collect *attached* volumes
    VOL_ATTACHED=()
    if ((${#CIDS[@]})); then
      while read -r v; do
        [[ -n "$v" ]] && VOL_ATTACHED+=("$v")
      done < <(engine_exec "$ENGINE" inspect "${CIDS[@]}" \
              -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{"\n"}}{{end}}{{end}}' \
              2>/dev/null | awk 'NF && !seen[$0]++' || true)

      # Remove those containers
      engine_exec "$ENGINE" rm -f "${CIDS[@]}" >/dev/null 2>&1 || true
    fi

    declare -a VOL_ATTACHED=()
    if ((${#CIDS[@]})); then
      while read -r v; do [[ -n "$v" ]] && VOL_ATTACHED+=("$v"); done < <(
        engine_exec "$ENGINE" inspect "${CIDS[@]}" \
          -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{"\n"}}{{end}}{{end}}' 2>/dev/null | awk 'NF && !seen[$0]++' || true
      )
      engine_exec "$ENGINE" rm -f "${CIDS[@]}" >/dev/null 2>&1 || true
    fi

    echo "ℹ️ Services are: ${SVCS}"
    echo "ℹ️ Fallback: remove by service name (handles engine quirks)"
    engine_exec "$ENGINE" rm -f "${SVCS[@]}" >/dev/null 2>&1 || true

    PROJECT="$(__compose_project_name)"
    echo "ℹ️  … stop/rm containers first …"
    REMOVE_VOLUMES=1 FORCE_VOLUME_REMOVE=1 remove_volumes_for_services "$PROJECT" "elastic" "${SVCS[@]}"

    set +x
    echo "[down_profile_interactive] Teardown commands complete (set -x disabled)"
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


  echo "[down_profile_interactive] Listing remaining containers for project='$PROJECT'..."
  engine_exec "$ENGINE" ps --format '{{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}' \
    --filter "label=com.docker.compose.project=${PROJECT}" | sed 's/^/  /' || true

  echo "[down_profile_interactive] Removing compose-declared named volumes for these services (helper)..."
  remove_volumes_for_services "$PROJECT" --volumes "${SVCS[@]}" || true

  echo "✅ Done with profile '${prof}'."
  echo "[down_profile_interactive] Returning to menu..."
  prompt_return
  echo "[down_profile_interactive] Finished execution"
}



# -------- Podman VM management --------
podman_vm_name() {
  echo "${PODMAN_MACHINE_NAME:-default}"
}
podman_vm_stop() {
  if ! command -v podman >/dev/null 2>&1; then
    echo "Podman not installed."
    return 1
  fi
  local NAME; NAME="$(podman_vm_name)"
  echo "▶️  Stopping podman machine '$NAME'…"
  podman machine stop "$NAME" || {
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
  echo "▶️  Stopping (if running)…"; podman machine stop "$NAME" >/dev/null 2>&1 || true
  echo "🗑  Removing podman machine '$NAME'…"
  podman machine rm -f "$NAME"
  echo "✅ Destroyed podman machine '$NAME'."
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
    echo "17) Create Keycloak server certificate"
    echo "18) Reset Podman machine (wipe & restart)"
    echo "19) Stop Podman VM"
    echo "20) Destroy Podman VM"
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
      17) create_keycloak_cert ;;
      18) reset_podman_machine ;;
      19) podman_vm_stop ;;
      20) podman_vm_destroy ;;
      q|Q) echo "Bye!"; exit 0 ;;
      *)   echo "Unknown choice: ${ans}"; prompt_return ;;
    esac
  done
}

menu






