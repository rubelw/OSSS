#!/usr/bin/env bash

# Fallback compose command if DC not provided
: "${DC:=docker compose}"

export COMPOSE_PROJECT_NAME=osss


# Ensure /etc/hosts contains 'host.docker.internal' on 127.0.0.1 line alongside 'localhost'
if ! grep -Eq '^[[:space:]]*127\.0\.0\.1[[:space:]].*\bhost\.docker\.internal\b' /etc/hosts; then
  if grep -Eq '^[[:space:]]*127\.0\.0\.1[[:space:]].*\blocalhost\b' /etc/hosts; then
    echo "🖇️  Adding 'host.docker.internal' to 127.0.0.1 localhost line (requires sudo)"
    TMPH="$(mktemp)"
    awk '($1=="127.0.0.1" && $0 ~ /\blocalhost\b/ && $0 !~ /\bhost\.docker\.internal\b/) {print $0" host.docker.internal"; next} {print}' /etc/hosts > "$TMPH"
    sudo cp "$TMPH" /etc/hosts && rm -f "$TMPH"
  else
    echo "🖇️  Appending '127.0.0.1 localhost host.docker.internal' to /etc/hosts (requires sudo)"
    echo "127.0.0.1 localhost host.docker.internal" | sudo tee -a /etc/hosts >/dev/null
  fi
else
  echo "✅ /etc/hosts already contains 'host.docker.internal'"
fi

set -euo pipefail

# --- Locations ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if REPO_ROOT_GIT="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel 2>/dev/null)"; then
  REPO_ROOT="$REPO_ROOT_GIT"
else
  REPO_ROOT="$SCRIPT_DIR"
fi

# Give this compose run a stable project name to avoid collisions
export COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-osss}
PROJECT="$COMPOSE_PROJECT_NAME"
NET="${PROJECT}_osss-net"

# ---- CLI flags ----
DO_BUILD=0
NO_CACHE=0

usage() {
  cat <<EOF
Usage: $(basename "$0") [--build|--rebuild] [--help]

  --build     Build docker images before 'compose up' (uses cache).
  --rebuild   Build docker images with --no-cache before 'compose up'.
  --help      Show this help.

If no flag is passed, the script will skip the image build step and just run 'compose up'.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)
      DO_BUILD=1
      NO_CACHE=0
      shift
      ;;
    --rebuild|--no-cache)
      DO_BUILD=1
      NO_CACHE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

# Ensure the external network exists (Compose won't create external networks)
if ! docker network inspect "$NET" >/dev/null 2>&1; then
  echo "🌐 Creating external network: $NET"
  docker network create "$NET"
else
  echo "✅ External network present: $NET"
fi

### --- .env loader (before reading defaults) ---
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env}"

mask() {
  local v="${1:-}"; local n="${#v}"
  if [[ -z "$v" ]]; then echo ""; return; fi
  if [[ $n -le 8 ]]; then printf '******'; else printf '****%s' "${v: -4}"; fi
}

load_env_file() {
  if [[ -f "$ENV_FILE" ]]; then
    echo "🧩 Loading environment from: $ENV_FILE"
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
  else
    echo "ℹ️  No .env file found at: $ENV_FILE (skipping)"
  fi
}
load_env_file

### --- Helpers used early ---

# --- URL encode a single component (user/pass) for DSNs ---
url_quote() {
  local py; py="$(resolve_python)"
  "$py" -c 'import sys, urllib.parse as u; print(u.quote(sys.argv[1], safe=""))' "$1"
}

# Trim outer whitespace and strip CR/LF (fixes CRLF line endings sneaking into secrets)
_trim_spaces() { local s="${1-}"; s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"; printf '%s' "$s"; }
_strip_crlf() { printf '%s' "${1-}" | tr -d '\r\n'; }
sanitize_secret() {
  local orig="${1-}"
  local trimmed; trimmed="$(_trim_spaces "$orig")"
  local fixed;   fixed="$(_strip_crlf "$trimmed")"
  if [[ "$orig" != "$fixed" ]]; then
    echo "⚠️  Normalized a secret (removed CR/LF or outer spaces)"
  fi
  printf '%s' "$fixed"
}

compose_base_cmd() {
  if command -v docker >/dev/null 2>&1; then
    if docker compose version >/dev/null 2>&1; then echo "docker compose"; return; fi
  fi
  if command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; return; fi
  echo "ERROR: Neither 'docker compose' nor 'docker-compose' found on PATH." >&2
  exit 1
}

# Decide which compose to use, and store it as an array not a string.
COMPOSE_CMD_STR="$(compose_base_cmd)"
if [[ "$COMPOSE_CMD_STR" == "docker compose" ]]; then
  COMPOSE_CMD_ARR=(docker compose)
else
  COMPOSE_CMD_ARR=(docker-compose)
fi
compose() { "${COMPOSE_CMD_ARR[@]}" "$@"; }

COMPOSE_ENV_ARGS=()
[[ -f "$ENV_FILE" ]] && COMPOSE_ENV_ARGS+=(--env-file "$ENV_FILE")


resolve_python() { command -v python >/dev/null 2>&1 && { echo "python"; return; }
                   command -v python3 >/dev/null 2>&1 && { echo "python3"; return; }
                   echo "❌ Python not found on PATH" >&2; exit 1; }
resolve_npm()    { command -v npm >/dev/null 2>&1 && { echo "npm"; return; }
                   echo "❌ npm not found on PATH. Install Node.js/npm." >&2; exit 1; }

# --- Priv escalation helper for package managers ---
need_sudo() { if [ "$(id -u)" -eq 0 ]; then echo ""; else command -v sudo >/dev/null 2>&1 && echo "sudo" || echo ""; fi; }

# --- mkcert (install if missing) + local TLS cert generation ---
ensure_mkcert() {
  if command -v mkcert >/dev/null 2>&1; then
    echo "✅ mkcert already installed: $(command -v mkcert)"
    return 0
  fi
  echo "⬇️  Installing mkcert…"
  local SUDO; SUDO="$(need_sudo)"
  case "$(uname -s)" in
    Darwin)
      if command -v brew >/dev/null 2>&1; then
        brew update >/dev/null || true
        brew install mkcert nss || brew install mkcert || true
      else
        echo "❌ Homebrew not found. Install Homebrew or mkcert manually: https://github.com/FiloSottile/mkcert" >&2
        return 1
      fi
      ;;
    Linux)
      if command -v apt-get >/dev/null 2>&1; then
        $SUDO apt-get update -y
        $SUDO apt-get install -y mkcert libnss3-tools || $SUDO apt-get install -y mkcert
      elif command -v dnf >/dev/null 2>&1; then
        $SUDO dnf install -y mkcert nss-tools || $SUDO dnf install -y mkcert
      elif command -v yum >/dev/null 2>&1; then
        $SUDO yum install -y mkcert nss-tools || $SUDO yum install -y mkcert
      elif command -v apk >/dev/null 2>&1; then
        $SUDO apk add --no-cache mkcert nss-tools || $SUDO apk add --no-cache mkcert nss
      elif command -v pacman >/dev/null 2>&1; then
        $SUDO pacman -Sy --noconfirm mkcert nss || $SUDO pacman -Sy --noconfirm mkcert
      else
        echo "❌ No supported package manager found. Install mkcert manually." >&2
        return 1
      fi
      ;;
    *)
      echo "❌ Unsupported OS for auto-install. Install mkcert manually." >&2
      return 1
      ;;
  esac
  command -v mkcert >/dev/null 2>&1 || { echo "❌ mkcert install failed." >&2; return 1; }
  echo "✅ mkcert installed: $(command -v mkcert)"
}

