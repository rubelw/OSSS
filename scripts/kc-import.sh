#!/usr/bin/env bash
# kc-import.sh — Keycloak headless importer (ordered). Works with KC 24/25/26.
set -Eeuo pipefail

# ---------- Required env ----------
: "${KC_DB:=postgres}"
: "${KC_DB_URL_HOST:?KC_DB_URL_HOST is required}"
: "${KC_DB_URL_PORT:=5432}"
: "${KC_DB_URL_DATABASE:?KC_DB_URL_DATABASE is required}"
: "${KC_DB_USERNAME:?KC_DB_USERNAME is required}"
: "${KC_DB_PASSWORD:?KC_DB_PASSWORD is required}"

# ---------- Optional ----------
: "${KC_LOG_LEVEL:=TRACE}"                      # INFO|DEBUG|TRACE
: "${IMPORT_PATH:=/opt/keycloak/data/import}"  # file or dir of JSONs
: "${IMPORT_STRATEGY:=IGNORE_EXISTING}"        # legacy: IGNORE_EXISTING|OVERWRITE_EXISTING|UPDATE
: "${IMPORT_OVERRIDE:=false}"                  # preferred: true|false (KC 25+)
: "${KC_DB_URL_PROPERTIES:=}"

echo "== Keycloak import starting =="
echo "DB: ${KC_DB}://${KC_DB_URL_HOST}:${KC_DB_URL_PORT}/${KC_DB_URL_DATABASE}"
[[ -n "${KC_DB_URL_PROPERTIES}" ]] && echo "DB PROPS: ${KC_DB_URL_PROPERTIES}"
echo "Import source: ${IMPORT_PATH}"

# Fix props accidentally appended to DB name (common env quirk)
if [[ "${KC_DB_URL_DATABASE}" =~ ^([A-Za-z0-9_-]+)\?([A-Za-z0-9_&=.:;-]+)$ ]]; then
  CLEAN_DB_NAME="${BASH_REMATCH[1]}"
  EXTRA_PROPS="${BASH_REMATCH[2]}"
  export KC_DB_URL_DATABASE="${CLEAN_DB_NAME}"
  if [[ -n "${KC_DB_URL_PROPERTIES}" ]]; then
    export KC_DB_URL_PROPERTIES="${KC_DB_URL_PROPERTIES}&${EXTRA_PROPS}"
  else
    export KC_DB_URL_PROPERTIES="${EXTRA_PROPS}"
  fi
  echo "Adjusted DB name -> ${KC_DB_URL_DATABASE} ; props -> ${KC_DB_URL_PROPERTIES}"
fi

# Validate import path
if [[ -f "${IMPORT_PATH}" ]]; then
  FILE_MODE=true
elif [[ -d "${IMPORT_PATH}" ]]; then
  FILE_MODE=false
else
  echo "ERROR: IMPORT_PATH ${IMPORT_PATH} not found" >&2
  exit 2
fi

# ---------- Map override flag ----------
OVERRIDE_BOOL=""
case "${IMPORT_OVERRIDE,,}" in
  true|false) OVERRIDE_BOOL="${IMPORT_OVERRIDE,,}";;
  "") :;;  # fall through to mapping from IMPORT_STRATEGY
  *) echo "ERROR: IMPORT_OVERRIDE must be true|false (got '${IMPORT_OVERRIDE}')" >&2; exit 2;;
esac
if [[ -z "${OVERRIDE_BOOL}" && -n "${IMPORT_STRATEGY}" ]]; then
  case "${IMPORT_STRATEGY^^}" in
    IGNORE_EXISTING)           OVERRIDE_BOOL="false";;
    OVERWRITE_EXISTING|UPDATE) OVERRIDE_BOOL="true";;
    *) echo "ERROR: Unsupported IMPORT_STRATEGY='${IMPORT_STRATEGY}'" >&2; exit 2;;
  esac
fi
: "${OVERRIDE_BOOL:=false}"

# ---------- Common kc args ----------
KC_ARGS=(
  "--verbose"
  "--db=${KC_DB}"
  "--db-url-host=${KC_DB_URL_HOST}"
  "--db-url-port=${KC_DB_URL_PORT}"
  "--db-url-database=${KC_DB_URL_DATABASE}"
  "--db-username=${KC_DB_USERNAME}"
  "--db-password=${KC_DB_PASSWORD}"
  "--log-level=${KC_LOG_LEVEL}"
)
[[ -n "${KC_DB_URL_PROPERTIES}" ]] && KC_ARGS+=("--db-url-properties=${KC_DB_URL_PROPERTIES}")

set -x
if [[ "${FILE_MODE}" == "true" ]]; then
  # Single file import
  /opt/keycloak/bin/kc.sh import --override="${OVERRIDE_BOOL}" --file="${IMPORT_PATH}" "${KC_ARGS[@]}"
else
  # Directory import — deterministic order:
  shopt -s nullglob
  mapfile -t FILES < <(ls -1 "${IMPORT_PATH}"/*.json 2>/dev/null | sort)
  if ((${#FILES[@]}==0)); then
    echo "No .json files in ${IMPORT_PATH}" >&2
    exit 2
  fi

  # Categorize files by name (no fragile [[ … ]] globs)
  realm=() cscopes=() clients=() roles=() croles=() groups=() maps=() users=() other=()
  for f in "${FILES[@]}"; do
    case "$f" in
      *-realm.json)                 realm+=("$f")  ;;
      *-client-scopes.json)         cscopes+=("$f");;
      *-clients.json)               clients+=("$f");;
      *-roles-client.json)          croles+=("$f") ;;
      *-roles.json)                 roles+=("$f")  ;; # after roles-client is also fine; we explicitly order below
      *-groups.json)                groups+=("$f") ;;
      *-group-role-mappings.json)   maps+=("$f")   ;;
      *-users.json|*-users-*.json)  users+=("$f")  ;;
      *)                            other+=("$f")  ;;
    esac
  done

  # Final order
  ordered=( "${realm[@]}" "${cscopes[@]}" "${clients[@]}" "${roles[@]}" "${croles[@]}" "${groups[@]}" "${maps[@]}" "${users[@]}" "${other[@]}" )

  echo "+ Import order:"
  printf '   %s\n' "${ordered[@]}"

  # Import one by one
  for f in "${ordered[@]}"; do
    echo "== Importing $f =="
    /opt/keycloak/bin/kc.sh import --override="${OVERRIDE_BOOL}" --file="$f" "${KC_ARGS[@]}"
  done
fi
set +x
