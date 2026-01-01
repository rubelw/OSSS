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

```bash
set -euo pipefail; now() { date -Iseconds; }; log() { printf '%s %s\n' "$$(now)" "$$*"; }; mask() { s="$$1"; [ -z "$$s" ] && printf '(empty)\n' || { [ "$${#s}" -le 8 ] && printf '******\n' || printf '%s******\n' "$${s%??????}"; }; }; log "ES_URL=$$ES_URL"; log "ELASTIC_PASSWORD=$$(mask "$$ELASTIC_PASSWORD")"; log "KIBANA_PASSWORD=$$(mask "$$KIBANA_PASSWORD")"; log "Waiting for Elasticsearch cluster health..."; __tries=0; while :; do
  __code="$$(curl -sS -o /dev/null -w '%{http_code}' -u "elastic:$$ELASTIC_PASSWORD" "$$ES_URL/_cluster/health" || echo 000)";
  log "cluster health http_code=$$__code";
  [ "$$__code" = "200" ] && break;
  __tries=$$((__tries+1)); [ "$$__tries" -le 180 ] || { log "Elasticsearch not ready after 180 attempts"; exit 1; };
  sleep 3;
done; log "Elasticsearch reachable"; log "Setting kibana_system password..."; __resp="$$(curl -sS -u "elastic:$$ELASTIC_PASSWORD" -H 'Content-Type: application/json' -w '\nHTTP_STATUS:%{http_code}\n' -X POST "$$ES_URL/_security/user/kibana_system/_password" -d "{\"password\":\"$$KIBANA_PASSWORD\"}")"; __rc="$$(printf '%s' "$$__resp" | sed -n 's/^HTTP_STATUS://p')"; __body="$$(printf '%s' "$$__resp" | sed '$$d')"; log "POST /_security/user/kibana_system/_password -> $$__rc"; if [ -z "$$__rc" ] || [ "$$__rc" -ge 400 ]; then log "Failed to set kibana_system password; response follows:"; printf '%s\n' "$$__body"; exit 1; fi; log "kibana_system password set"; log "Verifying kibana_system authentication..."; __v="$$(curl -sS -u "kibana_system:$$KIBANA_PASSWORD" -w '\nHTTP_STATUS:%{http_code}\n' "$$ES_URL/_security/_authenticate" || true)"; __v_code="$$(printf '%s' "$$__v" | sed -n 's/^HTTP_STATUS://p')"; __v_body="$$(printf '%s' "$$__v" | sed '$$d')"; log "GET /_security/_authenticate as kibana_system -> $$__v_code"; [ "$$__v_code" = "200" ] || { printf '%s\n' "$$__v_body"; exit 1; }; log "kibana-pass-init complete.";

```