ensure_local_tls_cert() {
  local SUDO; SUDO="$(need_sudo)"
  if [ ! -d "${TLS_CERT_DIR}" ]; then
    $SUDO mkdir -p "${TLS_CERT_DIR}"
    $SUDO chown "$(id -u):$(id -g)" "${TLS_CERT_DIR}" || true
  fi
  mkcert -install
  if [[ ! -s "${TLS_CERT_FILE}" || ! -s "${TLS_KEY_FILE}" ]]; then
    echo "🔐 Generating local TLS certs for: ${TLS_DOMAIN_LIST}"
    mkcert -key-file "${TLS_KEY_FILE}" -cert-file "${TLS_CERT_FILE}" ${TLS_DOMAIN_LIST}
    echo "✅ Created:"
    echo "   cert: ${TLS_CERT_FILE}"
    echo "   key : ${TLS_KEY_FILE}"
  else
    echo "✅ Using existing TLS certs:"
    echo "   ${TLS_CERT_FILE}"
    echo "   ${TLS_KEY_FILE}"
  fi
}

wait_for_url() {
  local url="$1"; local timeout="$2"
  local deadline=$(( $(date +%s) + timeout )); local delay=2
  echo "⏳ Waiting for ${url} (up to ${timeout}s)…"
  while [ "$(date +%s)" -lt "${deadline}" ]; do
    if curl -fsS -m 5 -H "Connection: close" "${url}" >/dev/null 2>&1; then
      echo "✅ Ready: ${url}"; return 0; fi
    sleep "${delay}"; [ "${delay}" -lt 5 ] && delay=$((delay + 1))
  done
  return 1
}

strip_sqla_driver() { local url="$1"; url="${url//+asyncpg/}"; url="${url//+psycopg2/}"; url="${url//+psycopg/}"; echo "$url"; }
force_ipv4_localhost() { local url="$1"; echo "${url/@localhost:/@127.0.0.1:}"; }
parse_db_host_port() {
  local url="$1"; local rest="${url#*://}"; rest="${rest#*@}"
  local host="${rest%%[:/]*}"; local after="${rest#${host}}"; local port="5432"
  if [[ "$after" == :* ]]; then port="${after#:}"; port="${port%%/*}"; fi
  [[ "$host" == "localhost" ]] && host="127.0.0.1"; echo "${host}:${port}"
}
wait_for_db() {
  local url_raw="$1"; local timeout="${2:-60}"
  local url="$(strip_sqla_driver "$url_raw")"
  local hp; hp="$(parse_db_host_port "$url")"; local host="${hp%%:*}" port="${hp##*:}"
  local deadline=$(( $(date +%s) + timeout ))
  echo "⏳ Waiting for Postgres at ${host}:${port} (up to ${timeout}s)…"
  if command -v pg_isready >/dev/null 2>&1; then
    while [ "$(date +%s)" -lt "${deadline}" ]; do
      if pg_isready -h "$host" -p "$port" >/dev/null 2>&1; then echo "✅ Postgres is accepting connections."; return 0; fi
      sleep 2
    done
  else
    while [ "$(date +%s)" -lt "${deadline}" ]; do (echo > "/dev/tcp/${host}/${port}") >/dev/null 2>&1 && { echo "✅ Postgres TCP ready."; return 0; }; sleep 2; done
  fi
  echo "❌ Timed out waiting for Postgres at ${host}:${port}" >&2; return 1
}
wait_for_pg_service() {
  local svc="$1"; local tries=60
  echo "⏳ Waiting for Postgres in service '${svc}' to be ready…"
  while (( tries-- > 0 )); do
    if "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "${COMPOSE_FILE}" exec -T "$svc" pg_isready -q >/dev/null 2>&1; then
      echo "✅ ${svc} Postgres is ready."; return 0; fi
    sleep 2
  done
  echo "❌ Timed out waiting for ${svc} Postgres." >&2; return 1
}

