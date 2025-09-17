#!/usr/bin/env bash
set -euo pipefail

log() { printf '%s %s\n' "[$(date '+%Y-%m-%dT%H:%M:%S%z')]" "$*" >&2; }

# Expected env:
#   POSTGRES_USER/POSTGRES_PASSWORD/POSTGRES_DB   (readiness only)
#   OSSS_DB_USER/OSSS_DB_PASSWORD/OSSS_DB_NAME    (must already exist)
#   ASYNC_DATABASE_URL                             (runtime for app)  [optional; we will construct if missing]
#   ALEMBIC_DATABASE_URL                           (we will overwrite with encoded DSN unless HONOR...=1)
#   HONOR_ALEMBIC_DATABASE_URL=1                   (optional: honor existing and re-encode/normalize)

PGHOST="${PGHOST:-osss_postgres}"
PGPORT="${PGPORT:-5432}"

APP_USER="${OSSS_DB_USER:?OSSS_DB_USER not set}"
APP_DB="${OSSS_DB_NAME:?OSSS_DB_NAME not set}"

# -------- Resolve & normalize DB password (single source of truth) --------
# Priority: secret file > explicit env > parse from URLs (async, then alembic)
RAW_PASS=""

# 1) Secret file (Docker secrets)
if [[ -z "${RAW_PASS}" && -n "${OSSS_DB_PASSWORD_FILE:-}" && -r "${OSSS_DB_PASSWORD_FILE}" ]]; then
  RAW_PASS="$(cat -- "${OSSS_DB_PASSWORD_FILE}")"
fi

# 2) Explicit env
if [[ -z "${RAW_PASS}" && -n "${OSSS_DB_PASSWORD:-}" ]]; then
  RAW_PASS="${OSSS_DB_PASSWORD}"
fi

# 3a) Parse from ASYNC_DATABASE_URL if still empty
if [[ -z "${RAW_PASS}" && -n "${ASYNC_DATABASE_URL:-}" ]]; then
  RAW_PASS="$(python - <<'PY' "$ASYNC_DATABASE_URL"
import sys, urllib.parse as up
u=sys.argv[1].strip()
p=up.urlparse(u).password or ""
print(p)
PY
)"
fi

# 3b) Parse from ALEMBIC_DATABASE_URL if still empty
if [[ -z "${RAW_PASS}" && -n "${ALEMBIC_DATABASE_URL:-}" ]]; then
  RAW_PASS="$(python - <<'PY' "$ALEMBIC_DATABASE_URL"
import sys, urllib.parse as up
u=sys.argv[1].strip()
p=up.urlparse(u).password or ""
print(p)
PY
)"
fi

log "RAW_PASSWORD='${RAW_PASS}'"

if [[ -z "${RAW_PASS}" ]]; then
  log "FATAL: OSSS_DB_PASSWORD is unset/empty (after resolving env/_FILE/URLs)."
  exit 1
fi

# Strip CR/LF (common when using Docker secrets)
NORM_PASS="$(printf %s "${RAW_PASS}" | tr -d '\r\n')"
log "NORM_PASS='${NORM_PASS}'"

if [[ -z "${NORM_PASS}" ]]; then
  log "FATAL: OSSS_DB_PASSWORD is empty after normalization (newline-only)."
  exit 1
fi

export OSSS_DB_PASSWORD="${NORM_PASS}"
APP_PASS="${NORM_PASS}"

# Ensure libpq behavior is consistent
export PGPASSFILE="/dev/null"
export PGSSLMODE="disable"

# -------- URL-encode password and construct DSNs --------
ENC_PASS="$(python - <<'PY' "$NORM_PASS"
import sys, urllib.parse
print(urllib.parse.quote(sys.argv[1], safe=''))
PY
)"

SYNC_DSN="postgresql+psycopg2://${APP_USER}:${ENC_PASS}@${PGHOST}:${PGPORT}/${APP_DB}?sslmode=disable"
ASYNC_DSN="postgresql+asyncpg://${APP_USER}:${ENC_PASS}@${PGHOST}:${PGPORT}/${APP_DB}"

# If ASYNC_DATABASE_URL not provided, set a sane default
export ASYNC_DATABASE_URL="${ASYNC_DATABASE_URL:-$ASYNC_DSN}"

# Build/normalize ALEMBIC_DATABASE_URL so it **always** has encoded password
alembic_src="constructed from OSSS_DB_*"
if [[ "${HONOR_ALEMBIC_DATABASE_URL:-}" =~ ^(1|true|TRUE|yes|YES)$ && -n "${ALEMBIC_DATABASE_URL:-}" ]]; then
  ALEMBIC_DATABASE_URL="$(
    python - <<'PY' "$ALEMBIC_DATABASE_URL"
import sys, urllib.parse as up
from sqlalchemy.engine.url import make_url

raw = sys.argv[1].strip()
u = make_url(raw)

# Force psycopg2 for Alembic; keep host/port/db/user
if u.get_backend_name() == "postgresql" and u.get_driver_name() != "psycopg2":
    u = u.set(drivername="postgresql+psycopg2")

# Ensure sslmode=disable if none provided (to mirror psql sanity check)
if "sslmode" not in (u.query or {}):
    u = u.update_query_dict({"sslmode": ["disable"]})

# Percent-encode password in final string
user = u.username or ""
pw   = u.password or ""
host = u.host or "localhost"
port = u.port or 5432
db   = (u.database or "").lstrip("/")
q    = u.query or {}

