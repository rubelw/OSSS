#!/bin/sh
# POSIX-safe, very verbose
set -eux

echo "[fb] whoami: $(id -u):$(id -g)"
uname -a || true

# Ensure data/logs
mkdir -p /shared/filebeat-data /shared/filebeat-logs
# Best-effort fixup for host UID 501 (your mac user in volumes)
chown -R 501:501 /shared/filebeat-data /shared/filebeat-logs || true

# Wait for API key from api-key-init
echo "[fb] waiting for /shared/.env.apikey ..."
i=0
while [ ! -s /shared/.env.apikey ]; do
  i=$((i+1))
  [ $i -le 180 ] || { echo "❌ /shared/.env.apikey missing"; ls -l /shared; exit 2; }
  sleep 1
done

echo "[fb] key preview:"; sed -n '1p' /shared/.env.apikey | sed 's/\(ELASTIC_API_KEY=......\).*/\1.../'

# Export clean ELASTIC_API_KEY (strip CR if any)
ELASTIC_API_KEY="$(awk -F= '/^ELASTIC_API_KEY=/{gsub(/\r/,"",$2);print $2}' /shared/.env.apikey)"
export ELASTIC_API_KEY

echo "[fb] test output → ES"
filebeat test output -e \
  -E output.elasticsearch.hosts=["http://host.containers.internal:9200"] \
  -E output.elasticsearch.api_key="$ELASTIC_API_KEY"

echo "[fb] launching filebeat (exec)"
exec filebeat -e \
  -c /work/config_files/filebeat/filebeat.podman.yml \
  -E path.data=/shared/filebeat-data \
  -E path.logs=/shared/filebeat-logs
