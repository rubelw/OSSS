#!/usr/bin/env bash
set -euo pipefail

# --- Locations ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if REPO_ROOT_GIT="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel 2>/dev/null)"; then
  REPO_ROOT="$REPO_ROOT_GIT"
else
  REPO_ROOT="$SCRIPT_DIR"
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

resolve_python() { command -v python >/dev/null 2>&1 && { echo "python"; return; }
                   command -v python3 >/dev/null 2>&1 && { echo "python3"; return; }
                   echo "❌ Python not found on PATH" >&2; exit 1; }
resolve_npm()    { command -v npm >/dev/null 2>&1 && { echo "npm"; return; }
                   echo "❌ npm not found on PATH. Install Node.js/npm." >&2; exit 1; }

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
    if ${COMPOSE_CMD} "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" exec -T "$svc" pg_isready -q >/dev/null 2>&1; then
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
  if ! ${COMPOSE_CMD} "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" exec -T -e PGPASSWORD="$su_pw" "$svc" \
        psql -U "$su" -d postgres -c "select 1" >/dev/null 2>&1; then
    if ! ${COMPOSE_CMD} "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" exec -T "$svc" \
          psql -U "$su" -d postgres -c "select 1" >/dev/null 2>&1; then
      echo "❌ Could not connect to $svc as '$su'." >&2; return 1
    fi
  fi

  # Pre-escape values
  local L_USER L_PASS L_DB
  L_USER=$(sql_escape_literal "$app_user")
  L_PASS=$(sql_escape_literal "$app_password")
  L_DB=$(sql_escape_literal "$app_db")

  ${COMPOSE_CMD} "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" exec -T -e PGPASSWORD="$su_pw" "$svc" \
    psql -X -v ON_ERROR_STOP=1 -U "$su" -d postgres -f - <<SQL
DO \$do\$
DECLARE
  v_user text := ${L_USER};
  v_pass text := ${L_PASS};
  v_db   text := ${L_DB};
BEGIN
  -- Always (re)apply the password to avoid stale/CRLF'd secrets
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_user) THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', v_user, v_pass);
  ELSE
    EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', v_user, v_pass);
  END IF;

  -- DB
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

# --- Config & defaults ---
COMPOSE_FILE="${FK_COMPOSE_FILE:-${REPO_ROOT}/docker-compose.yml}"
BOOT_WAIT="${FK_BOOT_WAIT:-90}"
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

# Alembic settings
ALEMBIC_INI="${ALEMBIC_INI:-${REPO_ROOT}/alembic.ini}"
ALEMBIC_CMD="${ALEMBIC_CMD:-alembic}"

# Ensure FastAPI project sources are importable
export PYTHONPATH="${PYTHONPATH:-${REPO_ROOT}/src}"

# Compose: pass .env explicitly
COMPOSE_ENV_ARGS=()
[[ -f "$ENV_FILE" ]] && COMPOSE_ENV_ARGS+=(--env-file "$ENV_FILE")

### --- Also export the exact names docker-compose typically references ---
export KC_DB_NAME KC_DB_USERNAME KC_DB_PASSWORD KC_DB_HOST KC_DB_PORT

# IMPORTANT: sanitize the cluster bootstrap creds for osss_postgres too
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
=============================================================

EOF
}
print_env_summary

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

COMPOSE_CMD=$(compose_base_cmd)
echo "▶️  Bringing up infra with: ${COMPOSE_CMD} ${COMPOSE_ENV_ARGS[*]:-} -f ${COMPOSE_FILE} up -d"
if ! ${COMPOSE_CMD} "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" up -d; then
  echo "❌ docker compose up failed" >&2; exit 1
fi

# --- Ensure both DBs have correct users/passwords (sanitized) ---
wait_for_pg_service osss_postgres
ensure_role_and_db osss_postgres \
  "$OSSS_DB_USER" "$OSSS_DB_PASSWORD" "$OSSS_DB_NAME" \
  "$POSTGRES_USER" "$POSTGRES_PASSWORD"

wait_for_pg_service kc_postgres
ensure_role_and_db kc_postgres \
  "$KC_DB_USERNAME" "$KC_DB_PASSWORD" "$KC_DB_NAME" \
  "$KC_DB_USERNAME" "$KC_DB_PASSWORD"

# Wait for Keycloak OIDC discovery
if ! wait_for_url "${OIDC_DISCOVERY}" "${BOOT_WAIT}"; then
  echo "❌ Keycloak did not become ready at: ${OIDC_DISCOVERY}" >&2
  echo "🔎 Recent logs:"; ${COMPOSE_CMD} "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" logs --tail=200 || true
  exit 1
fi

### --- Run Alembic migrations on OSSS Postgres ---
SYNC_DB_URL="${ALEMBIC_DATABASE_URL/postgresql+asyncpg/postgresql+psycopg2}"
SYNC_DB_URL="$(force_ipv4_localhost "$SYNC_DB_URL")"