# SQL escaping helpers
sql_escape_literal() { local s="${1:-}"; s="${s//\'/\'\'}"; printf "'%s'" "$s"; }
sql_escape_ident()   { local s="${1:-}"; s="${s//\"/\"\"}"; printf "\"%s\"" "$s"; }

ensure_role_and_db() {
  local svc="$1" app_user="$2" app_password="$3" app_db="$4"
  local su="${5:-postgres}" su_pw="${6:-}"

  echo "🔧 Ensuring role '${app_user}' and database '${app_db}' exist on ${svc}…"
  echo "   ↳ Using superuser: ${su}"

  # Try to connect (with pw, then without)
  if ! "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "${COMPOSE_FILE}" exec -T -e PGPASSWORD="$su_pw" "$svc" \
        psql -U "$su" -d postgres -c "select 1" >/dev/null 2>&1; then
    if ! "${COMPOSE_CMD[@]}" "${COMPOSE_ARGS[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "${COMPOSE_FILE}" exec -T "$svc" \
          psql -U "$su" -d postgres -c "select 1" >/dev/null 2>&1; then
      echo "❌ Could not connect to $svc as '$su'." >&2; return 1
    fi
  fi

  local L_USER L_PASS L_DB
  L_USER=$(sql_escape_literal "$app_user")
  L_PASS=$(sql_escape_literal "$app_password")
  L_DB=$(sql_escape_literal "$app_db")

  "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "${COMPOSE_FILE}" exec -T -e PGPASSWORD="$su_pw" "$svc" \
    psql -X -v ON_ERROR_STOP=1 -U "$su" -d postgres -f - <<SQL
DO \$do\$
DECLARE
  v_user text := ${L_USER};
  v_pass text := ${L_PASS};
  v_db   text := ${L_DB};
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_user) THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', v_user, v_pass);
  ELSE
    EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', v_user, v_pass);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = v_db) THEN
    EXECUTE format('CREATE DATABASE %I OWNER %I', v_db, v_user);
  ELSE
    BEGIN
      EXECUTE format('ALTER DATABASE %I OWNER TO %I', v_db, v_user);
    EXCEPTION WHEN others THEN
      NULL;
    END;
  END IF;
END
\$do\$;
SQL
}
install_python_requirements() {
  local py; py="$(resolve_python)"

  echo "📦 Ensuring Python dependencies (pyproject/requirements)…"
  "$py" -m pip --version >/dev/null 2>&1 || { echo "❌ pip not available"; exit 1; }
  "$py" -m pip install --upgrade pip setuptools wheel >/dev/null

  # Prompt user (default No)
  read -r -p "Do you want to install Python dependencies now? [y/N] " choice
  choice="${choice:-N}"
  if [[ ! "$choice" =~ ^[Yy]$ ]]; then
    echo "ℹ️  Skipping Python dependency installation."
    return 0
  fi

  if [[ -n "${PY_REQUIREMENTS_FILE:-}" && -f "${PY_REQUIREMENTS_FILE}" ]]; then
    echo "➡️  Installing from ${PY_REQUIREMENTS_FILE}"
    "$py" -m pip install -r "${PY_REQUIREMENTS_FILE}"
    return
  fi

  if [[ -f "${REPO_ROOT}/pyproject.toml" ]]; then
    local extras="${PIP_EXTRAS:-}"
    echo "➡️  Installing from pyproject.toml at ${REPO_ROOT} (editable) ${extras}"
    ( cd "${REPO_ROOT}" && "$py" -m pip install -e ".${extras}" )
    return
  fi

  if [[ -f "${REPO_ROOT}/requirements.txt" ]]; then
    echo "➡️  Installing from requirements.txt"
    "$py" -m pip install -r "${REPO_ROOT}/requirements.txt"
    return
  fi


  echo "⚠️  No pyproject.toml or requirements.txt found – installing minimal realm deps"
  "$py" -m pip install "SQLAlchemy>=2,<3" "pydantic>=2,<3" "pydantic-settings>=2,<3"
}

# Wait for a service to be healthy (or at least running if no healthcheck)
wait_healthy() {
  local service="$1"
  local timeout="${2:-120}"
  local start_ts end_ts cid status
  start_ts=$(date +%s)
  cid="$($DC -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null || true)"
  if [[ -z "$cid" ]]; then
    # try to start it in detached mode
    $DC -f "$COMPOSE_FILE" up -d "$service"
    cid="$($DC -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null || true)"
  fi
  if [[ -z "$cid" ]]; then
    log "WARN: could not get container id for $service"
    return 0
  fi
  while true; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || echo "unknown")"
    case "$status" in
      healthy|running) return 0 ;;
      starting|restarting) ;;
      *) ;;
    esac
    end_ts=$(date +%s)
    if (( end_ts - start_ts > timeout )); then
      log "WARN: timeout waiting for $service (last status: $status)"
      return 0
    fi
    sleep 2
  done
}

realm_exists() {
  curl -fsS "${KEYCLOAK_HTTP}/realms/${KC_REALM}/.well-known/openid-configuration" >/dev/null 2>&1
}

kc_init_needed() {
  # If marker exists, skip
  if [[ -f "$KC_MARKER" ]]; then
    return 1
  fi
  # If realm already responds, skip
  if realm_exists; then
    return 1
  fi
  return 0
}

