#!/usr/bin/env bash
# Destroy containers for a specific compose profile, and (optionally) its volumes.
# Bash 3 compatible; safe: won't remove containers outside the selected profile.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: destroy-profile.sh [<profile>] [-r|--profile <profile>] [-p <project>] [-f <compose-file>] [--volumes] [--include-external]

  <profile> / -r, --profile   Compose profile name to destroy (required)
  -p, --project               Compose project name (default: basename of $PWD or "work")
  -f, --file                  Compose file path (default: /work/docker-compose.yml)
  --volumes                   Also remove named volumes actually used by the profile's containers
  --include-external          If --volumes is set, also remove volumes marked external:true
  -h, --help                  Show this help
EOF
}

# -------- defaults --------
PROFILE="${PROFILE:-}"
PROJECT="${PROJECT:-}"
FILE="${FILE:-/work/docker-compose.yml}"
REMOVE_VOLUMES=0
INCLUDE_EXTERNAL=0

# -------- args --------
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -r|--profile) shift; [ $# -gt 0 ] || { echo "❌ --profile requires a value" >&2; exit 2; }; PROFILE="$1" ;;
    --profile=*) PROFILE="${1#*=}" ;;
    -p|--project) shift; [ $# -gt 0 ] || { echo "❌ --project requires a value" >&2; exit 2; }; PROJECT="$1" ;;
    --project=*) PROJECT="${1#*=}" ;;
    -f|--file) shift; [ $# -gt 0 ] || { echo "❌ --file requires a value" >&2; exit 2; }; FILE="$1" ;;
    --file=*) FILE="${1#*=}" ;;
    --volumes) REMOVE_VOLUMES=1 ;;
    --include-external) INCLUDE_EXTERNAL=1 ;;
    --) shift; break ;;
    -*) echo "❌ Unknown option: $1" >&2; usage; exit 2 ;;
    *) pos+=("$1") ;;
  esac
  shift || true
