#!/usr/bin/env bash
# docker-logs-menu.sh
# View docker compose service logs (follow) with one keypress to exit and come back to the menu.
# Adds profile-aware service discovery and a menu to pick active profiles.

set -euo pipefail

# --- Helpers ---
compose_cmd() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "docker compose"; return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"; return
  fi
  echo "❌ Neither 'docker compose' nor 'docker-compose' found on PATH." >&2
  exit 1
}

have_jq() { command -v jq >/dev/null 2>&1; }

# Defaults (override via env or flags)
COMPOSE_FILE="${COMPOSE_FILE:-../docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"
TAIL_DEFAULT="${TAIL_DEFAULT:-400}"
PROFILE_FILTER="${PROFILE_FILTER:-}"   # e.g. "seed,app" or "" for ALL

# CLI flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--file) COMPOSE_FILE="$2"; shift 2;;
    --env-file) ENV_FILE="$2"; shift 2;;
    -t|--tail) TAIL_DEFAULT="$2"; shift 2;;
    -p|--profiles) PROFILE_FILTER="$2"; shift 2;;   # comma-separated, e.g. seed,app
    -h|--help)
      cat <<EOF
Usage: $0 [-f docker-compose.yml] [--env-file .env] [-t 200] [-p seed,app]

Options:
  -f, --file FILE       Path to docker-compose.yml (default: ../docker-compose.yml)
      --env-file FILE   Path to .env to pass to compose (if exists)
  -t, --tail N          Default 'tail -n' for logs (default: 400)
  -p, --profiles LIST   Comma-separated profiles to enable (e.g. "seed,app"; empty = all)

Tips:
  - Press Ctrl-C to exit the logs and return to this menu.
  - Service list honors the selected profiles (via --profile flags).
EOF
      exit 0;;
    *) echo "Unknown argument: $1" >&2; exit 1;;
  esac
done

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "❌ Compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

COMPOSE="$(compose_cmd)"
ENV_ARGS=()
if [[ -f "$ENV_FILE" ]]; then
  ENV_ARGS+=(--env-file "$ENV_FILE")
fi

# Build profile args array from PROFILE_FILTER (comma-separated)
build_profile_args() {
  PROFILES_ARGS=()
  if [[ -n "${PROFILE_FILTER}" ]]; then
    IFS=',' read -r -a _p <<<"$PROFILE_FILTER"
    for p in "${_p[@]}"; do
      p_trim="${p//[[:space:]]/}"
      [[ -n "$p_trim" ]] && PROFILES_ARGS+=(--profile "$p_trim")
    done
  fi
}

# Discover all distinct profiles from the compose (best-effort)
discover_all_profiles() {
  ALL_PROFILES=()
  if have_jq; then
    if $COMPOSE "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" config --format json >/dev/null 2>&1; then
      mapfile -t ALL_PROFILES < <(
        $COMPOSE "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" config --format json \
          | jq -r '.services|to_entries[]|.value.profiles // []|.[]' \
          | sort -u
      )
    fi
  fi
}

# Get list of services honoring profile selection
get_services() {
  build_profile_args
  if have_jq && $COMPOSE "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" "${PROFILES_ARGS[@]}" config --format json >/dev/null 2>&1; then
    # JSON path: .services keys (only those enabled by selected profiles)
    mapfile -t SERVICES < <(
      $COMPOSE "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" "${PROFILES_ARGS[@]}" config --format json \
        | jq -r '.services|keys[]' | sort
    )
  else
    # Fallback: plain list (cannot filter by profile without --format json); shows all
    mapfile -t SERVICES < <($COMPOSE "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" config --services | sort)
  fi
}

# Pretty string for current profiles
profiles_pretty() {
  if [[ -z "$PROFILE_FILTER" ]]; then
    echo "ALL (no filter)"
  else
    echo "$PROFILE_FILTER"
  fi
}

discover_all_profiles
get_services

if [[ ${#SERVICES[@]} -eq 0 ]]; then
  echo "❌ No services found in $COMPOSE_FILE" >&2
  exit 1
fi

# Menu loop
while true; do
  clear
  echo "================ Docker Logs Menu ================"
  echo "Compose file : $COMPOSE_FILE"
  [[ -f "$ENV_FILE" ]] && echo "Env file     : $ENV_FILE"
  echo "Profiles     : $(profiles_pretty)"
  if [[ ${#ALL_PROFILES[@]} -gt 0 ]]; then
    echo "Available    : ${ALL_PROFILES[*]}"
  fi
  echo "Default tail : $TAIL_DEFAULT lines"
  echo "=================================================="
  echo "Select a service to follow logs:"
  echo

  i=1
  for s in "${SERVICES[@]}"; do
    printf "  %2d) %s\n" "$i" "$s"
    ((i++))
  done
  printf "  %2d) %s\n" "$i" "All services (current profiles)"; ALL_IDX=$i; ((i++))
  printf "  %2d) %s\n" "$i" "Change tail (current: $TAIL_DEFAULT)"; TAIL_IDX=$i; ((i++))
  printf "  %2d) %s\n" "$i" "Change profiles (current: $(profiles_pretty))"; PROF_IDX=$i; ((i++))
  printf "  %2d) %s\n" "$i" "Quit"; QUIT_IDX=$i
  echo

  read -rp "Enter choice [1-$i]: " choice || exit 0
  [[ -z "${choice:-}" ]] && continue
  if ! [[ "$choice" =~ ^[0-9]+$ ]]; then
    echo "Not a number. Press Enter to continue." && read -r _; continue
  fi

  if (( choice == QUIT_IDX )); then
    echo "Bye!"; exit 0
  fi

  if (( choice == TAIL_IDX )); then
    read -rp "New tail lines: " newtail
    if [[ "$newtail" =~ ^[0-9]+$ ]] && (( newtail >= 0 )); then
      TAIL_DEFAULT="$newtail"
    else
      echo "Invalid number."; sleep 1
    fi
    continue
  fi

  if (( choice == PROF_IDX )); then
    echo
    echo "Change profiles:"
    echo "  - Enter comma-separated list (e.g. seed,app)"
    echo "  - Leave empty for ALL (no profile filter)"
    read -rp "Profiles: " pf
    PROFILE_FILTER="${pf//[[:space:]]/}"
    get_services
    if [[ ${#SERVICES[@]} -eq 0 ]]; then
      echo "⚠️  No services match these profiles; reverting to ALL."
      PROFILE_FILTER=""
      get_services
    fi
    continue
  fi

  if (( choice == ALL_IDX )); then
    echo "➡️  Following logs for ALL services (tail $TAIL_DEFAULT) with profiles: $(profiles_pretty). Press Ctrl-C to return."
    build_profile_args
    # shellcheck disable=SC2068
    $COMPOSE "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" ${PROFILES_ARGS[@]+"${PROFILES_ARGS[@]}"} logs -f --tail="$TAIL_DEFAULT"
    continue
  fi

  idx=$((choice-1))
  if (( idx < 0 || idx >= ${#SERVICES[@]} )); then
    echo "Invalid choice."; sleep 1; continue
  fi

  svc="${SERVICES[$idx]}"
  echo "➡️  Following logs for service: $svc (tail $TAIL_DEFAULT) with profiles: $(profiles_pretty). Press Ctrl-C to return."
  build_profile_args
  $COMPOSE "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" ${PROFILES_ARGS[@]+"${PROFILES_ARGS[@]}"} logs -f --tail="$TAIL_DEFAULT" "$svc"
done