bring_up_keycloak() {
  echo "▶️  Bringing up keycloak…"
  ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" up -d keycloak || return 1

  if command -v wait_for_url >/dev/null 2>&1; then
    # Try the realm; if not there yet, just wait for Keycloak readiness
    if curl -fsS --max-time 3 "http://localhost:${kc_port}/realms/${kc_realm}/.well-known/openid-configuration" >/dev/null; then
      echo "✅ ${kc_realm} realm is reachable."
    else
      echo "ℹ️ ${kc_realm} realm not found yet; waiting on Keycloak health only."
      wait_for_url "http://localhost:${kc_port}/health/ready" 180 || true
    fi
  fi
}

kc_init_sequence() {
  echo "🔑 Running kc-init (kc-importer → keycloak → kc-post-import → kc-verify)…"

  # 1) DB up
  ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" up -d kc_postgres || return 1
  command -v wait_healthy >/dev/null && wait_healthy kc_postgres 120 || true

  # 2) Offline import (no keycloak running yet)
  ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" --profile "$kc_profile" up --build kc-importer || return 1

  # 3) Start Keycloak and wait for realm to respond
  bring_up_keycloak || return 1

  # 4) Post-import (talks to running KC)
  ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" --profile "$kc_profile" up --build kc-post-import || return 1

  # 5) Optional verification AFTER import settles
  ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" up --build kc-verify || true

  echo "✅ kc-init completed."
}


start_stack() {
  log "Starting stack (without kc-init one-shots)…"
  $DC -f "$COMPOSE_FILE" up -d
  log "Stack is starting. Use: docker compose ps && docker compose logs -f <service>"
}

build_realm_before_infra() {
  # Always prompt the user whether to skip the realm build
  local default="${DEFAULT_SKIP_REALM_BUILD:-N}" ans
  if [[ -t 0 ]]; then
    while :; do
      printf "Skip Keycloak realm build and use existing realm-export.json? [y/N]: "
      read -r ans
      ans="${ans:-$default}"
      case "${ans,,}" in
        y|yes) SKIP_REALM_BUILD=1; break ;;
        n|no)  SKIP_REALM_BUILD=0; break ;;
        *) echo "Please answer yes or no."; ;;
      esac
    done
  else
    echo "⚠️  Non-interactive shell detected; defaulting to '${default}'."
    case "${default,,}" in y|yes) SKIP_REALM_BUILD=1 ;; *) SKIP_REALM_BUILD=0 ;; esac
  fi

  # --- Build realm-export.json BEFORE starting infra ---
  if [[ "${SKIP_REALM_BUILD}" != "1" ]]; then
    if [[ ! -f "${REALM_BUILDER}" ]]; then
      echo "❌ REALM_BUILDER not found: ${REALM_BUILDER}" >&2
      echo "   Set SKIP_REALM_BUILD=1 to bypass this step." >&2
      return 1
    fi

    local PY
    PY="$(resolve_python)"
    echo "🧱 Building realm export via: ${PY} ${REALM_BUILDER}"
    if ! "${PY}" -u "${REALM_BUILDER}"; then
      echo "❌ build_realm.py failed" >&2
      return 1
    fi

    if [[ ! -s "${REALM_EXPORT}" ]]; then
      echo "❌ Realm export not found or empty at: ${REALM_EXPORT}" >&2
      return 1
    fi

    echo "✅ Realm export ready at: ${REALM_EXPORT}"
    echo "Running Python script..."
    python3 ./build_split_realm.py --in ./realm-export.json
  else
    echo "⏭️  Skipping realm build (per user choice)."
  fi

  # --- Start infra (Keycloak + both Postgres) ---
  if [[ ! -f "${COMPOSE_FILE}" ]]; then
    echo "❌ Compose file not found: ${COMPOSE_FILE}" >&2
    return 1
  fi
}


maybe_build_images() {
  # --- Optional image build step ---
  if [[ ${DO_BUILD:-0} -eq 1 ]]; then
    echo "🔧 Building docker images (infra) …"
    if [[ ${NO_CACHE:-0} -eq 1 ]]; then
      echo "   ↳ Using --no-cache"
      "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "${COMPOSE_FILE}" build --no-cache --progress=plain || return 1
    else
      "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "${COMPOSE_FILE}" build --progress=plain || return 1
    fi
    echo "✅ Images built."
  else
    echo "⏭️  Skipping 'compose build' (no --build/--rebuild flag provided)."
  fi
}

ensure_db_roles_and_databases() {
  # --- Ensure both DBs have correct users/passwords (sanitized) ---

  # OSSS Postgres
  wait_for_pg_service osss_postgres || return 1
  ensure_role_and_db osss_postgres \
    "${OSSS_DB_USER}" "${OSSS_DB_PASSWORD}" "${OSSS_DB_NAME}" \
    "${POSTGRES_USER}" "${POSTGRES_PASSWORD}" || return 1

  # Keycloak Postgres
  wait_for_pg_service kc_postgres || return 1
  ensure_role_and_db kc_postgres \
    "${KC_DB_USERNAME}" "${KC_DB_PASSWORD}" "${KC_DB_NAME}" \
    "${KC_DB_USERNAME}" "${KC_DB_PASSWORD}" || return 1
}

