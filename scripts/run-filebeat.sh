#!/bin/sh
set -eu

ES="${ELASTICSEARCH_HOSTS:-http://elasticsearch:9200}"
KB="${KIBANA_HOST:-http://kibana:5601}"
ENV_PATH="${ENV_PATH:-/workspace/.env}"   # host .env bind mount path

log() { echo "[$(date -u +%FT%TZ)] $*"; }
b64() { printf '%s' "$1" | base64; }

# --- robust Elasticsearch wait: accept 200/401/302 as reachable ---
wait_es() {
  host="$1"
  log "Waiting for Elasticsearch at $host ..."
  tries=0
  while :; do
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$host")" || code=""
    case "$code" in
      200|401|302) break ;;
    esac
    tries=$((tries+1))
    if [ $tries -gt 180 ]; then
      log "ERROR: timeout waiting for Elasticsearch at $host (last HTTP $code)"
      exit 1
    fi
    sleep 1
  done
  # Best-effort authenticated health
  health_url="$host/_cluster/health?wait_for_status=yellow&timeout=60s"
  if [ -n "${ELASTIC_API_KEY:-}" ]; then
    auth="$(printf '%s' "$ELASTIC_API_KEY" | base64)"
    curl -sS -H "Authorization: ApiKey $auth" "$health_url" >/dev/null || true
  elif [ -n "${ELASTIC_PASSWORD:-}" ]; then
    curl -sS -u "elastic:${ELASTIC_PASSWORD}" "$health_url" >/dev/null || true
  fi
  log "Elasticsearch is reachable."
}

wait_url() {
  # $1=url  $2=desc
  i=0
  until curl -fsS "$1" >/dev/null 2>&1; do
    i=$((i+1))
    if [ $i -gt 120 ]; then
      log "ERROR: timeout waiting for $2 at $1"
      exit 1
    fi
    sleep 1
  done
}

mint_api_key() {
  # $1=name  $2=payload_json
  resp="$(curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
    -H 'Content-Type: application/json' \
    -d "$2" "${ES}/_security/api_key")"
  id=$(printf '%s' "$resp" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  key=$(printf '%s' "$resp" | sed -n 's/.*"api_key"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  if [ -z "${id:-}" ] || [ -z "${key:-}" ]; then
    log "ERROR: failed to parse API key response for $1: $resp"
    exit 1
  fi
  printf '%s:%s' "$id" "$key"
}

need_key() { varname="$1"; eval "v=\${$varname:-}"; [ -z "${v}" ]; }

# Safely replace-or-append VAR=VALUE in ENV_PATH (no quotes)
persist_env_var() {
  var="$1"; val="$2"; file="$3"
  [ -z "${file}" ] && return 0
  mkdir -p "$(dirname "$file")"
  touch "$file"
  # escape slashes and &
  safe_val=$(printf '%s' "$val" | sed -e 's/[\/&]/\\&/g')
  if grep -q "^${var}=" "$file"; then
    sed -i "s/^${var}=.*/${var}=${safe_val}/" "$file"
  else
    # ensure newline at EOF then append
    [ -s "$file" ] && [ "$(tail -c1 "$file" | wc -l)" -eq 0 ] && printf '\n' >> "$file"
    printf '%s=%s\n' "$var" "$val" >> "$file"
  fi
}

log "Waiting for Elasticsearch..."
wait_es "${ES}"

log "Waiting for Kibana..."
wait_url "${KB}/api/status" "Kibana"

# Create/verify ELASTIC_API_KEY (for output.elasticsearch)
if need_key "ELASTIC_API_KEY"; then
  if [ -z "${ELASTIC_PASSWORD:-}" ]; then
    log "ERROR: ELASTIC_API_KEY is empty and ELASTIC_PASSWORD not provided to mint it."
    exit 1
  fi
  log "Minting ELASTIC_API_KEY (ingest privileges for filebeat-* & logs-*)..."
  ELASTIC_API_KEY="$(mint_api_key "filebeat_osss_ingest" '{
    "name": "filebeat_osss_ingest",
    "role_descriptors": {
      "filebeat_writer": {
        "cluster": ["monitor","read_ilm","read_pipeline"],
        "index": [
          { "names": ["filebeat-*","logs-*"], "privileges": ["auto_configure","create_doc","view_index_metadata"] }
        ]
      }
    }
  }')"
  export ELASTIC_API_KEY
  # Persist to host .env for future runs
  persist_env_var "ELASTIC_API_KEY" "$ELASTIC_API_KEY" "$ENV_PATH"
  log "Persisted ELASTIC_API_KEY to $ENV_PATH"
fi

# Create/verify KIBANA_SETUP_API_KEY (for setup.kibana)
if need_key "KIBANA_SETUP_API_KEY"; then
  if [ -z "${ELASTIC_PASSWORD:-}" ]; then
    log "ERROR: KIBANA_SETUP_API_KEY is empty and ELASTIC_PASSWORD not provided to mint it."
    exit 1
  fi
  log "Minting KIBANA_SETUP_API_KEY (inherits elastic user privileges for setup) ..."
  KIBANA_SETUP_API_KEY="$(mint_api_key "filebeat_setup_kibana" '{"name":"filebeat_setup_kibana"}')"
  export KIBANA_SETUP_API_KEY
  # Persist to host .env for future runs
  persist_env_var "KIBANA_SETUP_API_KEY" "$KIBANA_SETUP_API_KEY" "$ENV_PATH"
  log "Persisted KIBANA_SETUP_API_KEY to $ENV_PATH"
fi

# Sanity: Kibana must return full status (with version) when authorized
AUTH_KB="$(b64 "$KIBANA_SETUP_API_KEY")"
status_json="$(curl -fsS -H "Authorization: ApiKey ${AUTH_KB}" "${KB}/api/status")" || {
  log "ERROR: Kibana status request failed with setup API key"; exit 1; }

case "$status_json" in
  *\"version\"* ) log "Kibana API key looks good (version present).";;
  * ) log "WARNING: Kibana returned minimal status (no version). Setup may fail. Using inherited superuser key is recommended.";;
esac

log "Diagnostics: printing merged config sections"
filebeat export config -e | sed -n '/^setup.kibana:/,/^[^ ]/p'
filebeat export config -e | sed -n '/^output.elasticsearch:/,/^[^ ]/p'

log "Testing Elasticsearch output"
filebeat test output -e || log "WARN: filebeat test output failed; proceeding to start"

log "Starting Filebeat…"
exec filebeat "$@"