# Use libpq env PW (no secret in URL)
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

### --- Force the API runtime DB URL (async) with sanitized secrets ---
RUNTIME_DB_HOST="127.0.0.1"
RUNTIME_DB_PORT="${OSSS_DB_PORT}"
RUNTIME_DB_NAME="${OSSS_DB_NAME}"
RUNTIME_DB_USER="${OSSS_DB_USER}"
RUNTIME_DB_PASSWORD="${OSSS_DB_PASSWORD}"

enc_user="$(url_quote "${RUNTIME_DB_USER}")"
enc_pass="$(url_quote "${RUNTIME_DB_PASSWORD}")"
export DATABASE_URL="postgresql+asyncpg://${enc_user}:${enc_pass}@${RUNTIME_DB_HOST}:${RUNTIME_DB_PORT}/${RUNTIME_DB_NAME}"
unset SQLALCHEMY_DATABASE_URL ALEMBIC_DATABASE_URL
echo "🔧 Runtime DB → ${RUNTIME_DB_USER}@${RUNTIME_DB_HOST}:${RUNTIME_DB_PORT}/${RUNTIME_DB_NAME} (password hidden)"

# --- Optional: asyncpg preflight (uncomment to hard-fail early) ---
: <<'ASYNC_PREFLIGHT'
PY="$(resolve_python)"
"$PY" - "$DATABASE_URL" <<'PYCODE'
import os, sys, asyncio, asyncpg
url = sys.argv[1].replace("postgresql+asyncpg", "postgresql")
async def main():
    conn = await asyncpg.connect(dsn=url, timeout=5)
    await conn.execute("SELECT 1")
    await conn.close()
print("✅ asyncpg preflight OK:", url.replace(url.split("@")[0], "****"))
asyncio.run(main())
PYCODE
ASYNC_PREFLIGHT

### --- Start FastAPI (uvicorn) ---
PY="$(resolve_python)"



if ! "${PY}" -c "import uvicorn" 2>/dev/null; then
  echo "❌ uvicorn not installed. Try: pip install uvicorn" >&2; exit 1
fi
echo "🚀 Starting FastAPI: uvicorn ${API_MODULE} --host ${API_HOST} --port ${API_PORT} --reload"
"${PY}" -m uvicorn "${API_MODULE}" --host "${API_HOST}" --port "${API_PORT}" --reload &
API_PID=$!

### --- Start Next.js (npm run dev) ---
NPM="$(resolve_npm)"
if [ ! -d "${OSSS_WEB_DIR}" ]; then
  echo "❌ OSSS web app directory not found: ${OSSS_WEB_DIR}" >&2
  echo "   Set OSSS_WEB_DIR=... to override." >&2
  kill "${API_PID}" 2>/dev/null || true; wait "${API_PID}" 2>/dev/null || true
  ${COMPOSE_CMD} "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" down -v || true
  exit 1
fi

pushd "${OSSS_WEB_DIR}" >/dev/null
if [ "${OSSS_WEB_INSTALL}" = "1" ] || [ ! -d "node_modules" ]; then
  echo "📦 Installing web dependencies (npm install)…"
  ${NPM} install
fi
export OSSS_API_URL="http://${API_HOST}:${API_PORT}"
echo "🕸  Starting osss-web: ${NPM} run dev (port ${OSSS_WEB_PORT})"
${NPM} run dev -- --port "${OSSS_WEB_PORT}" &
WEB_PID=$!
popd >/dev/null

wait_for_url "http://localhost:${OSSS_WEB_PORT}" 20 || true

### --- Cleanup on exit ---
cleanup() {
  echo ""
  echo "🧹 Stopping web (PID ${WEB_PID:-n/a})…";   [ -n "${WEB_PID:-}" ] && kill "${WEB_PID}" 2>/dev/null || true;   [ -n "${WEB_PID:-}" ] && wait "${WEB_PID}" 2>/dev/null || true
  echo "🧹 Stopping API (PID ${API_PID:-n/a})…";   [ -n "${API_PID:-}" ] && kill "${API_PID}" 2>/dev/null || true;   [ -n "${API_PID:-}" ] && wait "${API_PID}" 2>/dev/null || true
  echo "🛑 Tearing down infra (compose down -v)…"; ${COMPOSE_CMD} "${COMPOSE_ENV_ARGS[@]}" -f "${COMPOSE_FILE}" down -v || true
}
trap cleanup INT TERM EXIT

echo ""
echo "📎 OpenAPI docs:    http://${API_HOST}:${API_PORT}/docs"
echo "📎 OIDC discovery:  ${OIDC_DISCOVERY}"
echo "🌐 osss-web:        http://localhost:${OSSS_WEB_PORT}"
echo ""
echo "⌨️  Press Ctrl-C to stop everything…"
wait "${API_PID}"
