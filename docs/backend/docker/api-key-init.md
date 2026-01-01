# `api-key-init` service

This page documents the configuration for the `api-key-init` service from `docker-compose.yml`.

**Image:** `curlimages/curl:8.8.0`
**Container name:** `api-key-init`

**Volumes:**

- `./config_files/filebeat/mint_apikey.sh:/usr/local/bin/mint_apikey.sh:ro,z`
- `es-shared:/shared:z`

**Depends on:**

- `shared-vol-init`
- `elasticsearch`

**Networks:**

- `osss-net`

**Environment:**

- `ES_URL=http://elasticsearch:9200`
- `ELASTIC_PASSWORD=${ELASTIC_PASSWORD:-password}`

**Command:**

```bash
/bin/sh -exc echo "[api-key-init] begin"
ls -l /usr/local/bin/mint_apikey.sh || { echo "missing mint_apikey.sh" >&2; exit 1; }
# run script explicitly; we don't need +x on the file this way
/bin/sh /usr/local/bin/mint_apikey.sh

echo "[verify] checking /shared/.env.apikey"
ls -l /shared || true
if [ -s /shared/.env.apikey ]; then
  echo "[verify] permissions/owner for /shared/.env.apikey"
  stat -c 'mode=%a owner=%U group=%G' /shared/.env.apikey || true
  echo "[verify] masked key preview"
  awk -F= '/^ELASTIC_API_KEY=/{print "ELASTIC_API_KEY=" substr($$2,1,6) "..."}' /shared/.env.apikey || true
else
  echo "❌ /shared/.env.apikey missing or empty" >&2
  exit 2
fi
echo "[api-key-init] done"

```
