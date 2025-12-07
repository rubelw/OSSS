#!/usr/bin/env bash
set -euo pipefail

log() { printf '%s %s\n' "[$(date '+%Y-%m-%dT%H:%M:%S%z')]" "$*" >&2; }

# Expected env:
#   POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB         (readiness only)
#   OSSS_DB_USER/OSSS_DB_PASSWORD/OSSS_DB_NAME          (main DB)
#   ASYNC_DATABASE_URL                                   (optional; we construct if missing)
#   ALEMBIC_DATABASE_URL                                 (we set to psycopg2 DSN)
#   HONOR_ALEMBIC_DATABASE_URL=1                         (optional)
#   -- Tutor DB (one of) --
#   TUTOR_DB_URL | TUTOR_DATABASE_URL | OSSS_TUTOR_DB_{USER,PASSWORD,HOST,PORT,NAME}

PGHOST="${PGHOST:-osss_postgres}"
PGPORT="${PGPORT:-5432}"

# Paths to your migration roots and (expected) alembic.ini files inside the container
MAIN_MIGR_DIR="/workspace/src/OSSS/db/migrations"
MAIN_INI_PATH="${MAIN_MIGR_DIR}/alembic.ini"

TUTOR_MIGR_DIR="/workspace/src/OSSS/db_tutor"
TUTOR_INI_PATH="${TUTOR_MIGR_DIR}/alembic.ini"

APP_USER="${OSSS_DB_USER:?OSSS_DB_USER not set}"
APP_DB="${OSSS_DB_NAME:?OSSS_DB_NAME not set}"

# ---------------- helpers: ini detection / creation ----------------
# We generate a minimal alembic.ini if missing or if it lacks script_location
ensure_alembic_ini() {
  local migr_dir="$1"
  local ini_path="$2"
  local label="$3"   # "main" or "tutor"

  if [[ -f "$ini_path" ]] && grep -Eq '^\s*script_location\s*=' "$ini_path"; then
    # looks good
    return 0
  fi

  log "[$label] creating minimal alembic.ini at: ${ini_path}"
  mkdir -p "$(dirname "$ini_path")"
  cat >"$ini_path" <<EOF
[alembic]
script_location = ${migr_dir}
sqlalchemy.url = postgresql://placeholder/placeholder

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers = console
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers = console
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
EOF
}

# ---------------- Resolve & normalize MAIN DB password ----------------
RAW_PASS=""
if [[ -z "${RAW_PASS}" && -n "${OSSS_DB_PASSWORD_FILE:-}" && -r "${OSSS_DB_PASSWORD_FILE}" ]]; then
  RAW_PASS="$(cat -- "${OSSS_DB_PASSWORD_FILE}")"
fi
if [[ -z "${RAW_PASS}" && -n "${OSSS_DB_PASSWORD:-}" ]]; then
  RAW_PASS="${OSSS_DB_PASSWORD}"
fi
if [[ -z "${RAW_PASS}" && -n "${ASYNC_DATABASE_URL:-}" ]]; then
  RAW_PASS="$(python - <<'PY' "$ASYNC_DATABASE_URL"
import sys, urllib.parse as up
u=sys.argv[1].strip(); print(up.urlparse(u).password or "")
PY
)"
fi
if [[ -z "${RAW_PASS}" && -n "${ALEMBIC_DATABASE_URL:-}" ]]; then
  RAW_PASS="$(python - <<'PY' "$ALEMBIC_DATABASE_URL"
import sys, urllib.parse as up
u=sys.argv[1].strip(); print(up.urlparse(u).password or "")
PY
)"
fi

log "RAW_PASSWORD='${RAW_PASS}'"
if [[ -z "${RAW_PASS}" ]]; then
  log "FATAL: OSSS_DB_PASSWORD is unset/empty (after resolving env/_FILE/URLs)."; exit 1
fi

