#!/usr/bin/env bash
# /work/scripts/deploy-profile.sh
set -euo pipefail

usage() {
  echo "Usage: $(basename "$0") <profile> [-p <project>] [-f <compose-file>]" >&2
  exit 2
}

# ---- Defaults (safe with set -u) ----
PROFILE=""
PROJECT="${PROJECT:-$(basename "${PWD:-/work}")}"
FILE="${FILE:-/work/docker-compose.yml}"
DOTENV="${DOTENV:-/work/.env}"
# REBUILD comes from env (e.g. management_menu.sh); default to 0 if not set
REBUILD="${REBUILD:-0}"

# ---- Parse args (bash3-safe) ----
[ $# -ge 1 ] || usage
PROFILE="$1"; shift || true

while [ $# -gt 0 ]; do
  case "$1" in
    -p|--project)
      shift || usage
      PROJECT="${1:-}"
      [ -n "${PROJECT}" ] || usage
      shift || true
      ;;
    -f|--file)
      shift || usage
      FILE="${1:-}"
      [ -n "${FILE}" ] || usage
      shift || true
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      ;;
  esac
done

# ---- Sanity ----
[ -f "$FILE" ] || { echo "❌ Compose file not found: $FILE" >&2; exit 1; }

# ---- Keycloak preflight (validate realm-export.json) ----
if [ "$PROFILE" = "keycloak" ]; then
  FILE_DIR="$(cd "$(dirname "$FILE")" && pwd -P)"
  REALM_JSON="$FILE_DIR/realm-export.json"
  if [ ! -f "$REALM_JSON" ]; then
    echo "❌ Keycloak profile requires $REALM_JSON (mounted to /opt/keycloak/data/import/10-OSSS.json)" >&2
    exit 12
  fi
  # strip BOM, warn on CRLF, validate
  sed -i '1s/^\xEF\xBB\xBF//' "$REALM_JSON" || true
  grep -q $'\r' "$REALM_JSON" && echo "⚠️  $REALM_JSON has CRLF; consider dos2unix" >&2 || true
  if command -v jq >/dev/null 2>&1; then
    jq -e . "$REALM_JSON" >/dev/null || { echo "❌ $REALM_JSON is not valid JSON"; exit 14; }
    echo "🧪 realm-export.json passed jq validation."
  else
    echo "⚠️  jq not found on host; skipping JSON validation."
  fi
fi

# ---- Optional: load simple KEY=VAL from .env (no code exec) ----
PRESERVE=""
if [ -f "$DOTENV" ]; then
  VARS=$(sed -e 's/^[[:space:]]*export[[:space:]]\+//' "$DOTENV" \
         | grep -E '^[A-Za-z_][A-Za-z0-9_]*=' \
         | cut -d= -f1 | tr '\n' ',' | sed 's/,$//') || true
  while IFS= read -r line; do
    case "$line" in ""|\#*) continue ;; esac
    line="${line#export }"
    case "$line" in
      *=*)
        k="${line%%=*}"; v="${line#*=}"
        if [ "${v#\"}" != "$v" ] && [ "${v%\"}" != "$v" ]; then v="${v#\"}"; v="${v%\"}"; fi
        export "$k=$v"
        ;;
    esac
  done < "$DOTENV"
  [ -n "${VARS:-}" ] && PRESERVE="--preserve-env=$VARS"
fi

# ---- Ensure the external podman network exists ----
if ! sudo podman network exists osss-net 2>/dev/null; then
  echo "🌐 Creating external network: osss-net"
  sudo podman network create osss-net >/dev/null
fi

# ---- If compose does NOT declare networks.osss-net, inject a tiny override file ----
OVERRIDE_NET=""
if ! awk '
  BEGIN{n=0}
  /^[[:space:]]*networks:[[:space:]]*$/ {in_n=1; next}
  in_n && /^[[:space:]]*osss-net:[[:space:]]*$/ {n=1}
  END{exit(!n)}
' "$FILE"; then
  OVERRIDE_NET="/tmp/deploy-$$-osss-net.override.yml"
  cat > "$OVERRIDE_NET" <<'YAML'
version: "3.8"
networks:
  osss-net:
    external: true
    name: osss-net
YAML
  echo "🧩 Injecting network override: $OVERRIDE_NET"
fi

