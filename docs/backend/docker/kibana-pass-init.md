# `kibana-pass-init` service

This page documents the configuration for the `kibana-pass-init` service from `docker-compose.yml`.

**Image:** `curlimages/curl:8.8.0`  
**Container name:** `kibana-pass-init`

**Depends on:**

- `elasticsearch`

**Networks:**

- `osss-net`

**Environment:**

- `ELASTIC_PASSWORD=${ELASTIC_PASSWORD}`
- `KIBANA_PASSWORD=${KIBANA_PASSWORD}`
- `ES_URL=http://elasticsearch:9200`

**Command:**

{% raw %}
```bash
set -euo pipefail

now() { date -Iseconds; }

log() {
  printf '%s %s\n' "$(now)" "$*"
}

mask() {
  s="$1"
  if [ -z "$s" ]; then
    printf '(empty)\n'
  elif [ "${#s}" -le 8 ]; then
    printf '******\n'
  else
    printf '%s******\n' "${s%??????}"
  fi
}

log "ES_URL=$ES_URL"
log "ELASTIC_PASSWORD=$(mask "$ELASTIC_PASSWORD")"
log "KIBANA_PASSWORD=$(mask "$KIBANA_PASSWORD")"
log "Waiting for Elasticsearch cluster health..."

tries=0
while :; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' \
    -u "elastic:$ELASTIC_PASSWORD" \
    "$ES_URL/_cluster/health" || echo 000)"
  log "cluster health http_code=$code"
  [ "$code" = "200" ] && break
  tries=$((tries+1))
  [ "$tries" -le 180 ] || { log "Elasticsearch not ready after 180 attempts"; exit 1; }
  sleep 3
done

log "Elasticsearch reachable"
log "Setting kibana_system password..."

resp="$(curl -sS -u "elastic:$ELASTIC_PASSWORD" \
  -H 'Content-Type: application/json' \
  -w '\nHTTP_STATUS:%{http_code}\n' \
  -X POST "$ES_URL/_security/user/kibana_system/_password" \
  -d "{\"password\":\"$KIBANA_PASSWORD\"}")"

rc="$(printf '%s' "$resp" | sed -n 's/^HTTP_STATUS://p')"
body="$(printf '%s' "$resp" | sed '$d')"

log "POST /_security/user/kibana_system/_password -> $rc"

if [ -z "$rc" ] || [ "$rc" -ge 400 ]; then
  log "Failed to set kibana_system password; response follows:"
  printf '%s\n' "$body"
  exit 1
fi

log "kibana_system password set"
log "Verifying kibana_system authentication..."

v="$(curl -sS -u "kibana_system:$KIBANA_PASSWORD" \
  -w '\nHTTP_STATUS:%{http_code}\n' \
  "$ES_URL/_security/_authenticate" || true)"

v_code="$(printf '%s' "$v" | sed -n 's/^HTTP_STATUS://p')"
v_body="$(printf '%s' "$v" | sed '$d')"

log "GET /_security/_authenticate as kibana_system -> $v_code"

[ "$v_code" = "200" ] || { printf '%s\n' "$v_body"; exit 1; }

log "kibana-pass-init complete."

{% endraw %}