NORM_PASS="$(printf %s "${RAW_PASS}" | tr -d '\r\n')"
log "NORM_PASS='${NORM_PASS}'"
if [[ -z "${NORM_PASS}" ]]; then
  log "FATAL: OSSS_DB_PASSWORD is empty after normalization (newline-only)."; exit 1
fi

export OSSS_DB_PASSWORD="${NORM_PASS}"
APP_PASS="${NORM_PASS}"

export PGPASSFILE="/dev/null"
export PGSSLMODE="disable"

# ---------------- URL-encode password and construct MAIN DSNs ----------------
ENC_PASS="$(python - <<'PY' "$NORM_PASS"
import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))
PY
)"
SYNC_DSN="postgresql+psycopg2://${APP_USER}:${ENC_PASS}@${PGHOST}:${PGPORT}/${APP_DB}?sslmode=disable"
ASYNC_DSN="postgresql+asyncpg://${APP_USER}:${ENC_PASS}@${PGHOST}:${PGPORT}/${APP_DB}"

export ASYNC_DATABASE_URL="${ASYNC_DATABASE_URL:-$ASYNC_DSN}"

alembic_src="constructed from OSSS_DB_*"
if [[ "${HONOR_ALEMBIC_DATABASE_URL:-}" =~ ^(1|true|TRUE|yes|YES)$ && -n "${ALEMBIC_DATABASE_URL:-}" ]]; then
  ALEMBIC_DATABASE_URL="$(
    python - <<'PY' "$ALEMBIC_DATABASE_URL"
import sys, urllib.parse as up
from sqlalchemy.engine.url import make_url
raw=sys.argv[1].strip(); u=make_url(raw)
if u.get_backend_name()=="postgresql" and u.get_driver_name()!="psycopg2":
    u=u.set(drivername="postgresql+psycopg2")
if "sslmode" not in (u.query or {}):
    u=u.update_query_dict({"sslmode":["disable"]})
user=u.username or ""; pw=u.password or ""; host=u.host or "localhost"; port=u.port or 5432; db=(u.database or "").lstrip("/")
q=u.query or {}; enc_pw=up.quote(pw, safe="")
qstr=up.urlencode({k:(v[0] if isinstance(v,(list,tuple)) else v) for k,v in q.items()}, doseq=False)
print(f"postgresql+psycopg2://{user}:{enc_pw}@{host}:{port}/{db}"+(f"?{qstr}" if qstr else ""))
PY
  )"
  alembic_src="ALEMBIC_DATABASE_URL (honored+encoded)"
else
  ALEMBIC_DATABASE_URL="$SYNC_DSN"
  alembic_src="constructed from OSSS_DB_* (encoded)"
fi
export ALEMBIC_DATABASE_URL

# ---------------- Diagnostics helpers ----------------
_hex_preview() {
  python - <<'PY'
import sys, binascii
s=sys.stdin.buffer.read(); n=len(s); h=binascii.hexlify(s).decode("ascii")
print("len=0, hex=" if n==0 else (f"len={n}, hex={h}" if n<=6 else f"len={n}, hex={h[:12]}…{h[-12:]}"))
PY
}
_urlencode_pw() { python - <<'PY'
import os, urllib.parse; print(urllib.parse.quote_plus(os.getenv("PW",""), safe=""))
PY
}
dump_env_summary() {
  log "ENV summary:"
  log "  PGHOST='${PGHOST}'  PGPORT='${PGPORT}'"
  log "  APP_USER='${APP_USER}'  APP_DB='${APP_DB}'"
  if [[ -n "${ALEMBIC_DATABASE_URL:-}" ]]; then
    log "  ALEMBIC_DATABASE_URL is set: ${ALEMBIC_DATABASE_URL}"
    log "  ALEMBIC effective URL source=${alembic_src}"
  else
    log "  ALEMBIC_DATABASE_URL is not set"
  fi
  if [[ -n "${ASYNC_DATABASE_URL:-}" ]]; then
    log "  ASYNC_DATABASE_URL is set: ${ASYNC_DATABASE_URL}"
  else
    log "  ASYNC_DATABASE_URL is not set"
  fi
}
dump_password_diagnostics() {
  log "Password diagnostics for user '${APP_USER}':"
  if [[ -z "${RAW_PASS}" ]]; then log "  value: <EMPTY>"; return; fi
  [[ "${RAW_PASS}" = " "* ]] && log "  leading-space: YES"  || log "  leading-space: NO"
  [[ "${RAW_PASS}" = *" " ]] && log "  trailing-space: YES" || log "  trailing-space: NO"
  if printf %s "$RAW_PASS" | grep -q $'\r'; then log "  contains-CR: YES (\\r found)"; else log "  contains-CR: NO"; fi
  if printf %s "$RAW_PASS" | grep -q $'\n'; then log "  contains-LF: YES (\\n found)"; else log "  contains-LF: NO"; fi
  raw_preview="$(printf %s "$RAW_PASS"  | _hex_preview)"
  norm_preview="$(printf %s "$NORM_PASS" | _hex_preview)"
  log "  RAW  ${raw_preview}"
  log "  NORM ${norm_preview}"
  PW="$NORM_PASS"; export PW
  enc="$(_urlencode_pw)"
  [[ "$enc" == "$NORM_PASS" ]] && log "  urlencoded(norm): <unchanged>" || log "  urlencoded(norm): '${enc}'"
}