run_alembic_migrations() {
  # --- Run Alembic migrations on OSSS Postgres ---
  # Requires env: ALEMBIC_DATABASE_URL, REPO_ROOT, ALEMBIC_CMD, ALEMBIC_INI, OSSS_DB_PASSWORD
  # Uses helpers: force_ipv4_localhost, wait_for_db

  # sanity checks
  [[ -z "${ALEMBIC_DATABASE_URL:-}" ]] && { echo "❌ ALEMBIC_DATABASE_URL is not set" >&2; return 1; }
  [[ -z "${REPO_ROOT:-}" ]] && { echo "❌ REPO_ROOT is not set" >&2; return 1; }
  [[ -z "${ALEMBIC_CMD:-}" ]] && { echo "❌ ALEMBIC_CMD is not set" >&2; return 1; }
  [[ -z "${ALEMBIC_INI:-}" ]] && { echo "❌ ALEMBIC_INI is not set" >&2; return 1; }
  [[ -z "${OSSS_DB_PASSWORD:-}" ]] && { echo "❌ OSSS_DB_PASSWORD is not set" >&2; return 1; }

  # swap async driver for sync driver and normalize localhost to IPv4
  local SYNC_DB_URL
  SYNC_DB_URL="${ALEMBIC_DATABASE_URL/postgresql+asyncpg/postgresql+psycopg2}"
  SYNC_DB_URL="$(force_ipv4_localhost "$SYNC_DB_URL")"

  # helper to hide password in logs/env vars
  drop_password_in_url() {
    echo "$1" | sed -E 's#^(postgresql(\+[a-z0-9]+)?://[^:/@]+):[^@]*(@.*)$#\1\3#'
  }

  local SYNC_DB_URL_NOPW
  SYNC_DB_URL_NOPW="$(drop_password_in_url "$SYNC_DB_URL")"

  echo "🧭 Alembic will use DB URL: ${SYNC_DB_URL}"
  wait_for_db "${SYNC_DB_URL}" 90 || { echo "❌ DB not reachable within timeout" >&2; return 1; }

  echo "📜 Running Alembic migrations (upgrade head)…"
  pushd "${REPO_ROOT}" >/dev/null || { echo "❌ pushd ${REPO_ROOT} failed" >&2; return 1; }
  PGPASSWORD="${OSSS_DB_PASSWORD}" \
  DATABASE_URL="${SYNC_DB_URL_NOPW}" \
  SQLALCHEMY_DATABASE_URL="${SYNC_DB_URL_NOPW}" \
  ALEMBIC_DATABASE_URL="${SYNC_DB_URL_NOPW}" \
    "${ALEMBIC_CMD}" -c "${ALEMBIC_INI}" -x echo=true -x log=DEBUG upgrade head
  local rc=$?
  popd >/dev/null || true

  if [[ $rc -ne 0 ]]; then
    echo "❌ Alembic migrations failed (rc=$rc)" >&2
    return "$rc"
  fi

  echo "✅ Alembic migrations completed."
}