enc_pw = up.quote(pw, safe="")
qstr = up.urlencode({k: v[0] if isinstance(v, (list,tuple)) else v for k,v in q.items()}, doseq=False)

print(f"postgresql+psycopg2://{user}:{enc_pw}@{host}:{port}/{db}" + (f"?{qstr}" if qstr else ""))
PY
  )"
  alembic_src="ALEMBIC_DATABASE_URL (honored+encoded)"
else
  ALEMBIC_DATABASE_URL="$SYNC_DSN"
  alembic_src="constructed from OSSS_DB_* (encoded)"
fi
export ALEMBIC_DATABASE_URL

# -------- Verbose diagnostics helpers --------

_hex_preview() {
  python - <<'PY'
import sys, binascii
s = sys.stdin.buffer.read()
hexs = binascii.hexlify(s).decode("ascii")
n = len(s)
if n == 0:
    print("len=0, hex=")
else:
    if n <= 6:
        print(f"len={n}, hex={hexs}")
    else:
        head = hexs[:12]; tail = hexs[-12:]
        print(f"len={n}, hex={head}…{tail}")
PY
}

_urlencode_pw() {
  python - <<'PY'
import os, urllib.parse
pw = os.getenv("PW","")
print(urllib.parse.quote_plus(pw, safe=""))
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
  if [[ -z "${RAW_PASS}" ]]; then
    log "  value: <EMPTY>"; return
  fi
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
  if [[ "$enc" == "$NORM_PASS" ]]; then
    log "  urlencoded(norm): <unchanged>"
  else
    log "  urlencoded(norm): '${enc}'"
  fi
}

# -------- Core steps --------

wait_for_pg() {
  log "waiting for Postgres at ${PGHOST}:${PGPORT}…"
  for _ in {1..120}; do
    if pg_isready -h "$PGHOST" -p "$PGPORT" >/dev/null 2>&1; then
      log "Postgres is accepting connections."
      return 0
    fi
    sleep 1
  done
  log "Postgres did not become ready in time."
  exit 1
}

sanity_check_app_creds() {
  log "sanity check (auth): connect as '${APP_USER}' to '${APP_DB}' with password…"
  if ! PGPASSWORD="$APP_PASS" psql "host=$PGHOST port=$PGPORT dbname=$APP_DB user=$APP_USER sslmode=disable" \
        -v ON_ERROR_STOP=1 -Atqc 'SELECT 1;' >/dev/null 2>&1; then
    log "ERROR: psql cannot authenticate to '${APP_DB}' as '${APP_USER}'."
    dump_env_summary
    dump_password_diagnostics
    log "psql verbose attempt:"
    PGPASSWORD="$APP_PASS" psql "host=$PGHOST port=$PGPORT dbname=$APP_DB user=$APP_USER sslmode=disable" \
      -v VERBOSITY=verbose -c "SELECT current_user, current_database();"
    exit 1
  fi
  log "sanity check OK (passworded auth)."
}

probe_alembic_url_and_connect() {
  log "ALEMBIC_DATABASE_URL=${ALEMBIC_DATABASE_URL}"

  # Raw psycopg2 probe to avoid async/greenlet issues
  python - <<'PY'
import os, sys, urllib.parse as up
try:
    import psycopg2
except Exception as e:
    print("[alembic-probe] FAIL: psycopg2 not installed -", e); sys.exit(12)

url = os.environ["ALEMBIC_DATABASE_URL"]
norm = url.replace("postgresql+psycopg2://", "postgresql://", 1)
p = up.urlsplit(norm)
q = dict((k, v[0]) for k, v in up.parse_qs(p.query).items())

host = p.hostname or "localhost"
port = p.port or 5432
user = up.unquote(p.username or "")
pwd  = up.unquote(p.password or "")
db   = p.path.lstrip("/") or None
sslmode = q.get("sslmode", "disable")

try:
    conn = psycopg2.connect(host=host, port=port, user=user, password=pwd, dbname=db, sslmode=sslmode)
    cur = conn.cursor(); cur.execute("SELECT current_user, current_database()"); cur.close(); conn.close()
    print("[alembic-probe] OK")
except Exception as e:
    print("[alembic-probe] FAIL:", type(e).__name__, "-", e); sys.exit(12)
PY
}

maybe_run_alembic() {
  [[ -n "${SKIP_ALEMBIC:-}" ]] && { log "SKIP_ALEMBIC set; skipping migrations."; return 0; }

  probe_alembic_url_and_connect

  log "running Alembic migrations (no role/db creation here)…"
  # NOTE: scope sync URLs to the alembic process only
  if ! env \
      DATABASE_URL="$ALEMBIC_DATABASE_URL" \
      SQLALCHEMY_DATABASE_URI="$ALEMBIC_DATABASE_URL" \
      SQLALCHEMY_URL="$ALEMBIC_DATABASE_URL" \
      alembic -x sqlalchemy_url="$ALEMBIC_DATABASE_URL" upgrade head; then
    log "Alembic upgrade failed; dumping diagnostics again:"
    dump_env_summary
    dump_password_diagnostics
    exit 14
  fi
  log "alembic migrations complete."
}


main() {
  dump_env_summary               # now shows encoded ALEMBIC URL
  dump_password_diagnostics
  wait_for_pg
  sanity_check_app_creds
  maybe_run_alembic
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

  exec "$@"
}

main "$@"