# ---------------- Tutor DB URL build + helpers ----------------
normalize_psycopg2() {
  local url="${1:-}"; [[ -z "$url" ]] && { echo ""; return 0; }
  url="${url/postgresql+asyncpg:/postgresql+psycopg2:}"
  url="${url/postgresql+psycopg:/postgresql+psycopg2:}"
  echo "$url"
}
rewrite_localhost_to_service() {
  local url="${1:-}" svc="${2:-tutor-db}" sport="${3:-5432}"
  [[ -z "$url" ]] && { echo ""; return 0; }
  python - "$url" "$svc" "$sport" <<'PY'
import sys
from urllib.parse import urlsplit, urlunsplit
u = urlsplit(sys.argv[1]); svc = sys.argv[2]; sport = sys.argv[3]
host = (u.hostname or "").lower()
if host in ("localhost","127.0.0.1"):
    # replace hostname and force port
    netloc = f"{svc}:{sport}"
    if u.username:
        from urllib.parse import quote
        pwd = (u.password or "")
        auth = f"{u.username}:{quote(pwd, safe='')}"
        netloc = f"{auth}@{netloc}"
    u = u._replace(netloc=netloc)
print(urlunsplit(u))
PY
}

TUTOR_URL_RAW="${TUTOR_DB_URL:-${TUTOR_DATABASE_URL:-}}"
if [[ -z "$TUTOR_URL_RAW" && -n "${OSSS_TUTOR_DB_USER:-}" ]]; then
  TUTOR_HOST="${OSSS_TUTOR_DB_HOST:-tutor-db}"
  TUTOR_PORT="${OSSS_TUTOR_DB_PORT:-5432}"
  TUTOR_NAME="${OSSS_TUTOR_DB_NAME:-tutor-db}"
  TUTOR_PASS_ENC="$(python - <<'PY'
import os, urllib.parse
pw=os.getenv("OSSS_TUTOR_DB_PASSWORD","password")
print(urllib.parse.quote(pw, safe=""))
PY
)"
  TUTOR_URL_RAW="postgresql+psycopg2://${OSSS_TUTOR_DB_USER}:${TUTOR_PASS_ENC}@${TUTOR_HOST}:${TUTOR_PORT}/${TUTOR_NAME}?sslmode=disable"
fi
TUTOR_URL="$(normalize_psycopg2 "$TUTOR_URL_RAW")"
TUTOR_URL="$(rewrite_localhost_to_service "$TUTOR_URL" "tutor-db" "5432")"

parse_host_port_from_url() {
  python - <<'PY' "$1"
import sys
from urllib.parse import urlsplit
u=urlsplit(sys.argv[1]); host=u.hostname or ""; port=u.port or 5432
print(f"{host} {port}", end="")
PY
}