start_infra_with_kc_prompts() {
  # Modes:
  #   1) Seed + start:
  #        docker compose --profile seed up --abort-on-container-exit kc-importer
  #        docker compose up -d keycloak
  #   2) Infra only:
  #        docker compose up -d kc_postgres keycloak
  #   3) Remaining services:
  #        docker compose up -d <everything except kc_postgres/keycloak/kc-importer/kc-verify/kc-post-import>

  local compose_file="${COMPOSE_FILE:-docker-compose.yml}"
  [[ ! -f "$compose_file" ]] && { echo "❌ Compose file not found: ${compose_file}" >&2; return 1; }

  # Resolve compose base cmd and env args (arrays supported)
  local COMPOSE_CMD
  COMPOSE_CMD="$(compose_base_cmd)"
  local -a env_args=()
  [[ ${#COMPOSE_ENV_ARGS[@]} -gt 0 ]] && env_args=("${COMPOSE_ENV_ARGS[@]}")

  # Options / defaults
  local kc_profile="${KC_INIT_PROFILE:-seed}"
  local kc_port="${KEYCLOAK_PORT:-8085}"
  local kc_realm="${KEYCLOAK_REALM:-OSSS}"
  local kc_well_known="http://localhost:${kc_port}/realms/${kc_realm}/.well-known/openid-configuration"

  # Decide mode: arg > env > prompt (non-interactive default = infra)
  local mode=""
  case "${1:-}" in
    seed|SEED)       mode="seed" ;;
    infra|INFRA)     mode="infra" ;;
    rest|remaining|others|stack|REST) mode="rest" ;;
    "") : ;;
    *)  : ;;
  esac
  [[ -z "$mode" && "${DO_KC_SEED:-0}" != "0" ]] && mode="seed"

  if [[ -z "$mode" && -t 0 ]]; then
    echo "What do you want to do?"
    echo "  [1] Seed + start (kc-importer → keycloak)"
    echo "  [2] Bring infra only (kc_postgres + keycloak)"
    echo "  [3] Start remaining services (everything else in compose)"
    printf "Select [1/2/3] (default 1): "
    local ans; read -r ans
    case "$ans" in
      2) mode="infra" ;;
      3) mode="rest"  ;;
      *) mode="seed"  ;;
    esac
  fi
  mode="${mode:-infra}"

  # Helpers
  compose_supports_profiles() {
  # returns 0 if 'docker compose' with profiles is available
  # v2 prints "Docker Compose version v2.x" or "v2.x"
  ${COMPOSE_CMD} version 2>/dev/null | grep -Eq 'v2(\.|$)|Docker Compose version v2'
}

  wait_kc() {
    # Prefer realm well-known; if not present yet, at least wait for KC health
    if curl -fsS --max-time 3 "$kc_well_known" >/dev/null; then
      echo "✅ ${kc_realm} realm is reachable."
    else
      echo "ℹ️ ${kc_realm} realm not found yet; waiting on Keycloak health only."
      if command -v wait_for_url >/dev/null 2>&1; then
        wait_for_url "http://localhost:${kc_port}/health/ready" 180 || true
      fi
    fi
  }

  _in_list() {
    # _in_list <needle> <list...>
    local n="$1"; shift
    local x
    for x in "$@"; do [[ "$x" == "$n" ]] && return 0; done
    return 1
  }
  start_remaining() {
    # Determine all services and filter out infra + seed helpers
    local -a all rest exclude
    exclude=(kc_postgres keycloak kc-importer kc-verify kc-post-import)
    mapfile -t all < <(${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" config --services 2>/dev/null)
    local s
    for s in "${all[@]}"; do
      _in_list "$s" "${exclude[@]}" || rest+=("$s")
    done
    if [[ ${#rest[@]} -eq 0 ]]; then
      echo "ℹ️ No remaining services to start."
      return 0
    fi
    echo "▶️  Starting remaining services: ${rest[*]}"
    ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" up -d "${rest[@]}"
  }

  # Run
  case "$mode" in
    seed)

      echo "🐘 Bringing up kc_postgres…"
      ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" up -d kc_postgres || return 1
      wait_service_healthy kc_postgres || return 1

      echo "🔑 Running importer (must succeed)…"
      if compose_supports_profiles; then
        # v2 path — profiles supported
        ${COMPOSE_CMD} "${env_args[@]}" \
          --project-name "$COMPOSE_PROJECT_NAME" \
          -f "$compose_file" \
          --profile seed \
          up --no-deps --abort-on-container-exit --exit-code-from kc-importer kc-importer || return 1
      else
        # v1 path — no profiles; run the importer service explicitly
        ${COMPOSE_CMD} "${env_args[@]}" \
          --project-name "$COMPOSE_PROJECT_NAME" \
          -f "$compose_file" \
          up --no-deps --abort-on-container-exit --exit-code-from kc-importer kc-importer || return 1
      fi

      echo "▶️  Starting keycloak…"
      ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" up -d keycloak || return 1
      wait_kc

      echo "▶️  Running kc-post-import…"
      if compose_supports_profiles; then
        ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" --profile seed up --no-deps kc-post-import || true
      else
        ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" up --no-deps kc-post-import || true
      fi
      ;;
    infra)
      echo "▶️  Bringing infra only (kc_postgres + keycloak)…"
      ${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" up -d kc_postgres keycloak || return 1
      wait_kc
      ;;
    rest)
      echo "▶️  Spinning up remaining services…"
      start_remaining || return 1
      ;;
  esac
}

# Wait for a service with a Docker healthcheck to become healthy
wait_service_healthy() {
  local service="$1"
  local cid
  # Get the container id for this compose service
  cid="$(${COMPOSE_CMD} "${env_args[@]}" --project-name "$COMPOSE_PROJECT_NAME" -f "$compose_file" ps -q "$service")"
  if [[ -z "$cid" ]]; then
    echo "❌ Could not find container for service '$service'."
    return 1
  fi

  echo "⏳ Waiting for $service to become healthy…"
  # Poll health status (fallback to 'running' if no healthcheck is defined)
  local status tries=0
  while true; do
    status="$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || true)"
    case "$status" in
      healthy) echo "✅ $service is healthy."; return 0 ;;
      running|starting) ;;
      exited|dead) echo "❌ $service is not running (status: $status)."; return 1 ;;
      *) ;; # keep waiting on unknown/empty
    esac

    ((tries++))
    if (( tries > 120 )); then
      echo "⚠️  Timed out waiting for $service to become healthy."
      return 1
    fi
    sleep 1
  done
}

ensure_realm_python_deps() {
  local req_file="${REALM_REQUIREMENTS_FILE:-requirements/realm.txt}"

  if [[ ! -f "$req_file" ]]; then
    echo "ℹ️  No requirements file found at '$req_file'. Skipping dependency check."
    return 0
  fi

  echo "Realm Python dependencies file: $req_file"
  read -r -p "Do you want to install these Python dependencies? [y/N] " choice
  choice="${choice:-N}"

  if [[ ! "$choice" =~ ^[Yy]$ ]]; then
    echo "ℹ️  Skipping Python dependency installation."
    return 0
  fi

  # Ensure python + pip are available
  if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Python3 is required but not found."
    return 1
  fi

  if ! python3 -m pip --version >/dev/null 2>&1; then
    echo "❌ pip is required but not found for python3."
    return 1
  fi

  echo "📦 Installing dependencies from $req_file..."
  if ! python3 -m pip install --upgrade pip; then
    echo "⚠️  Could not upgrade pip, continuing anyway."
  fi

  if ! python3 -m pip install -r "$req_file"; then
    echo "❌ Failed to install dependencies."
    return 1
  fi

  echo "✅ Python dependencies installed."
}

ensure_compose_network() {
  # Ensures the Compose-managed network has the expected compose label.
  # Derives the runtime network name as "${COMPOSE_PROJECT_NAME:-osss}_${1:-osss-net}"
  local net_key="${1:-osss-net}"
  local project="${COMPOSE_PROJECT_NAME:-osss}"
  local net_runtime="${project}_${net_key}"

  if docker network inspect "$net_runtime" >/dev/null 2>&1; then
    # Read the compose label value (may be empty if created manually)
    local label
    label="$(docker network inspect -f '{{ index .Labels "com.docker.compose.network" }}' "$net_runtime" 2>/dev/null || true)"
    if [[ "$label" != "$net_key" ]]; then
      # Only safe to remove if nothing is attached
      local attached
      attached="$(docker network inspect -f '{{len .Containers}}' "$net_runtime" 2>/dev/null || echo 0)"
      if (( attached > 0 )); then
        echo "❌ Network '$net_runtime' has $attached attached container(s). Stop/disconnect them, or mark the network external in compose." >&2
        return 1
      fi
      echo "🧹 Removing stale network '$net_runtime' (label='$label', expected='$net_key')…"
      docker network rm "$net_runtime" || return 1
      echo "✅ Removed. Compose will recreate it correctly."
    fi
  fi
}


