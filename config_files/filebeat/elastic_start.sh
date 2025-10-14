#!/usr/bin/env bash
set -euo pipefail

VM_PROJ="/work"
PROJECT="osss-elastic"
PROFILE="elastic"
COMPOSE_FILE="${VM_PROJ}/docker-compose.yml"

echo "🔧 [elastic-start] Entered elastic stack startup script"
echo "   VM_PROJ=${VM_PROJ}"
echo "   PROJECT=${PROJECT}  PROFILE=${PROFILE}"
echo

cd "${VM_PROJ}" || { echo "❌ Path not visible inside VM: ${VM_PROJ}"; exit 1; }
command -v sudo podman-compose >/dev/null && podman-compose --version || true

# Pick compose provider (prefer podman compose)
if sudo podman compose version >/dev/null 2>&1; then
  COMPOSE=(sudo podman compose)
elif command -v sudo podman-compose >/dev/null 2>&1; then
  COMPOSE=(sudo podman-compose)
else
  echo '❌ Neither podman compose nor podman-compose installed' >&2; exit 1
fi

# Helpers
cid_for() {
  local svc="$1"
  sudo podman ps -a \
    --filter label=io.podman.compose.project="${PROJECT}" \
    --filter label=com.docker.compose.project="${PROJECT}" \
    --filter label=io.podman.compose.service="${svc}" \
    --filter label=com.docker.compose.service="${svc}" \
    --format '{{.ID}}' | head -n1
}

wait_healthy() {
  local svc="$1"; local timeout="${2:-300}"; local start
  start="$(date +%s)"
  echo "⏳ Waiting for ${svc} to be healthy..."
  while :; do
    local cid health running
    cid="$(cid_for "$svc" || true)"
    if [ -n "${cid:-}" ]; then
      health="$(sudo podman inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" || echo none)"
      running="$(sudo podman inspect -f '{{.State.Running}}' "$cid" || echo false)"
      if [ "$health" = "healthy" ] || { [ "$health" = "none" ] && [ "$running" = "true" ]; }; then
        echo "✅ $svc is ready ($health)"
        break
      fi
    fi
    if [ $(( $(date +%s) - start )) -ge "$timeout" ]; then
      echo "❌ Timeout waiting for $svc"
      [ -n "${cid:-}" ] && sudo podman logs --tail=200 "$cid" || true
      exit 1
    fi
    sleep 2
  done
}

echo
echo "🚀 [elastic-start] Starting base stack (elasticsearch + kibana + kibana-pass-init + api-key-init)"
echo "    Using compose file: ${COMPOSE_FILE}"
COMPOSE_PROJECT_NAME="${PROJECT}" "${COMPOSE[@]}" -f "${COMPOSE_FILE}" --profile "${PROFILE}" up -d \
  --force-recreate --remove-orphans \
  elasticsearch kibana kibana-pass-init api-key-init
echo "✅ Base stack containers launched"

# Wait on ES + Kibana (container health)
wait_healthy elasticsearch 300
wait_healthy kibana 300

# Ensure API key file exists (written by api-key-init)
echo
echo "[check] /shared/filebeat.apikey.env"
if ! sudo podman run --rm -v es-shared:/shared alpine sh -lc "test -s /shared/filebeat.apikey.env"; then
  echo "❌ Missing /shared/filebeat.apikey.env; run/retry api-key-init first"
  exit 2
fi

# Run filebeat-setup once (force recreate so it actually re-runs)
echo
echo "🛠️  [elastic-start] Running setup job: filebeat-setup"
sudo podman rm -f filebeat-setup >/dev/null 2>&1 || true
COMPOSE_PROJECT_NAME="${PROJECT}" "${COMPOSE[@]}" -f "${COMPOSE_FILE}" --profile "${PROFILE}" up -d --force-recreate filebeat-setup

# Follow until it exits (ok or error)
for i in $(seq 1 240); do
  st="$(sudo podman inspect -f '{{.State.Status}}' filebeat-setup 2>/dev/null || echo 'missing')"
  case "$st" in
    running) sleep 2 ;;
    exited)
      rc="$(sudo podman inspect -f '{{.State.ExitCode}}' filebeat-setup 2>/dev/null || echo 1)"
      echo "-- filebeat-setup exited rc=$rc; last 200 lines --"
      sudo podman logs --tail=200 filebeat-setup || true
      [ "$rc" -eq 0 ] || exit "$rc"
      break
      ;;
    *) sleep 2 ;;
  esac
done

# Start filebeat (compose already mounts /shared + podman.sock)
echo
echo "📡 [elastic-start] Starting filebeat"
sudo podman rm -f filebeat >/dev/null 2>&1 || true
COMPOSE_PROJECT_NAME="${PROJECT}" "${COMPOSE[@]}" -f "${COMPOSE_FILE}" --profile "${PROFILE}" up -d --force-recreate filebeat

echo
echo "== 📋 Running containers (name | status | ports) =="
sudo podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || true
echo "== End of container list =="
