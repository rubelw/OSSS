#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker-compose.yml"

# --- helpers ---------------------------------------------------------------
# Return first container ID that looks like the compose service (by label or name)
cid_for_service() {
  local svc="$1"
  # prefer label match (works for both docker/podman compose labels)
  local cid
  cid="$(podman ps -a \
          --filter "label=com.docker.compose.service=${svc}" \
          --format '{{.ID}}' | head -n1 || true)"
  if [[ -z "$cid" ]]; then
    cid="$(podman ps -a \
            --filter "label=io.podman.compose.service=${svc}" \
            --format '{{.ID}}' | head -n1 || true)"
  fi
  # fallback: name contains service
  if [[ -z "$cid" ]]; then
    cid="$(podman ps -a --filter "name=${svc}" -q | head -n1 || true)"
  fi
  echo "$cid"
}

pretty_health() {
  local cid="$1"
  if [[ -z "$cid" ]]; then echo "null"; return 0; fi
  podman inspect -f '{{json .State.Health}}' "$cid" 2>/dev/null | jq .
}

exec_in() {
  local cid="$1"; shift
  if [[ -z "$cid" ]]; then
    echo "container not running"; return 1
  fi
  podman exec "$cid" "$@"
}

inspect_networks() {
  local cid="$1"
  if [[ -z "$cid" ]]; then return 0; fi
  podman inspect -f '{{range $n,$v := .NetworkSettings.Networks}}{{$n}} {{join $v.Aliases ","}}{{end}}' "$CID"
}

# --- resolve container IDs -------------------------------------------------
OM_CID="$(cid_for_service openmetadata || true)"
MYSQL_CID="$(cid_for_service mysql-openmetadata || true)"

echo "OpenMetadata CID:      ${OM_CID:-<none>}"
echo "MySQL (openmetadata):  ${MYSQL_CID:-<none>}"
echo

# 1) Is the MySQL service actually running & healthy?
echo "== MySQL container state/health =="
if [[ -n "${MYSQL_CID:-}" ]]; then
  podman ps -a --filter "id=${MYSQL_CID}" --format '  {{.ID}}\t{{.Names}}\t{{.Status}}'
  pretty_health "$MYSQL_CID"
else
  echo "  mysql-openmetadata not running (no container found)"
fi
echo

# 2) Can OM resolve and reach the hostname?
echo "== Name resolution & TCP reachability from OpenMetadata =="
if [[ -n "${OM_CID:-}" ]]; then
  exec_in "$OM_CID" getent hosts mysql-openmetadata || echo "no DNS"
  exec_in "$OM_CID" sh -lc 'nc -vz mysql-openmetadata 3306 || true'
else
  echo "  openmetadata not running (no container found)"
fi
echo

# 3) Is MySQL listening on 3306 in the container?
echo "== Is MySQL listening on 3306 inside its container? =="
if [[ -n "${MYSQL_CID:-}" ]]; then
  exec_in "$MYSQL_CID" sh -lc 'ss -lntp | grep :3306 || netstat -lntp | grep :3306 || true'
else
  echo "  mysql-openmetadata not running (no container found)"
fi
echo

# 4) Are both services on the SAME user-defined network?
echo "== Network attachments (NetworkID + alias) =="
echo "OpenMetadata:"
inspect_networks "$OM_CID"
echo
echo "MySQL:"
inspect_networks "$MYSQL_CID"
echo

# 5) Does OM point JDBC to the service name (NOT localhost)?
echo "== JDBC env in OpenMetadata =="
if [[ -n "${OM_CID:-}" ]]; then
  exec_in "$OM_CID" printenv | grep -E 'DB_URL|DATABASE_URL|dw\.database\.url' || true
else
  echo "  openmetadata not running (no container found)"
fi