# --- Config & defaults ---
COMPOSE_FILE="${FK_COMPOSE_FILE:-${REPO_ROOT}/docker-compose.yml}"
BOOT_WAIT="${FK_BOOT_WAIT:-600}"
OIDC_DISCOVERY="${FK_OIDC_URL:-http://localhost:8085/realms/OSSS/.well-known/openid-configuration}"

API_MODULE="${API_MODULE:-src.OSSS.main:app}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8081}"

# Realm build
SKIP_REALM_BUILD="${SKIP_REALM_BUILD:-0}"
REALM_BUILDER="${REALM_BUILDER:-${REPO_ROOT}/build_realm.py}"

REALM_SPLITTER="${REALM_SPLITTER:-${REPO_ROOT}/build_split_realm.py}"
REALM_EXPORT="${REALM_EXPORT:-${REPO_ROOT}/OSSS-realm.json}"
if [[ "${SKIP_REALM_BUILD}" != "1" && ! -f "${REALM_BUILDER}" ]]; then
  echo "⚠️  build_realm.py not found at: ${REALM_BUILDER} — skipping realm build (set SKIP_REALM_BUILD=0 and fix path to enable)."
  SKIP_REALM_BUILD=1
fi

# Web
OSSS_WEB_DIR="${OSSS_WEB_DIR:-${REPO_ROOT}/src/osss-web}"
OSSS_WEB_PORT="${OSSS_WEB_PORT:-3000}"
OSSS_WEB_INSTALL="${OSSS_WEB_INSTALL:-0}"

# -------- Keycloak / OIDC general --------
KEYCLOAK_BASE_URL="${KEYCLOAK_BASE_URL:-http://localhost:8085}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-OSSS}"
KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-osss-api}"
KEYCLOAK_CLIENT_SECRET="$(sanitize_secret "${KEYCLOAK_CLIENT_SECRET:-password}")"
KEYCLOAK_ADMIN="${KEYCLOAK_ADMIN:-admin}"
KEYCLOAK_ADMIN_PASSWORD="$(sanitize_secret "${KEYCLOAK_ADMIN_PASSWORD:-admin}")"


# Keycloak realm/URL used to detect init status
KC_REALM="${KC_REALM:-OSSS}"
KEYCLOAK_HTTP="${KEYCLOAK_HTTP:-http://localhost:8085}"  # external URL per your compose ports

# Marker to remember we've completed kc-init
STATE_DIR="${STATE_DIR:-.state}"
KC_MARKER="${KC_MARKER:-${STATE_DIR}/kc_init_done}"

# --- Ensure ENV_FILE and COMPOSE_FILE point to files ---
if [ -n "${ENV_FILE:-}" ] && [ ! -f "$ENV_FILE" ]; then
  echo "⚠️  ENV_FILE points to '$ENV_FILE' but it does not exist or is not a file."
  echo "   → Falling back to skipping --env-file"
  unset ENV_FILE
fi

if [ -n "${COMPOSE_FILE:-}" ] && [ ! -f "$COMPOSE_FILE" ]; then
  echo "❌ COMPOSE_FILE points to '$COMPOSE_FILE' but no file found."
  echo "   Please create $COMPOSE_FILE or export FK_COMPOSE_FILE to the correct path."
  exit 1
fi

# Ensure localhost can resolve "keycloak" hostname for OIDC callbacks/tools.
if ! grep -qE '^[[:space:]]*127\.0\.0\.1[[:space:]].*\bkeycloak\b' /etc/hosts; then
  echo "🖇️  Adding 'keycloak' to /etc/hosts (requires sudo)"
  sudo sh -c 'echo "127.0.0.1 keycloak" >> /etc/hosts'
else
  echo "✅ /etc/hosts already contains 'keycloak'"
fi

# one-time: make sure the cert directory exists and is writable
sudo mkdir -p /etc/osss/certs
sudo chown "$(id -u)":"$(id -g)" /etc/osss/certs

### --- Local HTTPS / mkcert ---
ENABLE_LOCAL_TLS="${ENABLE_LOCAL_TLS:-0}"
TLS_DOMAIN_LIST="${TLS_DOMAIN_LIST:-localhost 127.0.0.1 ::1}"
TLS_CERT_DIR="${TLS_CERT_DIR:-/etc/osss/certs}"
TLS_CERT_FILE="${TLS_CERT_FILE:-${TLS_CERT_DIR}/fullchain.pem}"
TLS_KEY_FILE="${TLS_KEY_FILE:-${TLS_CERT_DIR}/privkey.pem}"
TRUST_STORES=${TRUST_STORES:-system}

# --- Redis ----
REDIS_TOKEN="${REDIS_TOKEN:-LoG1W0PtrKylYyQkSsk4FUcukhymnchrsjGLToF0U}"
REDIS_USER="${REDIS_USER:-appuser}"
REDIS_VERSION="${REDIS_VERSION:-'-7-alpine'}"

# -------- Keycloak DB (kc_postgres) --------
KC_DB_NAME="${KC_DB_NAME:-keycloak}"
KC_DB_USERNAME="${KC_DB_USERNAME:-keycloak}"
KC_DB_PASSWORD="$(sanitize_secret "${KC_DB_PASSWORD:-keycloakpass}")"
KC_DB_HOST="${KC_DB_HOST:-kc_postgres}"
KC_DB_PORT="${KC_DB_PORT:-5434}"