wait_for_pg() {
  local host="$1" port="$2"
  [[ -z "$host" || -z "$port" ]] && { log "wait_for_pg: empty host/port"; exit 1; }
  log "waiting for Postgres at ${host}:${port}…"
  for _ in {1..120}; do
    if timeout 1 bash -lc "</dev/tcp/${host}/${port}" 2>/dev/null; then
      log "Postgres is accepting connections."
      return 0
    fi
    sleep 1
  done
  log "Postgres did not become ready in time at ${host}:${port}."; exit 1
}

# ---------------- Core MAIN steps ----------------
sanity_check_app_creds() {
  log "sanity check (auth): connect as '${APP_USER}' to '${APP_DB}' with password…"
  if ! PGPASSWORD="$APP_PASS" psql "host=$PGHOST port=$PGPORT dbname=$APP_DB user=$APP_USER sslmode=disable" \
        -v ON_ERROR_STOP=1 -Atqc 'SELECT 1;' >/dev/null 2>&1; then
    log "ERROR: psql cannot authenticate to '${APP_DB}' as '${APP_USER}'."
    dump_env_summary; dump_password_diagnostics
    log "psql verbose attempt:"
    PGPASSWORD="$APP_PASS" psql "host=$PGHOST port=$PGPORT dbname=$APP_DB user=$APP_USER sslmode=disable" \
      -v VERBOSITY=verbose -c "SELECT current_user, current_database();"
    exit 1
  fi
  log "sanity check OK (passworded auth)."
}

probe_alembic_url_and_connect() {
  log "ALEMBIC_DATABASE_URL=${ALEMBIC_DATABASE_URL}"
  python - <<'PY'
import os, sys, urllib.parse as up
try:
    import psycopg2
except Exception as e:
    print("[alembic-probe] FAIL: psycopg2 not installed -", e); sys.exit(12)
url=os.environ["ALEMBIC_DATABASE_URL"]
norm=url.replace("postgresql+psycopg2://","postgresql://",1)
p=up.urlsplit(norm); q=dict((k,v[0]) for k,v in up.parse_qs(p.query).items())
host=p.hostname or "localhost"; port=p.port or 5432
user=up.unquote(p.username or ""); pwd=up.unquote(p.password or "")
db=p.path.lstrip("/") or None; sslmode=q.get("sslmode","disable")
try:
    conn = psycopg2.connect(host=host, port=port, user=user, password=pwd, dbname=db, sslmode=sslmode)
    cur=conn.cursor(); cur.execute("SELECT current_user, current_database()"); cur.close(); conn.close()
    print("[alembic-probe] OK")
except Exception as e:
    print("[alembic-probe] FAIL:", type(e).__name__, "-", e); sys.exit(12)
PY
}

# If ini missing/invalid, create it before running alembic.
prepare_main_ini()   { ensure_alembic_ini "$MAIN_MIGR_DIR"  "$MAIN_INI_PATH"  "main"; }
prepare_tutor_ini()  { ensure_alembic_ini "$TUTOR_MIGR_DIR" "$TUTOR_INI_PATH" "tutor"; }

maybe_run_alembic() {
  [[ -n "${SKIP_ALEMBIC:-}" ]] && { log "SKIP_ALEMBIC set; skipping migrations."; return 0; }

  # Ensure ini exists and has script_location
  prepare_main_ini

  probe_alembic_url_and_connect
  log "running Alembic migrations (main)…"
  # Use 'heads' to handle multi-head branches without failing hard.
  if ! env \
      DATABASE_URL="$ALEMBIC_DATABASE_URL" \
      SQLALCHEMY_DATABASE_URI="$ALEMBIC_DATABASE_URL" \
      SQLALCHEMY_URL="$ALEMBIC_DATABASE_URL" \
      alembic -c "$MAIN_INI_PATH" -x sqlalchemy_url="$ALEMBIC_DATABASE_URL" upgrade heads; then
    log "Alembic upgrade (main) failed; diagnostics:"; dump_env_summary; dump_password_diagnostics; exit 14
  fi
  log "alembic migrations (main) complete."
}

