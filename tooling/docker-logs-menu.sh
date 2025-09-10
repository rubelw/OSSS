#!/usr/bin/env bash
# docker-logs-menu.sh
# Simple menu to view docker compose service logs (follow) with one keypress to exit and come back to the menu.

set -euo pipefail

# --- Helpers ---
compose_cmd() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "docker compose"
    return
  fi
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
    return
  fi
  echo "❌ Neither 'docker compose' nor 'docker-compose' found on PATH." >&2
  exit 1
}

# Discover compose file (current dir by default) unless user passes -f FILE
COMPOSE_FILE="${COMPOSE_FILE:-../docker-compose.yml}"
ENV_FILE="${ENV_FILE:-.env}"
TAIL_DEFAULT="${TAIL_DEFAULT:-400}"

# CLI flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--file) COMPOSE_FILE="$2"; shift 2;;
    --env-file) ENV_FILE="$2"; shift 2;;
    -t|--tail) TAIL_DEFAULT="$2"; shift 2;;
    -h|--help)
      cat <<EOF
Usage: $0 [-f docker-compose.yml] [--env-file .env] [-t 200]

Options:
  -f, --file FILE      Path to docker-compose.yml (default: docker-compose.yml)
      --env-file FILE  Path to .env to pass to compose (if exists)
  -t, --tail N         Default 'tail -n' for logs (default: 200)

Tips:
  - Press Ctrl-C to exit the logs and return to this menu.
  - Services list is discovered from: 'compose config --services'.
EOF
      exit 0;;
    *)
      echo "Unknown argument: $1" >&2; exit 1;;
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

# Get list of services from compose config
mapfile -t SERVICES < <($COMPOSE "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" config --services | sort)

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
  echo "Default tail : $TAIL_DEFAULT lines"
  echo "=================================================="
  echo "Select a service to follow logs:"
  echo

  i=1
  for s in "${SERVICES[@]}"; do
    printf "  %2d) %s\n" "$i" "$s"
    ((i++))
  done
  printf "  %2d) %s\n" "$i" "All services"
  ALL_IDX=$i
  ((i++))
  printf "  %2d) %s\n" "$i" "Change tail (current: $TAIL_DEFAULT)"
  TAIL_IDX=$i
  ((i++))
  printf "  %2d) %s\n" "$i" "Quit"
  QUIT_IDX=$i
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
      echo "Invalid number."
      sleep 1
    fi
    continue
  fi

  if (( choice == ALL_IDX )); then
    echo "➡️  Following logs for ALL services (tail $TAIL_DEFAULT). Press Ctrl-C to return."
    # shellcheck disable=SC2068
    $COMPOSE "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" logs -f --tail="$TAIL_DEFAULT"
    continue
  fi

  idx=$((choice-1))
  if (( idx < 0 || idx >= ${#SERVICES[@]} )); then
    echo "Invalid choice."
    sleep 1
    continue
  fi

  svc="${SERVICES[$idx]}"
  echo "➡️  Following logs for service: $svc (tail $TAIL_DEFAULT). Press Ctrl-C to return."
  $COMPOSE "${ENV_ARGS[@]}" -f "$COMPOSE_FILE" logs -f --tail="$TAIL_DEFAULT" "$svc"
done