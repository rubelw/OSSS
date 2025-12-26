#!/usr/bin/env sh
set -e

log() { printf '%s %s\n' "[$(date '+%Y-%m-%dT%H:%M:%S%z')]" "$*" >&2; }

# ---------------------------
# Postgres bootstrap: role + DBs
# ---------------------------
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
  -- Ensure role
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${OSSS_DB_USER}') THEN
    EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', '${OSSS_DB_USER}', '${OSSS_DB_PASSWORD}');
  ELSE
    EXECUTE format('ALTER ROLE %I WITH LOGIN PASSWORD %L', '${OSSS_DB_USER}', '${OSSS_DB_PASSWORD}');
  END IF;
END
\$\$;
SQL

# Drop + recreate OSSS and Tutor DBs
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
DROP DATABASE IF EXISTS "${OSSS_DB_NAME}";
DROP DATABASE IF EXISTS "${OSSS_TUTOR_DB_NAME:-osss_tutor}";

CREATE DATABASE "${OSSS_DB_NAME}" OWNER "${OSSS_DB_USER}";
CREATE DATABASE "${OSSS_TUTOR_DB_NAME:-osss_tutor}" OWNER "${OSSS_DB_USER}";
SQL

# ---------------------------
# Ensure pgvector extension exists (superuser) in BOTH DBs
# ---------------------------

ensure_vector() {
  db="$1"
  log "Ensuring pgvector extension in DB: $db"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
    RAISE EXCEPTION 'pgvector extension (vector) is not available in this Postgres instance. Use pgvector/pgvector image or install the extension.';
  END IF;

  -- needs superuser; safe here because init scripts run as POSTGRES_USER
  CREATE EXTENSION IF NOT EXISTS vector;
END
$$;
SQL
}

ensure_vector "${OSSS_DB_NAME}"
ensure_vector "${OSSS_TUTOR_DB_NAME:-osss_tutor}"

# ---------------------------
# OSSS Tutor DB + tutor_chunks table
# ---------------------------

# In the tutor DB, create extension/table/indexes idempotently
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${OSSS_TUTOR_DB_NAME:-osss_tutor}" <<SQL
-- ensure extension (idempotent)
CREATE EXTENSION IF NOT EXISTS vector;

-- create table once
DO \$\$
BEGIN
  IF to_regclass('public.tutor_chunks') IS NULL THEN
    CREATE TABLE public.tutor_chunks (
      id         VARCHAR(36) PRIMARY KEY,
      doc_id     VARCHAR(36) NOT NULL,
      text       TEXT NOT NULL,
      -- recommended: use real pgvector type instead of double precision[]
      embedding  VECTOR(1536),
      created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
  END IF;
END
\$\$;

-- create indexes once
DO \$\$
BEGIN
  IF to_regclass('public.ix_tutor_chunks_doc_id') IS NULL THEN
    CREATE INDEX ix_tutor_chunks_doc_id ON public.tutor_chunks (doc_id);
  END IF;

  -- optional: vector index (IVFFLAT requires lists; tune as needed)
  IF to_regclass('public.idx_tutor_chunks_embedding') IS NULL THEN
    CREATE INDEX idx_tutor_chunks_embedding
      ON public.tutor_chunks
      USING ivfflat (embedding vector_cosine_ops)
      WITH (lists = 100);
  END IF;
END
\$\$;
SQL

# ---------------------------
# Keycloak partial import (only if realm exists)
# ---------------------------

KC_URL="${KEYCLOAK_URL:-http://keycloak:8080}"
REALM="${KEYCLOAK_REALM:-OSSS}"
ADMIN="${KEYCLOAK_ADMIN:-a2a}"
ADMIN_PASS="${KEYCLOAK_ADMIN_PASSWORD:-a2a}"
POLICY="${KEYCLOAK_IMPORT_POLICY:-OVERWRITE}"  # OVERWRITE|SKIP|FAIL

IMPORT_DIRS="${KEYCLOAK_IMPORT_DIRS:-/opt/keycloak/data/import:/opt/keycloak/import:/seed/keycloak:/docker-entrypoint-initdb.d}"

find_one() {
  pattern="$1"
  OLDIFS=$IFS; IFS=":"
  for d in $IMPORT_DIRS; do
    [ -d "$d" ] || continue
    for f in $d/$pattern; do
      [ -f "$f" ] && { IFS=$OLDIFS; echo "$f"; return 0; }
    done
  done
  IFS=$OLDIFS
  return 1
}

REALM_FILE="$(find_one "*-${REALM}-realm.json" || true)"
ROLES_FILE="$(find_one "*-${REALM}-roles.json" || true)"
CLIENTS_FILE="$(find_one "*-${REALM}-clients.json" || true)"
GROUPS_FILE="$(find_one "*-${REALM}-groups.json" || true)"
USERS_FILE="$(find_one "*-${REALM}-users.json" || true)"

wait_for_kc() {
  url="$KC_URL/realms/master/.well-known/openid-configuration"
  end=$(( $(date +%s) + ${KC_WAIT_SECS:-60} ))
  while [ "$(date +%s)" -lt "$end" ]; do
    if curl -fsS "$url" >/dev/null 2>&1; then return 0; fi
    sleep 1
  done
  return 1
}

get_admin_token() {
  curl -fsS -X POST "$KC_URL/realms/master/protocol/openid-connect/token" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode "grant_type=password" \
    --data-urlencode "client_id=admin-cli" \
    --data-urlencode "username=$ADMIN" \
    --data-urlencode "password=$ADMIN_PASS" \
  | awk -F'"' '/access_token/ {getline; print $4}' 2>/dev/null
}

realm_exists() {
  tok="$1"
  curl -fsS -H "Authorization: Bearer $tok" \
    "$KC_URL/admin/realms/$REALM" >/dev/null 2>&1
}

inject_policy() {
  file="$1"
  policy="$2"
  content=$(cat "$file" | sed '1s/^\xEF\xBB\xBF//')
  body=$(printf '{"ifResourceExists":"%s",%s}' "$policy" \
        "$(printf '%s' "$content" | sed -e '1s/^[[:space:]]*{//' -e '$s/}[[:space:]]*$//')")
  printf '%s' "$body"
}

partial_import() {
  file="$1"
  kind="$2"
  [ -f "$file" ] || return 0
  body="$(inject_policy "$file" "$POLICY")"
  curl -fsS -X POST "$KC_URL/admin/realms/$REALM/partialImport" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    --data-binary "$body" >/dev/null
  log "Keycloak partial import ($kind) from $(basename "$file") with policy=$POLICY"
}

if wait_for_kc; then
  TOKEN="$(get_admin_token || true)"
  if [ -z "$TOKEN" ]; then
    log "Keycloak admin token unavailable; skipping KC import."
    exit 0
  fi

  if realm_exists "$TOKEN"; then
    log "Realm '$REALM' exists — applying partial imports."
    [ -n "$CLIENTS_FILE" ] && partial_import "$CLIENTS_FILE" "clients"
    [ -n "$ROLES_FILE" ]   && partial_import "$ROLES_FILE"   "roles"
    [ -n "$GROUPS_FILE" ]  && partial_import "$GROUPS_FILE"  "groups"
    [ -n "$USERS_FILE" ]   && partial_import "$USERS_FILE"   "users"
    log "Keycloak partial import completed."
  else
    log "Realm '$REALM' not found — skipping KC import."
  fi
else
  log "Keycloak not reachable — skipping KC import."
fi