maybe_run_tutor_alembic() {
  [[ -n "${SKIP_ALEMBIC:-}" ]] && { log "SKIP_ALEMBIC set; skipping tutor migrations."; return 0; }
  [[ -z "${TUTOR_URL:-}" ]] &&  { log "TUTOR_URL not set; skipping tutor migrations."; return 0; }

  # Ensure ini exists and has script_location
  prepare_tutor_ini

  read -r T_HOST T_PORT <<<"$(parse_host_port_from_url "$TUTOR_URL")"
  [[ -n "$T_HOST" ]] && wait_for_pg "$T_HOST" "$T_PORT"

  log "running Alembic migrations (tutor)…"
  if ! alembic -c "$MAIN_INI_PATH" \
        -x sqlalchemy_url="$ALEMBIC_DATABASE_URL" \
        -x tutor_skip=1 \
        upgrade heads; then
    log "Alembic upgrade (tutor) failed."; exit 14
  fi
  log "alembic migrations (tutor) complete."
}

check_python_deps() {
  log "checking required Python packages…"
  python - <<'PY'
import importlib, sys
req=("httpx","prometheus_client","alembic")
missing=[]
for m in req:
    try: importlib.import_module(m)
    except Exception as e:
        print(f"[deps] MISSING: {m} -> {e}"); missing.append(m)
if missing: print("[deps] One or more required packages are missing:", ", ".join(missing)); sys.exit(23)
print("[deps] OK")
PY
}

check_fk_integrity() {
  log "checking FK integrity between work_orders.request_id -> maintenance_requests.id…"
  local sql="
    SELECT COUNT(*) AS broken
    FROM work_orders w
    LEFT JOIN maintenance_requests r ON r.id = w.request_id
    WHERE r.id IS NULL;
  "
  if ! broken=$(PGPASSWORD="$APP_PASS" psql "host=$PGHOST port=$PGPORT dbname=$APP_DB user=$APP_USER sslmode=disable" \
         -Atqc "$sql" 2>/dev/null); then
    log "WARN: could not run FK check (psql failed); continuing."; return 0
  fi
  if [[ "${broken}" != "0" ]]; then
    log "ERROR: ${broken} work_orders row(s) reference missing maintenance_requests."; exit 16
  fi
  log "FK check OK."
}

main() {
  dump_env_summary
  dump_password_diagnostics

  # MAIN postgres readiness + checks
  wait_for_pg "$PGHOST" "$PGPORT"
  sanity_check_app_creds
  check_python_deps

  # MAIN migrations
  maybe_run_alembic

  # TUTOR migrations (optional)
  #log "TUTOR_URL=${TUTOR_URL:-<empty>}"
  #if [[ -z "${SKIP_ALEMBIC:-}" ]]; then
  #  maybe_run_tutor_alembic
  #else
  #  log "SKIP_ALEMBIC set; not waiting for tutor DB."
  #fi

  #check_fk_integrity
  log "starting application: $*"
  unset DATABASE_URL SQLALCHEMY_DATABASE_URI SQLALCHEMY_URL

  python - <<'PY'
import os, asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def main():
    eng = create_async_engine(os.environ["ASYNC_DATABASE_URL"])
    async with eng.connect() as c:
        val = await c.scalar(text("SELECT 1"))
        print("[startup-check] async SELECT 1 ->", val)
asyncio.run(main())
PY

  if [[ $# -eq 0 ]]; then
    HOST="${HOST:-0.0.0.0}"; PORT="${PORT:-8000}"
    set -- uvicorn src.OSSS.main:app \
      --host "$HOST" --port "$PORT" \
      --reload \
      --reload-dir /workspace/src/OSSS \
      --log-level "${UVICORN_LOG_LEVEL:-info}" \
      --access-log \
      --log-config /workspace/docker/logging.yaml
  fi
  exec "$@"
}

main "$@"