# -------- OSSS App DB (osss_postgres) --------
OSSS_DB_HOST="${OSSS_DB_HOST:-osss_postgres}"
OSSS_DB_PORT="${OSSS_DB_PORT:-5433}"
OSSS_DB_NAME="${OSSS_DB_NAME:-osss}"
OSSS_DB_USER="${OSSS_DB_USER:-osss}"
OSSS_DB_PASSWORD="$(sanitize_secret "${OSSS_DB_PASSWORD:-password}")"

# Build DATABASE_URL (async) if not provided
DATABASE_URL="${DATABASE_URL:-${OSSS_DATABASE_URL:-}}"
DATABASE_URL="${DATABASE_URL:-${OSSS_DB_URL:-}}"
if [[ -z "${DATABASE_URL}" ]]; then
  enc_user="$(url_quote "${OSSS_DB_USER}")"
  enc_pass="$(url_quote "${OSSS_DB_PASSWORD}")"
  DATABASE_URL="postgresql+asyncpg://${enc_user}:${enc_pass}@${OSSS_DB_HOST}:${OSSS_DB_PORT}/${OSSS_DB_NAME}"
fi

# Alembic (sync) URL default = psycopg2 variant of DATABASE_URL
ALEMBIC_DATABASE_URL="${ALEMBIC_DATABASE_URL:-${DATABASE_URL/postgresql+asyncpg/postgresql+psycopg2}}"
CALLBACK_URL="${CALLBACK_URL:-http://localhost:8081/callback}"

ALEMBIC_INI="${ALEMBIC_INI:-${REPO_ROOT}/alembic.ini}"
ALEMBIC_CMD="${ALEMBIC_CMD:-alembic}"

export PYTHONPATH="${PYTHONPATH:-${REPO_ROOT}/src}"

# Compose: pass .env explicitly
COMPOSE_ENV_ARGS=()
[[ -f "$ENV_FILE" ]] && COMPOSE_ENV_ARGS+=(--env-file "$ENV_FILE")

# Also export the exact names docker-compose typically references
export KC_DB_NAME KC_DB_USERNAME KC_DB_PASSWORD KC_DB_HOST KC_DB_PORT
export POSTGRES_DB="${OSSS_DB_NAME}"
export POSTGRES_USER="${OSSS_DB_USER}"
export POSTGRES_PASSWORD="${OSSS_DB_PASSWORD}"

### --- Pretty print selected environment ---
print_env_summary() {
  cat <<EOF

==================== ENVIRONMENT SUMMARY ====================
ENV_FILE            : ${ENV_FILE}
COMPOSE_FILE        : ${COMPOSE_FILE}
COMPOSE_ENV_FILE    : $( [[ -f "$ENV_FILE" ]] && echo "$ENV_FILE" || echo "(none)" )

# API
API_MODULE          : ${API_MODULE}
API_HOST            : ${API_HOST}
API_PORT            : ${API_PORT}
CALLBACK_URL        : ${CALLBACK_URL}

# WEB
OSSS_WEB_DIR        : ${OSSS_WEB_DIR}
OSSS_WEB_PORT       : ${OSSS_WEB_PORT}
OSSS_API_URL        : http://${API_HOST}:${API_PORT}

# KEYCLOAK
KEYCLOAK_BASE_URL   : ${KEYCLOAK_BASE_URL}
KEYCLOAK_REALM      : ${KEYCLOAK_REALM}
KEYCLOAK_CLIENT_ID  : ${KEYCLOAK_CLIENT_ID}
KEYCLOAK_SECRET     : $(mask "${KEYCLOAK_CLIENT_SECRET}")
KEYCLOAK_ADMIN      : ${KEYCLOAK_ADMIN}
KEYCLOAK_ADMIN_PW   : $(mask "${KEYCLOAK_ADMIN_PASSWORD}")

# KEYCLOAK DB
KC_DB_URL           : jdbc:postgresql://${KC_DB_HOST}:${KC_DB_PORT}/${KC_DB_NAME}
KC_DB_NAME          : ${KC_DB_NAME}
KC_DB_USERNAME      : ${KC_DB_USERNAME}
KC_DB_PASSWORD      : $(mask "${KC_DB_PASSWORD}")
KC_DB_HOST:PORT     : ${KC_DB_HOST}:${KC_DB_PORT}

# OSSS DATABASE
OSSS_DB_HOST        : ${OSSS_DB_HOST}
OSSS_DB_PORT        : ${OSSS_DB_PORT}
OSSS_DB_NAME        : ${OSSS_DB_NAME}
OSSS_DB_USER        : ${OSSS_DB_USER}
OSSS_DB_PASSWORD    : $(mask "${OSSS_DB_PASSWORD}")
DATABASE_URL        : ${DATABASE_URL}
ALEMBIC_DATABASE_URL: ${ALEMBIC_DATABASE_URL}

# OIDC & boot
OIDC_DISCOVERY      : ${OIDC_DISCOVERY}
BOOT_WAIT           : ${BOOT_WAIT}s

# TLS (local)
ENABLE_LOCAL_TLS    : ${ENABLE_LOCAL_TLS}
TLS_CERT_FILE       : ${TLS_CERT_FILE}
TLS_KEY_FILE        : ${TLS_KEY_FILE}
TLS_DOMAIN_LIST     : ${TLS_DOMAIN_LIST}
=============================================================

EOF
}
print_env_summary

ensure_realm_python_deps

install_python_requirements

echo "build keycloak realm before infrastructure"
build_realm_before_infra


maybe_build_images
ensure_compose_network
start_infra_with_kc_prompts

exit 0