done
[ -n "${PROFILE:-}" ] || { [ ${#pos[@]} -gt 0 ] && PROFILE="${pos[0]}"; }
[ -n "${PROFILE:-}" ] || { echo "❌ Profile is required (positional, --profile, or env PROFILE)"; usage; exit 2; }

# Project default from PWD
if [ -z "${PROJECT:-}" ]; then
  base="$(basename "$(pwd)")"
  PROJECT=$([ -n "$base" ] && [ "$base" != "/" ] && [ "$base" != "." ] && echo "$base" || echo "work")
fi

[ -f "$FILE" ] || { echo "❌ Compose file not found: $FILE" >&2; exit 1; }

# -------- choose compose CLI --------
COMPOSE_BIN=""
if sudo podman compose version >/dev/null 2>&1; then
  COMPOSE_BIN="podman compose"
elif command -v sudo podman-compose >/dev/null 2>&1; then
  COMPOSE_BIN="podman-compose"
else
  echo "❌ Neither sudo podman compose nor sudo podman-compose found." >&2
  exit 1
fi
COMPOSE=(sudo $COMPOSE_BIN -p "$PROJECT" -f "$FILE")

echo "🪪 Project: $PROJECT"
echo "🏷️  Profile: $PROFILE"
echo "📄 Compose: $FILE"
echo "🧰 CLI: $COMPOSE_BIN"

# -------- services in this profile (only) --------
SERVICES="$("${COMPOSE[@]}" --profile "$PROFILE" config --services 2>/dev/null || true)"
if [ -z "$SERVICES" ]; then
  echo "ℹ️  No services reported for profile '$PROFILE' (nothing to do?)"
fi
echo "🔎 Services in profile:"
printf '  - %s\n' $SERVICES 2>/dev/null || true

# -------- collect container IDs for this profile (target set) --------
TARGET_CONTS=""
for s in $SERVICES; do
  ids="$(sudo podman ps -a \
           --filter "label=com.docker.compose.project=$PROJECT" \
           --filter "label=com.docker.compose.service=$s" \
           -q || true)"
  [ -z "$ids" ] || TARGET_CONTS="$TARGET_CONTS $ids"
done
# Dedup; also a helper to test membership
TARGET_CONTS="$(printf '%s\n' $TARGET_CONTS | awk 'NF' | sort -u | tr '\n' ' ')"
in_target() { printf '%s\n' $TARGET_CONTS | grep -q -x "$1"; }

if [ -z "$TARGET_CONTS" ]; then
  echo "ℹ️  No containers found for project=$PROJECT profile=$PROFILE"
fi

# -------- helper: safe removal within profile only --------
rm_within_profile() {
  local id="$1"
  [ -n "$id" ] || return 0

  # If container is NOT in target set, do nothing.
  if ! in_target "$id"; then
    echo "↩️  Skip non-profile container $id"
    return 0
  fi

  # Try direct remove; if dependents exist, remove only dependents that are ALSO in target set.
  if sudo podman rm -f "$id" >/dev/null 2>&1; then
    echo "🗑️  removed $id"
    return 0
  fi

  local err deps d
  err="$(sudo podman rm -f "$id" 2>&1 || true)"
  if printf '%s' "$err" | grep -q 'has dependent containers'; then
    deps="$(printf '%s' "$err" | grep -Eo '[a-f0-9]{64}' | sort -u | tr '\n' ' ')"
    kept_any=0
    for d in $deps; do
      if in_target "$d"; then
        echo "🔗 removing dependent in profile: $d"
        rm_within_profile "$d"
      else
        echo "🛑 dependency outside profile, will keep: $d"
        kept_any=1
      fi
    done
    if [ "$kept_any" -eq 1 ] 2>/dev/null; then
      echo "↩️  Not removing $id because an out-of-profile container depends on it."
      return 0
    fi
    sudo podman rm -f "$id" >/dev/null 2>&1 || true
    echo "🗑️  removed $id after dependents"
    return 0
  fi

  echo "⚠️  could not remove $id : $err" >&2
  return 0
}

# -------- stop & remove only profile containers --------
if [ -n "$TARGET_CONTS" ]; then
  echo "🧹 Stopping/removing profile containers:"
  for c in $TARGET_CONTS; do
    echo "  - $c"
    sudo podman stop -t 10 "$c" >/dev/null 2>&1 || true
    rm_within_profile "$c"
  done
fi

# -------- gather named volumes used by TARGET_CONTS --------
ALL_VOLS=""
for c in $TARGET_CONTS; do
  vlist="$(sudo podman inspect -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{"\n"}}{{end}}{{end}}' "$c" 2>/dev/null || true)"
  [ -z "$vlist" ] || ALL_VOLS="$ALL_VOLS $vlist"
done
ALL_VOLS="$(printf '%s\n' $ALL_VOLS | awk 'NF' | sort -u | tr '\n' ' ')"

# external:true volumes in full config
EXTERNAL_VOLS=""
full_cfg="$("${COMPOSE[@]}" config 2>/dev/null || true)"
if [ -n "$full_cfg" ]; then
  EXTERNAL_VOLS="$(printf '%s\n' "$full_cfg" | awk '
    $0 ~ "^volumes:" {in_v=1; next}
    in_v && $0 ~ "^[^ ]" {in_v=0}
    in_v {
      if ($0 ~ "^  [^ ]") { if (name) { if (ext) print name; name=""; ext=0 } name=$0; sub(/^  /,"",name); sub(":.*","",name) }
      if ($0 ~ "external:[[:space:]]*true") { ext=1 }
    }
    END { if (in_v && name && ext) print name }
  ' | sort -u | tr '\n' ' ')"
fi

# -------- remove volumes only if not used by others --------
if [ $REMOVE_VOLUMES -eq 1 ] && [ -n "$ALL_VOLS" ]; then
  echo "📦 Candidate volumes (profile-only): $ALL_VOLS"
  for v in $ALL_VOLS; do
    # skip non-existent
    sudo podman volume inspect "$v" >/dev/null 2>&1 || continue

    # Skip external:true unless forced
    if printf '%s\n' $EXTERNAL_VOLS | grep -qx "$v"; then
      if [ $INCLUDE_EXTERNAL -ne 1 ]; then
        echo "↩️  Skipping external volume: $v"
        continue
      else
        echo "⚠️  Forcing removal of external volume: $v"
      fi
    fi

    # If any container NOT in target set still uses the volume, skip
    users="$(sudo podman ps -a -q --filter "volume=$v" || true)"
    keep=0
    for u in $users; do
      if ! in_target "$u"; then keep=1; fi
    done
    if [ $keep -eq 1 ]; then
      echo "↩️  Skipping shared volume in use by other profiles: $v"
      continue
    fi

    # Otherwise remove
    # (Remove any remaining profile containers still using it)
    for u in $users; do in_target "$u" && rm_within_profile "$u" || true; done
    sudo podman volume rm -f "$v" >/dev/null 2>&1 || true
    echo "🗑️  removed volume $v"
  done
fi

# best-effort prunes (won’t touch other profiles’ running resources)
sudo podman container prune -f >/dev/null 2>&1 || true
sudo podman network prune   -f >/dev/null 2>&1 || true
[ $REMOVE_VOLUMES -eq 1 ] && sudo podman volume prune -f >/dev/null 2>&1 || true

echo "✅ Done: destroyed profile '$PROFILE' in project '$PROJECT' (without touching other profiles)"
