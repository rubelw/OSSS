#!/bin/sh
set -eu

: "${ES_URL:?ES_URL not set}"
: "${ELASTIC_PASSWORD:?ELASTIC_PASSWORD not set}"
: "${KIBANA_URL:?KIBANA_URL not set}"
: "${KIBANA_USERNAME:?KIBANA_USERNAME not set}"
: "${KIBANA_PASSWORD:?KIBANA_PASSWORD not set}"

echo "[mint] checking write access to /shared"
touch /shared/.tmp.$$ && rm -f /shared/.tmp.$$ || { echo "❌ cannot write to /shared"; exit 1; }

# Ensure data/log dirs exist *before* any filebeat command
mkdir -p /shared/filebeat-data /shared/filebeat-logs
chmod 775 /shared/filebeat-data /shared/filebeat-logs || true
# make them usable by your host user if present in the container
id -u 501 >/dev/null 2>&1 && chown -R 501:501 /shared/filebeat-data /shared/filebeat-logs || true

echo "[mint] waiting for Elasticsearch at ${ES_URL} ..."
i=0
while :; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "${ES_URL}/")" || code=000
  case "$code" in
    200|401|302) echo "[mint] ES is reachable (code=${code})"; break ;;
  esac
  i=$((i+1)); [ "$i" -le 120 ] || { echo "❌ ES not reachable (last code=${code})"; exit 1; }
  sleep 1
done

echo "[mint] creating API key via _security/api_key"
body='{"name":"filebeat_osss_ingest","role_descriptors":{"filebeat_writer":{"cluster":["monitor","read_ilm","read_pipeline","manage_ilm"],"index":[{"names":["logs-*","filebeat-*"],"privileges":["auto_configure","create_doc","view_index_metadata","create_index","manage"]}]}}}'

resp="$(curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
  -H "Content-Type: application/json" \
  -d "${body}" \
  "${ES_URL}/_security/api_key" 2>/dev/null || true)"

[ -n "$resp" ] || { echo "❌ empty response creating API key"; exit 1; }

id="$(printf '%s' "$resp" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
secret="$(printf '%s' "$resp" | sed -n 's/.*"api_key"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
[ -n "$id" ] && [ -n "$secret" ] || { echo "❌ could not parse API key"; echo "$resp"; exit 1; }

ELASTIC_API_KEY="${id}:${secret}"
umask 022
printf 'ELASTIC_API_KEY=%s\n' "$ELASTIC_API_KEY" > /shared/.env.apikey
chmod 0644 /shared/.env.apikey

echo "[wait] for Kibana at ${KIBANA_URL}..."
i=0
until code="$(curl -sS -o /dev/null -w '%{http_code}' "${KIBANA_URL}/api/status")" \
  && { [ "$code" = "200" ] || [ "$code" = "302" ] || [ "$code" = "401" ]; }; do
  i=$((i+1)); [ $i -le 300 ] || { echo "Kibana not reachable (last http_code=$code)"; exit 1; }
  sleep 1
done

# Self-check paths
filebeat test config -e \
  -E path.data=/shared/filebeat-data \
  -E path.logs=/shared/filebeat-logs || true

# Run setup (dashboards + ILM + templates) with API key auth
timeout 10m filebeat setup -e \
  -E logging.level=debug -d "kibana,*" \
  -E setup.ilm.overwrite=true \
  -E setup.dashboards.enabled=true \
  -E "setup.kibana.host=${KIBANA_URL}" \
  -E "setup.kibana.username=${KIBANA_USERNAME}" \
  -E "setup.kibana.password=${KIBANA_PASSWORD}" \
  -E "output.elasticsearch.hosts=[\"${ES_URL}\"]" \
  -E path.data=/shared/filebeat-data \
  -E path.logs=/shared/filebeat-logs

# Keep ownership friendly for the runtime Filebeat container
id -u 501 >/dev/null 2>&1 && chown -R 501:501 /shared/filebeat-data /shared/filebeat-logs || true
