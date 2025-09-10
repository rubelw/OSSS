#!/usr/bin/env bash

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
    if "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" exec -T "$svc" pg_isready -q >/dev/null 2>&1; then
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
  if ! "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" exec -T -e PGPASSWORD="$su_pw" "$svc" \
        psql -U "$su" -d postgres -c "select 1" >/dev/null 2>&1; then
    if ! "${COMPOSE_CMD[@]}" "${COMPOSE_ARGS[@]}" -f "${COMPOSE_FILE}" exec -T "$svc" \
          psql -U "$su" -d postgres -c "select 1" >/dev/null 2>&1; then
      echo "❌ Could not connect to $svc as '$su'." >&2; return 1
    fi
  fi

  local L_USER L_PASS L_DB
  L_USER=$(sql_escape_literal "$app_user")
  L_PASS=$(sql_escape_literal "$app_password")
  L_DB=$(sql_escape_literal "$app_db")

  "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" exec -T -e PGPASSWORD="$su_pw" "$svc" \
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

ensure_realm_python_deps() {
  local py; py="$(resolve_python)"
  local need=()
  "$py" -c "import sqlalchemy"            2>/dev/null || need+=("SQLAlchemy>=2,<3")
  "$py" -c "import pydantic_settings"     2>/dev/null || need+=("pydantic-settings>=2,<3")
  "$py" -c "import pydantic"              2>/dev/null || need+=("pydantic>=2,<3")
  if ((${#need[@]})); then
    echo "📦 Installing missing realm deps: ${need[*]}"
    "$py" -m pip install --upgrade pip >/dev/null
    "$py" -m pip install "${need[@]}"
  else
    echo "✅ Realm Python deps already present."
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
REALM_EXPORT="${REALM_EXPORT:-${REPO_ROOT}/realm-export.json}"
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

# Ensure Python deps are present for build_realm.py
ensure_realm_python_deps
install_python_requirements

### --- Build realm-export.json BEFORE starting infra ---
if [ "${SKIP_REALM_BUILD}" != "1" ]; then
  if [ ! -f "${REALM_BUILDER}" ]; then
    echo "❌ REALM_BUILDER not found: ${REALM_BUILDER}" >&2
    echo "   Set SKIP_REALM_BUILD=1 to bypass this step." >&2
    exit 1
  fi
  PY="$(resolve_python)"
  echo "🧱 Building realm export via: ${PY} ${REALM_BUILDER}"
  if ! "${PY}" -u "${REALM_BUILDER}"; then
    echo "❌ build_realm.py failed" >&2; exit 1
  fi
  if [ ! -s "${REALM_EXPORT}" ]; then
    echo "❌ Realm export not found or empty at: ${REALM_EXPORT}" >&2; exit 1
  fi
  echo "✅ Realm export ready at: ${REALM_EXPORT}"
else
  echo "⚠️  SKIP_REALM_BUILD=1 set — skipping build_realm.py"
fi

### --- Start infra (Keycloak + both Postgres) ---
if [ ! -f "${COMPOSE_FILE}" ]; then
  echo "❌ Compose file not found: ${COMPOSE_FILE}" >&2; exit 1
fi

# Make COMPOSE_CMD an array for safety with spaces ("docker compose")
COMPOSE_CMD=($(compose_base_cmd))

# --- Optional image build step ---
if [[ $DO_BUILD -eq 1 ]]; then
  echo "🔧 Building docker images (infra) …"
  if [[ $NO_CACHE -eq 1 ]]; then
    echo "   ↳ Using --no-cache"
    "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" build --no-cache --progress=plain
  else
    "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" build --progress=plain
  fi
  echo "✅ Images built."
else
  echo "⏭️  Skipping 'compose build' (no --build/--rebuild flag provided)."
fi

echo "▶️  Bringing up infra with: ${COMPOSE_CMD_STR} ${COMPOSE_ENV_ARGS[*]:-} -f ${COMPOSE_FILE} up -d"

# First attempt (let Compose create the network itself)
set +e
"${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" up -d
rc=$?
set -e

if (( rc != 0 )); then
  echo "⚠️  'up -d' failed; performing a clean reset of the project network and retrying once…"

  # Tear everything for this project down (ignore errors)
  "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" down -v --remove-orphans || true

  # Remove any leftover networks for this project (they can be half-created)
  docker network rm "${NET}" 2>/dev/null || true
  docker network rm "${PROJECT}_default" 2>/dev/null || true
  docker network prune -f >/dev/null 2>&1 || true

  # Retry bringing everything up cleanly
  if ! "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" up -d; then
    echo "❌ docker compose up failed (after clean reset)"
    "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" ps || true
    exit 1
  fi
fi

echo "✅ Infra up."


# --- Ensure both DBs have correct users/passwords (sanitized) ---
wait_for_pg_service osss_postgres
ensure_role_and_db osss_postgres \
  "$OSSS_DB_USER" "$OSSS_DB_PASSWORD" "$OSSS_DB_NAME" \
  "$POSTGRES_USER" "$POSTGRES_PASSWORD"

wait_for_pg_service kc_postgres
ensure_role_and_db kc_postgres \
  "$KC_DB_USERNAME" "$KC_DB_PASSWORD" "$KC_DB_NAME" \
  "$KC_DB_USERNAME" "$KC_DB_PASSWORD"

echo "### Please wait at least 180 seconds for this to populate ###"

# Wait for Keycloak OIDC discovery
if ! wait_for_url "${OIDC_DISCOVERY}" "${BOOT_WAIT}"; then
  echo "❌ Keycloak did not become ready at: ${OIDC_DISCOVERY}" >&2
  echo "🔎 Recent logs:"; "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" logs --tail=200 || true
  exit 1
fi

### --- Run Alembic migrations on OSSS Postgres ---
SYNC_DB_URL="${ALEMBIC_DATABASE_URL/postgresql+asyncpg/postgresql+psycopg2}"
SYNC_DB_URL="$(force_ipv4_localhost "$SYNC_DB_URL")"

drop_password_in_url() { echo "$1" | sed -E 's#^(postgresql(\+[a-z0-9]+)?://[^:/@]+):[^@]*(@.*)$#\1\3#'; }
SYNC_DB_URL_NOPW="$(drop_password_in_url "$SYNC_DB_URL")"

echo "🧭 Alembic will use DB URL: ${SYNC_DB_URL}"
wait_for_db "${SYNC_DB_URL}" 90

echo "📜 Running Alembic migrations (upgrade head)…"
pushd "${REPO_ROOT}" >/dev/null
PGPASSWORD="${OSSS_DB_PASSWORD}" \
DATABASE_URL="${SYNC_DB_URL_NOPW}" \
SQLALCHEMY_DATABASE_URL="${SYNC_DB_URL_NOPW}" \
ALEMBIC_DATABASE_URL="${SYNC_DB_URL_NOPW}" \
  "${ALEMBIC_CMD}" -c "${ALEMBIC_INI}" -x echo=true -x log=DEBUG upgrade head
popd >/dev/null
echo "✅ Alembic migrations completed."

### --- Start app & web via Docker Compose ---
APP_PROFILE_FLAG="--profile app"
echo "▶️  Starting app & web containers with profile 'app'…"
if ! "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" ${APP_PROFILE_FLAG} up -d app web; then
  echo "❌ Failed to start app/web containers" >&2
  "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" logs --tail=200 app web || true
  exit 1
fi

# Wait for app (FastAPI) and web (Next.js) to be reachable on host ports
APP_PORT="${APP_PORT:-8081}"
WEB_PORT="${WEB_PORT:-3000}"
wait_for_url "http://localhost:${APP_PORT}" 120 || { echo "⚠️  app not responding yet on :${APP_PORT}"; }
wait_for_url "http://localhost:${WEB_PORT}" 120 || { echo "⚠️  web not responding yet on :${WEB_PORT}"; }
echo "✅ app/web reachable (or will be shortly)."

### --- Cleanup on exit ---
cleanup() {
  echo ""
  echo "🛑 Tearing down containers (compose down -v)…"
  "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" down -v --remove-orphans || true

  echo "🔎 Checking for containers still attached to ${NET}…"
  ATTACHED="$(docker network inspect "${NET}" --format '{{range .Containers}}{{println .Name}}{{end}}' 2>/dev/null || true)"

  if [ -n "${ATTACHED}" ]; then
    echo "⚠️  Detaching these containers from ${NET}:"
    echo "${ATTACHED}"
    while IFS= read -r cname; do
      [ -n "$cname" ] && docker network disconnect -f "${NET}" "$cname" || true
    done <<< "${ATTACHED}"
  fi

  echo "🧽 Removing network ${NET}…"
  for i in 1 2 3; do
    docker network rm "${NET}" && { echo "✅ Network removed."; break; }
    echo "   retry ${i}/3…"; sleep 1
  done
  docker network prune -f >/dev/null 2>&1 || true
}
trap cleanup INT TERM EXIT

# Host ports
FASTAPI_HOST_PORT="${FASTAPI_HOST_PORT:-8081}"  # host→container mapping 8081:8000
WEB_PORT="${WEB_PORT:-3000}"

wait_for_url "http://localhost:${FASTAPI_HOST_PORT}" 120 || {
  echo "⚠️  app not responding yet on :${FASTAPI_HOST_PORT}";
}
wait_for_url "http://localhost:${WEB_PORT}" 120 || {
  echo "⚠️  web not responding yet on :${WEB_PORT}";
}


echo ""
echo "📎 OpenAPI docs:    http://localhost:${APP_PORT}/docs"
echo "📎 OIDC discovery:  ${OIDC_DISCOVERY}"
echo "🌐 osss-web:        http://localhost:${WEB_PORT}"
echo "   osss:            http://localhost:8081/docs#/"
echo "   kibana:          http://localhost:5601"
echo "   consul:          http://localhost:8500"
echo "   vault:           http://localhost:8200"
echo ""
echo "⌨️  Press Ctrl-C to stop everything…"

# --- Stream FastAPI logs in foreground ---
"${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" logs -f app
# To also stream web logs, use:
# "${COMPOSE_CMD[@]}" "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" logs -f app web