#!/bin/sh
set -eu

# Ensure ES_URL and ELASTIC_PASSWORD are set
: "${ES_URL:?ES_URL not set}"
: "${ELASTIC_PASSWORD:?ELASTIC_PASSWORD not set}"

echo "[mint] checking write access to /shared"
# Check write access to /shared
touch /shared/.tmp.$$ && rm -f /shared/.tmp.$$ || { echo "❌ cannot write to /shared"; exit 1; }

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
# Build JSON body without needing jq
body='{
    "name": "filebeat_osss_ingest_rw",
    "role_descriptors": {
      "filebeat_rw": {
        "cluster": ["monitor","read_ilm","read_pipeline","manage_ilm"],
        "index": [
          {
            "names": ["filebeat-*",".ds-filebeat-*"],
            "privileges": ["auto_configure","create_doc","create","write","view_index_metadata","manage_ilm","read"]
          }
        ]
      }
    }
  }'

resp="$(curl -fsS -u "elastic:${ELASTIC_PASSWORD}" \
  -H "Content-Type: application/json" \
  -d "${body}" \
  "${ES_URL}/_security/api_key" 2>/dev/null || true)"

# If curl failed silently, try to capture an error code/body
if [ -z "${resp}" ]; then
  echo "❌ empty response creating API key"
  curl -i -u "elastic:${ELASTIC_PASSWORD}" -H "Content-Type: application/json" -d "${body}" "${ES_URL}/_security/api_key" || true
  exit 1
fi

# Extract fields with sed (BusyBox safe)
id="$(printf '%s' "$resp" | sed -n 's/.*"id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
secret="$(printf '%s' "$resp" | sed -n 's/.*"api_key"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"

# Check if the id and secret are valid
if [ -z "${id}" ] || [ -z "${secret}" ]; then
  echo "❌ could not parse API key from response:"
  echo "$resp"
  exit 1
fi

# Combine the id and secret into the final API key
ELASTIC_API_KEY="${id}:${secret}"
echo "[mint] raw response (masked id/secret preview):"
echo "       id=$(printf '%s' "$id" | sed 's/^\(......\).*/\1.../') api_key=$(printf '%s' "$secret" | sed 's/^\(......\).*/\1.../')"

# Write the API key to the file in /shared
umask 022
printf 'ELASTIC_API_KEY=%s\n' "$ELASTIC_API_KEY" > /shared/.env.apikey
chmod 0644 /shared/.env.apikey

# Verify that the file was created successfully
echo "[mint] verifying file"
ls -l /shared/.env.apikey || true
echo "mode=$(stat -c '%a' /shared/.env.apikey 2>/dev/null || echo n/a) owner=$(stat -c '%U' /shared/.env.apikey 2>/dev/null || echo n/a)"

echo "[mint] ok - api key created at /shared/.env.apikey"
