#!/bin/sh
set -Eeuo pipefail

# --- verbosity ---
VERBOSE="${VERBOSE:-1}"   # 1=log steps, 0=quiet
DEBUG="${DEBUG:-0}"       # 1=set -x

[ "$DEBUG" = "1" ] && { set -x; PS4='+ [seed] ${0##*/}:${LINENO}: '; }

# --- tiny utils ---
now()  { date +"%Y-%m-%dT%H:%M:%S%z"; }
log()  { printf '%s %s\n' "$(now)" "$*"; }
dbg()  { [ "$VERBOSE" = "1" ] && log "$*"; }

mask() {
  s="${1-}"; [ -z "$s" ] && { printf '\n'; return; }
  tail4="$(printf %s "$s" | tail -c 4 2>/dev/null || printf %s "$s")"
  printf '****%s\n' "$tail4"
}

need() { command -v "$1" >/dev/null 2>&1 || MISSING="$MISSING $1"; }

# --- config from env (with defaults) ---
VAULT_ADDR="${VAULT_ADDR:-http://vault:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-root}"
VAULT_KV_PATH="${VAULT_KV_PATH:-app}"

log "VAULT_ADDR=$VAULT_ADDR"
log "VAULT_KV_PATH=$VAULT_KV_PATH"
log "VAULT_TOKEN=$(mask "$VAULT_TOKEN")"

# --- ensure tools present ---
MISSING=""
need curl; need jq
if [ -n "${MISSING:-}" ]; then
  if command -v apk >/dev/null 2>&1; then
    log "Installing tools:${MISSING}"
    apk add --no-cache $MISSING >/dev/null
  else
    log "ERROR: missing:${MISSING} and no package manager found"; exit 1
  fi
fi

# --- wait for vault ---
log "Waiting for Vault to be healthy…"
until curl -fsS "$VAULT_ADDR/v1/sys/health" >/dev/null 2>&1; do sleep 1; done
log "Vault is reachable."

# --- validate token ---
if ! curl -fsS -H "X-Vault-Token: $VAULT_TOKEN" \
     "$VAULT_ADDR/v1/auth/token/lookup-self" >/dev/null; then
  log "ERROR: VAULT_TOKEN invalid for $VAULT_ADDR"; exit 1
fi
dbg "Token OK."

# --- ensure secret/ is KV v2 ---
MOUNTS="$(curl -fsS -H "X-Vault-Token: $VAULT_TOKEN" "$VAULT_ADDR/v1/sys/mounts")" || {
  log "ERROR: cannot read /v1/sys/mounts"; exit 1; }

if ! echo "$MOUNTS" | jq -e '.data."secret/".options.version == "2"' >/dev/null 2>&1; then
  typ="$(echo "$MOUNTS" | jq -r '.data."secret/".type // empty')"
  if [ -z "$typ" ]; then
    log "Mounting secret/ as KV v2"
    curl -fsS -H "X-Vault-Token: $VAULT_TOKEN" -H 'Content-Type: application/json' \
      -X POST "$VAULT_ADDR/v1/sys/mounts/secret" \
      -d '{"type":"kv","options":{"version":"2"}}' >/dev/null
  else
    log "ERROR: secret/ exists but is not KV v2 (type=$typ). Convert or change VAULT_KV_PATH."; exit 1
  fi
fi
dbg "KV v2 confirmed on secret/."

# --- build JSON from SEED_* env vars ---
TMP="$(mktemp)"; echo '{}' > "$TMP"
COUNT=0
# collect names safely, then read values with printenv
for NAME in $(env | awk -F= '/^SEED_/ {print $1}'); do
  VALUE="$(printenv "$NAME" || true)"
  KEY="$(printf %s "$NAME" | sed 's/^SEED_//' | tr 'A-Z' 'a-z')"
  jq --arg k "$KEY" --arg v "$VALUE" '. + {($k):$v}' "$TMP" > "${TMP}.new" && mv "${TMP}.new" "$TMP"
  COUNT=$((COUNT+1))
done

DATA="$(jq -c . "$TMP")"; rm -f "$TMP"

if [ "${COUNT:-0}" -eq 0 ] || [ "$DATA" = "{}" ]; then
  log "No SEED_* variables found; nothing to write. Done."; exit 0
fi

KEYS="$(printf %s "$DATA" | jq -r 'keys | join(",")')"
log "Writing $COUNT keys to secret/data/$VAULT_KV_PATH: [$KEYS]"

RESP="$(curl -sS -w ' HTTP_CODE:%{http_code}' \
  -H "X-Vault-Token: $VAULT_TOKEN" -H 'Content-Type: application/json' \
  -X POST "$VAULT_ADDR/v1/secret/data/$VAULT_KV_PATH" \
  -d "{\"data\":$DATA}")"
CODE="${RESP##*HTTP_CODE:}"; BODY="${RESP% HTTP_CODE:*}"
dbg "Write status: $CODE"
[ "$VERBOSE" = "1" ] && dbg "Write resp: $(echo "$BODY" | tr -d '\n' | cut -c1-400)"
[ "$CODE" -ge 200 ] && [ "$CODE" -lt 300 ] || { log "ERROR: write failed ($CODE)"; echo "$BODY" >&2; exit 1; }

# --- verify ---
VRESP="$(curl -sS -w ' HTTP_CODE:%{http_code}' \
  -H "X-Vault-Token: $VAULT_TOKEN" \
  "$VAULT_ADDR/v1/secret/data/$VAULT_KV_PATH")"
VCODE="${VRESP##*HTTP_CODE:}"; VBODY="${VRESP% HTTP_CODE:*}"
if [ "$VCODE" -ge 200 ] && [ "$VCODE" -lt 300 ]; then
  VKEYS="$(echo "$VBODY" | jq -r '.data.data | keys | join(",")')"
  log "Verify OK. Keys present: [$VKEYS]"
else
  log "WARN: verify fetch failed ($VCODE)"
fi

log "Seed complete."