# ---- Precreate env_file paths inside Podman volumes (e.g., es-shared/_data/.env.apikey) ----
grep -Eo '/var/lib/containers/storage/volumes/[A-Za-z0-9_.-]+/_data/[^[:space:]]+' "$FILE" 2>/dev/null \
  | while IFS= read -r abs; do
      vol="$(printf "%s" "$abs" | sed -E 's#.*/volumes/([^/]+)/_data/.*#\1#')"
      rel="$(printf "%s" "$abs" | sed -E 's#.*/volumes/[^/]+/_data/(.*)#\1#')"
      [ -n "$vol" ] && [ -n "$rel" ] || continue
      sudo podman volume exists "$vol" 2>/dev/null || sudo podman volume create "$vol" >/dev/null
      mp="$(sudo podman volume inspect "$vol" --format '{{.Mountpoint}}' 2>/dev/null || true)"
      [ -n "$mp" ] || continue
      dst="$mp/$rel"
      if [ ! -f "$dst" ]; then
        echo "📄 Pre-creating env_file: $dst"
        sudo install -Dm600 /dev/null "$dst"
      fi
    done

# ---- Choose compose CLI (support optional override -f) ----
if sudo podman compose version >/dev/null 2>&1; then
  echo "▶ Using: podman compose"
  if [ -n "${OVERRIDE_NET:-}" ]; then
    COMPOSE=(sudo ${PRESERVE:+$PRESERVE} podman compose -p "$PROJECT" -f "$FILE" -f "$OVERRIDE_NET" --profile "$PROFILE")
  else
    COMPOSE=(sudo ${PRESERVE:+$PRESERVE} podman compose -p "$PROJECT" -f "$FILE" --profile "$PROFILE")
  fi
elif command -v sudo podman-compose >/dev/null 2>&1; then
  echo "▶ Using: podman-compose"
  if [ -n "${OVERRIDE_NET:-}" ]; then
    COMPOSE=(sudo ${PRESERVE:+$PRESERVE} podman-compose -p "$PROJECT" -f "$FILE" -f "$OVERRIDE_NET" --profile "$PROFILE")
  else
    COMPOSE=(sudo ${PRESERVE:+$PRESERVE} podman-compose -p "$PROJECT" -f "$FILE" --profile "$PROFILE")
  fi
else
  echo "❌ Neither podman compose nor podman-compose is installed" >&2
  exit 1
fi

echo "📄 Compose: $FILE"
[ -n "${OVERRIDE_NET:-}" ] && echo "📎 Override: $OVERRIDE_NET"
echo "🪪 Project: $PROJECT"
echo "🏷️ Profile: $PROFILE"
echo "🔁 Rebuild: $REBUILD"

export COMPOSE_PROFILES="${PROFILE:-}"

echo "🔎 Services in profile ($PROFILE):"
"${COMPOSE[@]}" config --services || true

# ---- Conditional rebuild based on REBUILD flag ----
if [ "$REBUILD" = "1" ]; then
  echo "🧱 Rebuilding images (no cache) for profile '$PROFILE'…"
  "${COMPOSE[@]}" build --no-cache
else
  echo "⏭️  Skipping image rebuild (REBUILD=$REBUILD)"
fi

echo "🚀 Bringing up…"
"${COMPOSE[@]}" up -d --remove-orphans

# ---- Simple wait: healthy or running or exited 0 ----
service_cid() {
  sudo podman ps -a \
    --filter "label=com.docker.compose.project=$PROJECT" \
    --filter "label=com.docker.compose.service=$1" \
    --format "{{.ID}}" | head -n1
}
wait_one() {
  cid="$1"; [ -n "$cid" ] || return 0
  name="$(sudo podman inspect -f '{{.Name}}' "$cid" | sed 's#^/##')"
  echo "⏳ $name ($cid)…"
  i=0
  while [ $i -lt 600 ]; do
    health="$(sudo podman inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$cid" 2>/dev/null || true)"
    state="$(sudo podman inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || true)"
    exitc="$(sudo podman inspect -f '{{.State.ExitCode}}' "$cid" 2>/dev/null || echo "")"
    case "$health:$state:$exitc" in
      healthy:running:*)  echo "✅ $name healthy"; return 0 ;;
      :running:*)         echo "✅ $name running"; return 0 ;;
      *:exited:0)         echo "✅ $name completed"; return 0 ;;
      *:exited:*)         echo "❌ $name exit=$exitc"; sudo podman logs --tail=200 "$cid" || true; return 1 ;;
    esac
    i=$((i+2)); sleep 2
  done
  echo "❌ timeout $name"; sudo podman logs --tail=200 "$cid" || true; return 1
}

rc=0
for s in $("${COMPOSE[@]}" config --services); do
  cid="$(service_cid "$s")"
  [ -z "$cid" ] || wait_one "$cid" || rc=1
done

echo; echo "▶ Final:"
"${COMPOSE[@]}" ps || true
exit "$rc"
