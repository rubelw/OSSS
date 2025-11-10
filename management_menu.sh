#!/usr/bin/env bash
# management_menu.sh (Podman-only)
# - Uses Podman + Podman Compose exclusively
# - Adds 127.0.0.1 keycloak.local to /etc/hosts if missing
# - Has helpers to start profiles and view logs
# - Runs build_realm.py after Keycloak is up

set -Eeuo pipefail

# ---- debug harness ----------------------------------------------------------
: "${OSSS_DEBUG:=0}"         # set OSSS_DEBUG=0 to silence
if [[ "$OSSS_DEBUG" == "1" ]]; then
  export SHELLOPTS  # so 'set -o' is inherited in subshells
  set -o errtrace
  PS4='+ [${BASH_SOURCE##*/}:${LINENO}](${FUNCNAME[0]:-main}) '
  set -x
  trap 'echo "🔥 ERR at ${BASH_SOURCE##*/}:${LINENO} (in ${FUNCNAME[0]:-main}) running: ${BASH_COMMAND}"' ERR
fi

dbg() { [[ "$OSSS_DEBUG" == "1" ]] && echo "🪵 DBG: $*" 1>&2; }
# ---------------------------------------------------------------------------


: "${OSSS_VENV_BOOTSTRAPPED:=0}"
: "${TMP_COMPOSE:=/tmp/osss-elastic.compose.yml}"
export TMP_COMPOSE
: "${VM_NAME:=${PODMAN_MACHINE_NAME:-${PODMAN_MACHINE:-default}}}"
export VM_NAME

: "${PODMAN_MACHINE_ROOTFUL:=1}"
export PODMAN_MACHINE_ROOTFUL
: "${PODMAN_ENABLE_ROOTLESS:=0}"
export PODMAN_ENABLE_ROOTLESS
: "${VM_TMP:=/tmp/osss-elastic.compose.yml}"
export VM_TMP

DEBUG=1


VM_NAME="${VM_NAME:-default}"
NONINTERACTIVE="${NONINTERACTIVE:-0}"

info(){ printf "ℹ️   %s\n" "$*"; }
ok(){ printf "✅  %s\n" "$*"; }
warn(){ printf "⚠️   %s\n" "$*"; }
err(){ printf "❌  %s\n" "$*" >&2; }

have_cmd(){ command -v "$1" >/dev/null 2>&1; }

need_cmd(){ if ! have_cmd "$1"; then err "Missing required command: $1"; exit 127; fi; }

need_cmd podman

_pm() { podman machine "$@"; }

pm_ssh() { podman machine "$@"; }

# Wait until `podman machine ssh` actually works (no manual port scraping)
wait_vm_ssh(){
  local tries=60
  info "[ensure_podman_ready] waiting for 'podman machine ssh ${VM_NAME}' to be usable…"
  while ! podman machine ssh "$VM_NAME" -- bash -lc 'echo -n ok' >/dev/null 2>&1; do
    tries=$((tries-1))
    if [ $tries -le 0 ]; then
      err "podman machine ssh still not usable"
      return 1
    fi
    sleep 2
  done
  ok "SSH usable for VM '${VM_NAME}'"
}

ensure_vm_running(){
  # init if missing
  if ! _pm inspect "$VM_NAME" >/dev/null 2>&1; then
    info "[ensure_podman_ready] init VM '${VM_NAME}' (one time)…"
    _pm init "$VM_NAME"
  fi
  # start if not running
  if ! _pm inspect "$VM_NAME" --format '{{.State}}' 2>/dev/null | grep -qx 'running'; then
    info "[ensure_podman_ready] starting VM '${VM_NAME}'…"
    _pm start "$VM_NAME"
  fi
  wait_vm_ssh
}

# Run a command inside the VM as the default user (rootless)
in_vm(){
  # shellcheck disable=SC2029
  podman machine ssh "$VM_NAME" -- bash -lc "$*"
}

# Install podman-compose (idempotent) via rpm-ostree and reboot if needed
install_podman_compose_vm(){
  # Make this block resilient to benign failures
  set +e
  set +o pipefail

  local REBOOTED=0
  local VM="${VM_NAME:-${1:-$VM_CHOSEN}}"
  [ -z "$VM" ] && VM="default"

  info "▶ Installing podman-compose in VM '${VM}' (rpm-ostree)…"

  # Fast path: already available?
  if in_vm 'command -v podman-compose >/dev/null 2>&1'; then
    ok "podman-compose already installed (found on PATH)."
  else
    # Double-check via RPM database (helps during staged deployments)
    if in_vm 'rpm -q podman-compose >/dev/null 2>&1'; then
      ok "podman-compose already layered via rpm-ostree (rpm -q present)."
    else
      # Attempt to layer it
      local OUT
      OUT="$(in_vm 'rpm-ostree install -y podman-compose python3-dotenv' 2>&1)"
      local RC=$?
      if [ $RC -ne 0 ]; then
        if printf '%s' "$OUT" | grep -qi 'already requested'; then
          info "rpm-ostree reports 'already requested' — likely needs reboot to apply; proceeding."
        else
          echo "$OUT"
          warn "rpm-ostree install failed (rc=$RC). Continuing to check staged state."
        fi
      fi
      info "Rebooting VM to apply rpm-ostree changes…"
      podman machine ssh "$VM" -- systemctl reboot || true
      # Wait briefly and ensure VM is back
      sleep 2
      ensure_vm_ready "$VM" || true
      REBOOTED=1
    fi
  fi

  # Configure compose provider (safe even if already configured)
  info "▶ Configuring Podman to use the external compose provider 'podman-compose'…"
  in_vm 'mkdir -p ~/.config/containers
[ -f ~/.config/containers/containers.conf ] || : > ~/.config/containers/containers.conf
grep -q "compose_providers" ~/.config/containers/containers.conf 2>/dev/null || cat >~/.config/containers/containers.conf <<EOF
[engine]
compose_providers=["podman-compose"]
EOF
echo "--- containers.conf ---"; nl -ba ~/.config/containers/containers.conf | sed -n "1,200p"
echo
echo "-- which podman-compose --"; command -v podman-compose || true
echo
echo "-- podman compose version --"; podman compose version || true
'
  ok "compose provider configured."

  # Restore shell strictness
  set -e
  set -o pipefail
}

# Enable both sockets (idempotent)
enable_podman_sockets(){
  info "🔌 Ensuring rootless podman.socket is active in VM '${VM_NAME}'…"
  in_vm 'systemctl --user enable --now podman.socket; systemctl --user status --no-pager podman.socket || true'
  info "🔌 Ensuring rootful podman.socket is active in VM '${VM_NAME}'…"
  in_vm 'sudo systemctl enable --now podman.socket; sudo systemctl status --no-pager podman.socket || true'
}

# Show connection list from host POV
show_connections(){
  podman system connection list || true
}




# Resolve correct VM podman.sock path: rootful (uid 0) vs rootless (uid 1000)
resolve_vm_podman_sock() {
  local NAME="${PODMAN_MACHINE_NAME:-default}"
  if podman machine ssh "$NAME" -- test -S /run/user/0/podman/podman.sock; then
    echo /run/user/0/podman/podman.sock
    return 0
  fi
  if podman machine ssh "$NAME" -- test -S /run/user/1000/podman/podman.sock; then
    echo /run/user/1000/podman/podman.sock
    return 0
  fi
  echo /run/user/1000/podman/podman.sock
}
VM_PODMAN_SOCK="$(resolve_vm_podman_sock)"
export VM_PODMAN_SOCK

# Install podman-compose inside the VM (system package) and configure Podman to use it
install_podman_compose_vm() {
  set -euo pipefail

  local vm
  vm="$(podman machine active 2>/dev/null || echo default)"
  echo "▶️ Target VM: ${vm}"

  echo "▶️ Installing system podman-compose in '${vm}' (rpm-ostree)…"
  podman machine ssh "${vm}" -- bash -s <<'VM1'
set -euo pipefail
# 1) remove any user shim to avoid loops
rm -f "$HOME/bin/podman-compose" || true

# 2) install system podman-compose (requires reboot to apply)
sudo rpm-ostree install -y podman-compose || { echo "rpm-ostree install failed"; exit 1; }

echo "Rebooting VM to apply rpm-ostree changes…"
nohup sh -lc "sleep 1; sudo systemctl reboot" >/dev/null 2>&1 &
VM1

  echo "▶️ Waiting for VM reboot…"
  # 1) wait for SSH to drop
  for i in {1..120}; do
    if ! podman machine ssh "${vm}" -- true >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  # 2) wait for SSH to come back
  for i in {1..240}; do
    if podman machine ssh "${vm}" -- true >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done

  echo "▶️ Configuring Podman to use the external provider 'podman-compose'…"
  podman machine ssh "${vm}" -- bash -s <<'VM2'
set -euo pipefail

# 3) Set compose_providers to use podman-compose
mkdir -p "$HOME/.config/containers"
cat > "$HOME/.config/containers/containers.conf" <<'EOF'
[engine]
compose_providers=["podman-compose"]
EOF

# 4) Sanity checks
echo "--- containers.conf ---"
grep -n '^compose_providers' "$HOME/.config/containers/containers.conf" || true

echo
echo "-- which podman-compose --"
command -v podman-compose || { echo "podman-compose not found on PATH"; exit 1; }

echo
echo "-- podman compose version --"
podman compose version 2>&1 | sed -n '1,6p'
VM2

  echo "✅ podman-compose installed & configured for VM '${vm}'."
}



ensure_podman_ready() {
  set -euo pipefail
  echo "[ensure_podman_ready] checking podman…"

  unset CONTAINER_HOST PODMAN_HOST XDG_RUNTIME_DIR DOCKER_HOST

  local vm="${PODMAN_MACHINE_NAME:-${PODMAN_MACHINE:-default}}"
  local created_new_vm=0

  # Fast path
  if podman info >/dev/null 2>&1; then
    echo "[ensure_podman_ready] podman info ok"
    return 0
  fi

  # Create/init VM if missing
  if ! podman machine inspect "$vm" >/dev/null 2>&1; then
    echo "[ensure_podman_ready] init VM '$vm' (one time)…"
    created_new_vm=1
    podman machine init "$vm" \
      --rootful \
      --cpus "${PODMAN_MACHINE_CPUS:-12}" \
      --memory "${PODMAN_MACHINE_MEM_MB:-40960}" \
      --disk-size "${PODMAN_MACHINE_DISK_GB:-100}" \
      --volume "${PWD}:/work" >/dev/null 2>&1 || true
  fi

  # Start if needed
  if [ "$(podman machine inspect --format '{{.State}}' "$vm" 2>/dev/null || echo "")" != "running" ]; then
    echo "[ensure_podman_ready] starting VM '$vm'…"
    podman machine start "$vm" >/dev/null 2>&1 || true
  fi

  # Helpers
  _refresh_conninfo() {
    # Prefer data from 'podman system connection list' because it already knows the active forwarded port
    # Example URI: ssh://core@127.0.0.1:57255/run/user/501/podman/podman.sock
    local line uri
    line="$(podman system connection list --format '{{.Name}} {{.URI}}' 2>/dev/null \
            | awk '$1=="default"{print; exit}')"
    if [ -n "$line" ]; then
      uri="${line#* }"
      # uri looks like: ssh://core@127.0.0.1:57255/run/user/501/podman/podman.sock
      # Extract host & port with BSD-compatible sed -E and explicit capture groups
      # uri looks like: ssh://core@127.0.0.1:57255/run/user/501/podman/podman.sock
      HOST_IP="$(printf '%s\n' "$uri" | awk -F'[@:/]' '{print $3}')"
      HOST_PORT="$(printf '%s\n' "$uri" | awk -F'[@:/]' '{print $4}')"
      : "${HOST_IP:=127.0.0.1}"

    fi

    # Fallback to machine inspect if needed (older podman sometimes lacks .ConnectionInfo.Port)
    if [ -z "${HOST_PORT:-}" ]; then
      HOST_IP="$(podman machine inspect --format '{{.ConnectionInfo.HostIP}}' "$vm" 2>/dev/null || true)"
      HOST_PORT="$(podman machine inspect --format '{{index .ConnectionInfo "Port"}}' "$vm" 2>/dev/null || true)"
    fi

    # Last-ditch defaults
    HOST_IP="$(podman machine inspect --format '{{.ConnectionInfo.HostIP}}' default 2>/dev/null || echo 127.0.0.1)"
    HOST_PORT="$(podman machine inspect --format '{{.ConnectionInfo.Port}}'   default 2>/dev/null || echo 22)"
    REMOTE_USER="$(podman machine inspect --format '{{.ConnectionInfo.RemoteUsername}}' default 2>/dev/null || echo core)"
    REMOTE_UID="$(podman machine ssh "$vm" -- id -u "$REMOTE_USER" 2>/dev/null || echo 1000)"
  }

  _wait_ssh() {
    local tries=0
    while :; do
      if podman machine ssh "$vm" -- true >/dev/null 2>&1; then return 0; fi
      tries=$((tries+1))
      [ $tries -ge 120 ] && return 1
      sleep 1
    done
  }

  # Wait for SSH
  _refresh_conninfo
  echo "[ensure_podman_ready] waiting for SSH on ${HOST_IP}:${HOST_PORT}…"
  _wait_ssh || { echo "[ensure_podman_ready][ERR] cannot SSH to VM."; return 1; }

  # If brand new, layer podman-compose and reboot once
  if [ "$created_new_vm" -eq 1 ]; then
    echo "[ensure_podman_ready] fresh VM detected — ensuring podman-compose is installed…"
    if command -v install_podman_compose_vm >/dev/null 2>&1; then
      install_podman_compose_vm "$vm"
    else
      podman machine ssh "$vm" -- bash -lc 'set -e
        if command -v podman-compose >/dev/null 2>&1 || rpm -q podman-compose >/dev/null 2>&1; then
          exit 0
        fi
        sudo rpm-ostree install -y podman-compose >/dev/null
        nohup sh -c "sleep 1; sudo systemctl reboot" >/dev/null 2>&1 &
      '
      echo "[ensure_podman_ready] waiting for VM reboot…"
      # Wait for reboot cycle
      for _ in $(seq 1 180); do
        sleep 1
        if podman machine ssh "$vm" -- true >/dev/null 2>&1; then break; fi
      done
      # SSH port may have changed — refresh
      _refresh_conninfo
      _wait_ssh || { echo "[ensure_podman_ready][ERR] VM not reachable post-reboot."; return 1; }
      # Quick sanity
      podman machine ssh "$vm" -- podman-compose --version >/dev/null 2>&1 || true
    fi

    # Configure external provider once in the VM
    podman machine ssh "$vm" -- bash -lc 'set -e
      CFG=/etc/containers/containers.conf
      sudo mkdir -p /etc/containers
      if [ -f "$CFG" ]; then
        if ! grep -q "^compose_providers=.*podman-compose" "$CFG"; then
          sudo awk '\''BEGIN{done=0} /^compose_providers=/ && !done {sub(/\]$/, ",\"podman-compose\"]"); done=1} {print} END{if(!done) print "compose_providers=[\"podman-compose\"]"}'\'' "$CFG" | sudo tee "$CFG" >/dev/null
        fi
      else
        echo "compose_providers=[\"podman-compose\"]" | sudo tee "$CFG" >/dev/null
      fi
    '
  fi

  # Ensure sockets (rootless + rootful), no stray `set` calls
  echo "[ensure_podman_ready] ensuring rootless podman socket (idempotent)…"
  podman machine ssh "$vm" -- bash -lc 'set -e
    uid=$(id -u)
    export XDG_RUNTIME_DIR=/run/user/$uid
    mkdir -p "$XDG_RUNTIME_DIR" || true
    loginctl enable-linger "$(id -un)" >/dev/null 2>&1 || true
    systemctl --user is-active podman.socket >/dev/null 2>&1 || systemctl --user enable --now podman.socket >/dev/null 2>&1 || true
    test -S "$XDG_RUNTIME_DIR/podman/podman.sock" && echo "rootless sock ok"
  ' || true

  echo "[ensure_podman_ready] ensuring ROOTFUL podman socket (idempotent)…"
  podman machine ssh "$vm" -- bash -lc 'set -e
    systemctl is-active podman.socket >/dev/null 2>&1 || sudo systemctl enable --now podman.socket >/dev/null 2>&1 || true
    test -S /run/podman/podman.sock && echo "rootful sock ok"
  ' || true

  # Re-read host/port (it can change after reboot)
  _refresh_conninfo

  # Build URIs from the CURRENT port
  rootless_name="machine-default"
  root_name="machine-default-root"
  rootless_uri="ssh://${REMOTE_USER}@${HOST_IP}:${HOST_PORT}/run/user/${REMOTE_UID}/podman/podman.sock"
  root_uri="ssh://root@${HOST_IP}:${HOST_PORT}/run/podman/podman.sock"

  # Clean out stale entries, then add the fresh ones
  podman system connection remove "$rootless_name" >/dev/null 2>&1 || true
  podman system connection remove "$root_name"    >/dev/null 2>&1 || true
  podman system connection add "$rootless_name" "$rootless_uri" --default >/dev/null 2>&1 || true
  podman system connection add "$root_name"    "$root_uri"               >/dev/null 2>&1 || true

  # Prefer rootful if it actually works; otherwise stick with rootless
  if podman --connection "$root_name" info >/dev/null 2>&1; then
    podman system connection default "$root_name" >/dev/null 2>&1 || true
  elif podman --connection "$rootless_name" info >/dev/null 2>&1; then
    podman system connection default "$rootless_name" >/dev/null 2>&1 || true
  else
    echo "[ensure_podman_ready][ERR] podman still unavailable after sockets/connection."
    podman system connection list || true
    exit 1
  fi

  echo "[ensure_podman_ready] ready."
}





# Ensure the rootless Podman user socket is running inside the Podman VM
# Usage: vm_enable_rootless_podman_socket [vm_name]
vm_enable_rootless_podman_socket() {
  local VM="${1:-default}"
  echo "🔌 Ensuring rootless podman.socket is active in VM '${VM}'…"
  podman machine ssh "$VM" -- bash -lc '
    set -euo pipefail
    ME="$(id -un)"
    MY_UID="$(id -u)"                           # <-- do NOT assign to $UID (readonly)
    SOCK="/run/user/${MY_UID}/podman/podman.sock"

    # If the socket is already there, we are done.
    if [ -S "$SOCK" ]; then
      echo "[ok] socket already present: $SOCK"
      ls -l "$SOCK" || true
      exit 0
    fi

    # Make sure lingering is enabled, otherwise user services won’t survive/log in
    if ! loginctl show-user "$ME" 2>/dev/null | grep -q "^Linger=yes$"; then
      echo "[info] enabling linger for $ME"
      loginctl enable-linger "$ME" || true
    fi

    # Enable & start the user socket
    systemctl --user enable --now podman.socket

    # Wait briefly for the socket to appear
    for i in $(seq 1 30); do
      if [ -S "$SOCK" ]; then
        echo "[ok] user socket is up: $SOCK"
        ls -l "$SOCK" || true
        exit 0
      fi
      sleep 0.5
    done

    echo "[err] user socket did not appear at $SOCK"
    echo "— journalctl (user podman.socket) —"
    journalctl --no-pager --user -u podman.socket -n 100 || true
    exit 1
  '
}


# Run readiness checks *before* any other podman calls from this script
#ensure_vm_ready || { echo "[ERR] podman is not ready. Run this on your Mac with 'podman machine' running, or inside the VM with XDG_RUNTIME_DIR set."; exit 1; }

# --- Smart socket enablement: VM-aware (macOS) or host fallback (Linux) ---
os_is_darwin() { [ "$(uname -s)" = "Darwin" ]; }
have_podman_machine() { podman machine --help >/dev/null 2>&1; }

podman_machine_exists() {
  local NAME="${1:-default}"

# Ensure a VM is configured as rootful (must be STOPPED); no-op if already rootful
ensure_vm_rootful_config() {
  local NAME="${1:-default}"
  # Only applicable when podman machine exists
  podman machine inspect "$NAME" >/dev/null 2>&1 || return 0

  # Detect current rootful flag using a portable template (older podman may not expose .Config.Rootful)
  local IS_ROOTFUL
  IS_ROOTFUL="$(podman machine inspect --format '{{.Config.Rootful}}' "$NAME" 2>/dev/null || echo "")"
  if [ "$IS_ROOTFUL" = "true" ]; then
    echo "[ensure_vm_rootful_config] VM '$NAME' already rootful."
    return 0
  fi

  # Must be stopped to toggle
  if [ "$(podman machine inspect --format '{{.State}}' "$NAME" 2>/dev/null || echo "")" = "running" ]; then
    echo "[ensure_vm_rootful_config] Stopping running VM '$NAME' to toggle rootful…"
    podman machine stop "$NAME" >/dev/null 2>&1 || true
  fi

  echo "[ensure_vm_rootful_config] Setting VM '$NAME' to --rootful…"
  podman machine set --rootful "$NAME"
}

  podman machine inspect "$NAME" >/dev/null 2>&1
}

ensure_vm_ready() {
  local NAME="${1:-default}" state rc=0
  # Create only if truly missing
  if ! podman machine inspect "$NAME" >/dev/null 2>&1; then
    echo "🆕 No Podman VM named '$NAME' found. Initializing…"
    podman machine init "$NAME" \
      --rootful \
      --cpus "${PODMAN_MACHINE_CPUS:-12}" \
      --memory "${PODMAN_MACHINE_MEM_MB:-40960}" \
      --disk-size "${PODMAN_MACHINE_DISK_GB:-100}" \
      --volume "${PWD}:/work" || return $?
  fi

  state="$(podman machine inspect --format '{{.State}}' "$NAME" 2>/dev/null || true)"
  if [ "$state" = "running" ]; then
    echo "ℹ️  Podman VM '$NAME' already running."
  else
    echo "▶️  Starting Podman VM '$NAME'…"
    for i in 1 2 3; do
      if out="$(podman machine start "$NAME" 2>&1)"; then rc=0; break; else rc=$?
        if printf '%s' "$out" | grep -qi 'already running'; then rc=0; break; fi
        echo "⚠️  start attempt $i failed: $out"; sleep 2
      fi
    done
    [ $rc -ne 0 ] && { echo "❌  Failed to start VM '$NAME'"; return $rc; }
  fi

  # Prefer API readiness; SSH can flap on macOS
  if ! podman info >/dev/null 2>&1; then
    # Try to select a viable connection (rootful if present)
    podman system connection default "${NAME}-root" >/dev/null 2>&1 || \
    podman system connection default "$NAME" >/dev/null 2>&1 || true
    for t in $(seq 1 60); do
      podman info >/dev/null 2>&1 && { echo "✅ Podman API ready."; return 0; }
      sleep 1
    done
    echo "⌛ API not up, checking SSH…"
    for t in $(seq 1 120); do
      podman machine ssh "$NAME" -- true >/dev/null 2>&1 && break
      sleep 1
    done
    podman info >/dev/null 2>&1 || { echo "❌ Podman not reachable"; return 1; }
  fi
}

# --- Ensure rootful API connection exists on host (macOS) and set it default ---
ensure_rootful_connection_on_host() {
  # relax strict mode inside this function (probes can return non-zero)
  set +e
  set +o pipefail

  local NAME="${1:-default}"

  # Make sure rootful socket is alive inside the VM
  podman machine ssh "$NAME" 'sudo systemctl enable --now podman.socket >/dev/null 2>&1 || true'

  # If a rootful connection exists and works, use it
  if podman system connection ls --format '{{.Name}} {{.URI}}' 2>/dev/null \
     | awk '{print $1}' | grep -x "${NAME}-root" >/dev/null 2>&1; then
    podman system connection default "${NAME}-root" >/dev/null 2>&1 || true
    if podman info >/dev/null 2>&1; then
      echo "✅ Using existing rootful connection '${NAME}-root'."
      set -e; set -o pipefail; return 0
    fi
  fi

  # Build connection URI from machine inspect (port + identity)
  local PORT IDENTITY USER HOST URI
  PORT="$(podman machine inspect --format '{{ (index .ConnectionInfo.PodmanSSHConfig 0).Port }}' "$NAME" 2>/dev/null)"
  IDENTITY="$(podman machine inspect --format '{{ (index .ConnectionInfo.PodmanSSHConfig 0).IdentityPath }}' "$NAME" 2>/dev/null)"
  USER="core"; HOST="127.0.0.1"

  if [ -z "$PORT" ] || [ -z "$IDENTITY" ]; then
    echo "❌ Could not derive SSH port/identity for VM '$NAME'."
    set -e; set -o pipefail; return 1
  fi

  URI="ssh://${USER}@${HOST}/run/podman/podman.sock?identity=${IDENTITY}&port=${PORT}"

  # Add or update the connection safely
  podman system connection remove "${NAME}-root" >/dev/null 2>&1 || true
  echo "➕ Adding rootful host connection '${NAME}-root' → ${URI}"
  podman system connection add "${NAME}-root" "${URI}" >/dev/null 2>&1 || true
  podman system connection default "${NAME}-root" >/dev/null 2>&1 || true

  if podman info >/dev/null 2>&1; then
    echo "✅ Rootful API reachable via connection '${NAME}-root'."
    set -e; set -o pipefail; return 0
  else
    echo "❌ Rootful API still not reachable after adding connection."
    podman system connection ls || true
    set -e; set -o pipefail; return 1
  fi
}

vm_enable_rootless_podman_socket_safe() {
  local NAME="${1:-default}"
  echo "🔌 Ensuring rootless podman.socket is active in VM '$NAME'…"
  # Enable rootless socket for the 'core' user inside the VM
  podman machine ssh "$NAME" 'loginctl enable-linger $USER >/dev/null 2>&1 || true; systemctl --user enable --now podman.socket; systemctl --user status --no-pager podman.socket || true'
}

vm_enable_rootful_podman_socket_safe() {
  local NAME="${1:-default}"
  echo "🔌 Enabling rootful podman services (systemd) in VM '${NAME}' …"
  podman machine ssh "$NAME" -- bash -lc '
    set -euo pipefail
    sudo systemctl daemon-reload || true
    sudo systemctl enable --now podman.socket || true
    sudo systemctl enable --now podman.service || true
    echo "🩺 podman.service:"; sudo systemctl --no-pager --full status podman.service || true
    echo "🩺 podman.socket:";  sudo systemctl --no-pager --full status podman.socket  || true
    if sudo test -S /run/podman/podman.sock; then
      echo "✅ Rootful API socket is present at /run/podman/podman.sock"
    else
      echo "❌ Rootful API socket missing. Attempting restart…"
      sudo systemctl restart podman.socket podman.service || true
      sleep 1
      sudo test -S /run/podman/podman.sock || { echo "❌ Still missing rootful API socket."; exit 1; }
      echo "✅ Rootful API socket appeared after restart."
    fi
  '
}


# Enable sockets on *host* (Linux without VM)
host_enable_rootless_podman_socket_maybe() {

  echo "🔌 Ensuring rootless podman.socket is active on host…"
  systemctl --user enable --now podman.socket >/dev/null 2>&1 || true
  systemctl --user status --no-pager podman.socket || true

}
# Wrapper to honor PODMAN_ENABLE_ROOTLESS
host_enable_rootless_podman_socket_maybe_maybe() {
  if [ "${PODMAN_ENABLE_ROOTLESS}" = "1" ]; then
    host_enable_rootless_podman_socket_maybe
  else
    echo "ℹ️  Skipping rootless host socket (PODMAN_ENABLE_ROOTLESS=0)"
  fi
}

host_enable_rootful_podman_socket() {
  echo "🔌 Ensuring rootful podman.socket is active on host…"
  sudo systemctl enable --now podman.socket >/dev/null 2>&1 || true
  sudo systemctl status --no-pager podman.socket || true
}

VM_CHOSEN="${PODMAN_MACHINE:-default}"

# --- Ensure host podman CLI points at the VM API connection (macOS) ---
ensure_host_podman_connection() {
  local NAME="${1:-default}"
  # Try to set "default" first
  podman system connection default "$NAME" >/dev/null 2>&1 || true

  # If still not reachable, try common fallbacks
  if ! podman info >/dev/null 2>&1; then
    for alt in "${NAME}" "${NAME}-root" "podman-machine-${NAME}" "podman-machine-${NAME}-root"; do
      podman system connection default "$alt" >/dev/null 2>&1 || true
      podman info >/dev/null 2>&1 && break
    done
  fi

  # As a last resort, pick the first listed connection
  if ! podman info >/dev/null 2>&1; then
    first="$(podman system connection ls --format '{{.Name}}' 2>/dev/null | head -n1)"
    if [ -n "$first" ]; then
      podman system connection default "$first" >/dev/null 2>&1 || true
    fi
  fi
}


if os_is_darwin && have_podman_machine; then
  # macOS path: always use a VM; auto-init/start if needed.
  # VM will be set to rootful before first start.
  ensure_vm_ready "$VM_CHOSEN"

  ensure_rootful_connection_on_host "$VM_CHOSEN"
  # Enable sockets first (some compose installers probe the API)
  if [ "${PODMAN_ENABLE_ROOTLESS}" = "1" ]; then vm_enable_rootless_podman_socket_safe "$VM_CHOSEN"; else echo "ℹ️  Skipping rootless socket (PODMAN_ENABLE_ROOTLESS=0)"; fi
  vm_enable_rootful_podman_socket_safe "$VM_CHOSEN"

  # Install podman-compose inside the VM and configure compose provider (may reboot the VM)
  VM_NAME="$VM_CHOSEN"
  if ! podman machine inspect "$VM_NAME" --format '{{.State}}' 2>/dev/null | grep -qx running; then
    # VM is not running yet → allow first-boot install
    install_podman_compose_vm
  else
    # VM is already up → skip if podman-compose is present or layered
    if podman machine ssh "$VM_NAME" -- 'command -v podman-compose >/dev/null 2>&1 || rpm -q podman-compose >/dev/null 2>&1'; then
      echo "⏭️  Skipping system podman-compose install (already present/layered)."
    else
      install_podman_compose_vm
    fi
  fi

  # After rpm-ostree reboot, re-assert sockets and refresh host connection
  if [ "${PODMAN_ENABLE_ROOTLESS}" = "1" ]; then vm_enable_rootless_podman_socket_safe "$VM_CHOSEN"; else echo "ℹ️  Skipping rootless socket (PODMAN_ENABLE_ROOTLESS=0)"; fi
  vm_enable_rootful_podman_socket_safe "$VM_CHOSEN"
  ensure_host_podman_connection "$VM_CHOSEN"

  # Final macOS health check (no sudo)
  if ! podman info >/dev/null 2>&1; then
    echo "❌ Podman not reachable (host CLI not connected to VM API). Try: podman system connection ls"
    exit 1
  fi
elif have_podman_machine && podman_machine_exists "$VM_CHOSEN"; then
  # Non-mac with VM available
  if [ "${PODMAN_ENABLE_ROOTLESS}" = "1" ]; then vm_enable_rootless_podman_socket_safe "$VM_CHOSEN"; else echo "ℹ️  Skipping rootless socket (PODMAN_ENABLE_ROOTLESS=0)"; fi
  vm_enable_rootful_podman_socket_safe "$VM_CHOSEN"
else
  # Pure Linux host fallback (no VM present)
  echo "ℹ️  No Podman VM named '$VM_CHOSEN' detected; using host sockets."
  host_enable_rootless_podman_socket_maybe
  host_enable_rootful_podman_socket
fi



HOST_PROJ="$(pwd -P)"
COMPOSE_PROFILES_VERBOSE=1
export PODMAN_MACHINE="${PODMAN_MACHINE:-default}"
# Only compute overlay dir *after* ensure_podman_ready succeeded.
export PODMAN_OVERLAY_DIR="$(
  podman machine ssh "${PODMAN_MACHINE}" -- \
    sudo podman info | awk -F': *' 'tolower($1) ~ /graphroot/ { gsub(/[[:space:]]+/,"",$2); print $2 "/overlay-containers"; exit }'
)"
echo "$PODMAN_OVERLAY_DIR"   # sanity check; should exist inside VM

# --- Ollama preflight check (volume-aware, nounset-safe) ---
# Ensure host Ollama is ready and that MODEL is present in ./ollama_data/models
# Usage: check_ollama_ready [model_name]
check_ollama_ready() {
  set -euo pipefail

  local MODEL_NAME="${1:-llama3.1}"
  # Allow override via env; default to ./ollama_data
  local OLLAMA_DATA_DIR="${OLLAMA_DATA_DIR:-./ollama_data}"
  local MODELS_DIR="${OLLAMA_DATA_DIR%/}/models"

  echo "🧠 Checking host Ollama and model '${MODEL_NAME}' …"

  # 1) Host ollama binary
  if ! command -v ollama >/dev/null 2>&1; then
    echo "❌ 'ollama' not found in PATH. On macOS: brew install --cask ollama"
    exit 1
  fi
  echo "✅ Ollama found: $(command -v ollama)"
  echo "   Version: $(ollama --version 2>/dev/null || echo 'unknown')"

  # 2) Ensure Ollama key dir exists (~/.ollama) and key is present
  if [ ! -d "${HOME}/.ollama" ]; then
    echo "📂 Creating ${HOME}/.ollama"
    mkdir -p "${HOME}/.ollama"
  fi
  if [ ! -f "${HOME}/.ollama/id_ed25519" ]; then
    echo "🔑 Initializing Ollama registry key (~/.ollama/id_ed25519)"
    # Try the easy way (starts server briefly which generates the key)
    (OLLAMA_MODELS="${MODELS_DIR}" ollama serve >/dev/null 2>&1 & sleep 2; kill $! >/dev/null 2>&1 || true) || true
    # Fallback: generate a key if it still doesn't exist
    if [ ! -f "${HOME}/.ollama/id_ed25519" ]; then
      ssh-keygen -t ed25519 -f "${HOME}/.ollama/id_ed25519" -N "" >/dev/null
    fi
  fi

  # 3) Ensure custom models dir exists
  if [ ! -d "${MODELS_DIR}" ]; then
    echo "📂 Creating models directory at ${MODELS_DIR}"
    mkdir -p "${MODELS_DIR}"
  fi
  echo "📦 Using OLLAMA_MODELS=${MODELS_DIR}"

  # Helper to run ollama against our models dir
  _ollama() { OLLAMA_MODELS="${MODELS_DIR}" ollama "$@"; }

  # 4) Check model; pull if missing
  if ! _ollama show "${MODEL_NAME}" >/dev/null 2>&1; then
    echo "⬇️  Pulling '${MODEL_NAME}' into ${MODELS_DIR} …"
    _ollama pull "${MODEL_NAME}"
  fi

  echo "✅ Model '${MODEL_NAME}' available in ${MODELS_DIR}"
}


check_ollama_ready

# --- Bash 3.x compatibility shims (macOS default shell lacks mapfile/readarray) ---
if ! command -v mapfile >/dev/null 2>&1; then
  mapfile() {


    # supports: mapfile -t ARRAY  (reads from stdin)
    local strip=0 OPTIND=1 OPTARG
    while getopts "t" opt; do
      case "$opt" in
        t) strip=1 ;;
      esac
    done
    shift $((OPTIND-1))
    local __arr_name="$1"
    local __i=0 __line
    # ensure target exists as an array
    eval "$__arr_name=()"
    while IFS= read -r __line; do
      # -t behavior: strip trailing newline
      (( strip )) && __line="${__line%$'\n'}"
      eval "$__arr_name[__i]=\$__line"
      __i=$((__i+1))
    done
  }
fi


# Bash 3.x on macOS doesn't have readarray; alias it to mapfile.
if ! command -v readarray >/dev/null 2>&1; then
  readarray() { mapfile "$@"; }
fi

# Return the container engine binary ("podman" or "docker") matching the compose provider
get_compose_engine() {
  local CMD
  CMD="$(__compose_cmd)" || return 127
  case "$CMD" in
    "podman compose"|podman-compose) echo "sudo podman";;
    "docker compose"|docker-compose) echo "docker";;
    *)
      # Best-effort default
      echo "sudo podman"
      ;;
  esac
}

# Run an engine command with nice diagnostics
# --- engine_exec: trace to STDERR, emit only command STDOUT to caller ---

# --- External networks create-only helper (called by start_* funcs) ---
ensure_external_networks_exist() {
  # Ensure external networks referenced by compose exist.
  # For now we only create 'osss-net' if missing (create-only; no deletes).
  if ! podman network exists osss-net 2>/dev/null; then
    echo "➕ Creating external network: osss-net"
    sudo podman network create osss-net >/dev/null || echo "⚠️  Could not create osss-net (continuing)"
  fi
}



# --- Podman preflight (idempotent & errexit-safe) ---
podman_ready_once() {
  echo "### Running podman_ready_once (enter)"
  # short-circuit if already done
  if [[ "${__OSSS_PODMAN_READY:-}" == "1" ]]; then
    echo "### Running podman_ready_once (skip)"
    return 0
  fi

  # Temporarily relax errexit for probes; restore it on exit
  local _had_errexit=0
  case $- in *e*) _had_errexit=1 ;; esac
  set +e

  # If podman is not on PATH, there is nothing to prep
  if ! command -v podman >/dev/null 2>&1; then
    # restore errexit and mark ready
    [[ $_had_errexit -eq 1 ]] && set -e
    __OSSS_PODMAN_READY=1; export __OSSS_PODMAN_READY
    echo "### Running podman_ready_once (no podman on PATH; done)"
    return 0
  fi

  if [[ "$(uname -s)" == "Darwin" ]]; then
    local NAME="${PODMAN_MACHINE_NAME:-${PODMAN_MACHINE:-default}}"
    # Don't let inspect failures abort
    local state
    state="$(podman machine inspect "$NAME" --format '{{.State}}' 2>/dev/null || echo "")"
    if [[ "$state" != "running" ]]; then
      # Best-effort init/start; all errors swallowed
      podman machine inspect "$NAME" >/dev/null 2>&1 \
        || podman machine init --rootful "$NAME" >/dev/null 2>&1 || true
      podman machine start "$NAME" >/dev/null 2>&1 || true
    fi
    # Probe info but never fail the script
    podman info >/dev/null 2>&1 || true
  fi

  # Restore errexit exactly as it was
  [[ $_had_errexit -eq 1 ]] && set -e

  __OSSS_PODMAN_READY=1; export __OSSS_PODMAN_READY
  echo "### Running podman_ready_once (ok)"
  return 0
}


podman_ready_once


# -------- dotenv loader --------
load_dotenv() {
  local candidate="${1:-}"
  [[ -z "$candidate" ]] && return 0
  [[ -f "$candidate" ]] || return 0
  echo "🔧 Loading environment from: $candidate"
  # shellcheck disable=SC1090
  set -a; source "$candidate"; set +a
}

# Early dotenv load
if [[ -n "${ENV_FILE:-}" ]]; then
  load_dotenv "$ENV_FILE"
else
  load_dotenv "./.env"
fi

# -------- config / flags --------
PROJECT_DEFAULT="${COMPOSE_PROJECT_NAME:-osss}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
PROFILE="${PROFILE:-seed}"
DEFAULT_TAIL="200"
FORCE_VOLUME_REMOVE=1

usage() {
  cat <<EOF
Usage: $0 [-p PROJECT] [-f docker-compose.yml] [-r PROFILE]

Options:
  -p PROJECT      Compose project name (default: ${PROJECT_DEFAULT})
  -f FILE         Compose file path (default: ${COMPOSE_FILE})
  -r PROFILE      Compose profile to target (default: ${PROFILE})
Environment:
  ENV_FILE             Path to a .env file to load first (overrides ./\.env)
  OSSS_SKIP_VENV_CHECK Set to 1 to skip the Python venv check
EOF
  exit 0
}

while getopts ":p:f:r:h" opt; do
  case "$opt" in
    p) PROJECT_DEFAULT="$OPTARG" ;;
    f) COMPOSE_FILE="$OPTARG"   ;;
    r) PROFILE="$OPTARG"        ;;
    h) usage                    ;;
    \?) echo "Unknown option: -$OPTARG" >&2; usage ;;
  esac
done

# Late dotenv load (sibling .env next to compose file wins)
compose_dir="$(dirname -- "$COMPOSE_FILE")"
load_dotenv "${compose_dir%/}/.env"

export COMPOSE_PROJECT_NAME="${PROJECT_DEFAULT}"

# -------- ensure /etc/hosts has keycloak.local --------
ensure_hosts_keycloak() {
  local entry="127.0.0.1 keycloak.local"
  if ! grep -Eq '(^|\s)keycloak\.local(\s|$)' /etc/hosts; then
    echo "➕ Adding 'keycloak.local' → 127.0.0.1 to /etc/hosts (sudo may prompt)…"
    echo "$entry" | sudo tee -a /etc/hosts >/dev/null
  fi
}

build_trino_truststore() {
  echo "🛠️  Building Trino PKCS12 truststore (CA-based)…"

  # --- Config/paths ---
  local OUT_DIR="./config_files/trino/opt"
  local TRUSTSTORE_P12="${OUT_DIR}/osss-truststore.p12"
  local STOREPASS="changeit"

  # Your Keycloak CA (from create_keycloak_cert)
  local CA_CRT="./config_files/keycloak/secrets/ca/ca.crt"
  local CA_ALIAS="osss-dev-ca"

  # --- Preflight ---
  if ! command -v keytool >/dev/null 2>&1; then
    echo "❌ keytool not found."
    echo "   macOS: brew install --cask temurin || brew install openjdk"
    echo "   Linux: apt-get install -y openjdk-17-jre-headless (or similar)"
    return 1
  fi
  echo "✅ keytool: $(command -v keytool)"

  mkdir -p "${OUT_DIR}"

  if [ ! -f "${CA_CRT}" ]; then
    echo "❌ Missing CA certificate at ${CA_CRT}"
    echo "   Run your create_keycloak_cert step first."
    return 1
  fi

  # --- Build CA-only PKCS12 truststore (idempotent) ---
  echo "→ Creating PKCS12 truststore at ${TRUSTSTORE_P12} with alias '${CA_ALIAS}'"
  rm -f "${TRUSTSTORE_P12}"

  if ! keytool -importcert \
        -alias "${CA_ALIAS}" \
        -file "${CA_CRT}" \
        -keystore "${TRUSTSTORE_P12}" \
        -storetype PKCS12 \
        -storepass "${STOREPASS}" -noprompt; then
    echo "❌ Failed to create ${TRUSTSTORE_P12}"
    return 1
  fi

  # --- Sanity check ---
  echo "→ Sanity check: listing truststore entries"
  if ! keytool -list -v \
        -keystore "${TRUSTSTORE_P12}" \
        -storetype PKCS12 -storepass "${STOREPASS}"; then
    echo "❌ keytool -list failed on ${TRUSTSTORE_P12}"
    return 1
  fi

  echo "🎉 Truststore ready: ${TRUSTSTORE_P12}"
  echo "   Mount in docker-compose as read-only:"
  echo "     - ./config_files/trino/opt/osss-truststore.p12:/opt/trust/osss-truststore.p12:ro"
  echo "   And set JAVA_TOOL_OPTIONS:"
  echo "     -Djavax.net.ssl.trustStore=/opt/trust/osss-truststore.p12"
  echo "     -Djavax.net.ssl.trustStorePassword=changeit"
  echo "     -Djavax.net.ssl.trustStoreType=PKCS12"
}



# -------- Python venv (optional) --------
ensure_python_cmd() {
  command -v python3 >/dev/null 2>&1 && { echo python3; return; }
  command -v python  >/dev/null 2>&1 && { echo python;  return; }
  echo "❌ Python 3 not found." >&2; exit 1
}

ensure_node_installed() {
  if ! command -v node >/dev/null 2>&1; then
    echo "⚙️  Node.js not found. Installing Node.js..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
      if command -v brew >/dev/null 2>&1; then
        brew install node
      else
        echo "❌ Homebrew not found. Please install Homebrew first: https://brew.sh/"
        exit 1
      fi
    elif [[ -f /etc/debian_version ]]; then
      sudo apt update && sudo apt install -y nodejs npm
    elif [[ -f /etc/redhat-release ]]; then
      sudo dnf install -y nodejs npm
    else
      echo "⚠️  Unsupported OS. Please install Node.js manually: https://nodejs.org/"
      exit 1
    fi
  else
    echo "✅ Node.js is already installed: $(node -v)"
  fi
}



in_venv() { [[ -n "${VIRTUAL_ENV:-}" ]]; }

find_upwards() {
  local target="$1" dir="${2:-$PWD}"
  while :; do
    [[ -e "$dir/$target" ]] && { echo "$dir/$target"; return 0; }
    [[ "$dir" == "/" ]] && break
    dir="$(dirname "$dir")"
  done
  return 1
}

install_from_pyproject() {
  local proj_root="$1" py="$2"
  echo "📦 Installing project dependencies from pyproject.toml in: $proj_root"
  ( cd "$proj_root"
    "$py" -m pip install --upgrade pip setuptools wheel
    "$py" -m pip install .
  )
}

# ---- entrypoint (keep this near the end of the file) ----

# 1) One-time virtualenv bootstrap that re-execs the script once
ensure_python_venv() {
  # Already bootstrapped? do nothing.
  if [[ "${OSSS_VENV_BOOTSTRAPPED:-}" == "1" ]]; then
    return 0
  fi

  # Detect venv; if missing, create it and re-exec this script once
  if [[ -z "${VIRTUAL_ENV:-}" && ! -d ".venv" ]]; then
    echo "⚠️  Not running inside a Python virtual environment."
    read -r -p "Create and use '$(pwd)/.venv' and install packages from pyproject.toml? [Y/n] " ans
    ans=${ans:-Y}
    if [[ "$ans" =~ ^[Yy]$ ]]; then
      python3 -m venv .venv
      . .venv/bin/activate
      pip install -U pip setuptools wheel
      # If you have a pyproject.toml in repo:
      pip install .
      # IMPORTANT: mark as bootstrapped and re-exec so the rest of the script runs inside the venv
      export OSSS_VENV_BOOTSTRAPPED=1
      exec "$0" "$@"
    fi
  fi
}

# 2) Always run bootstrap (it’s a no-op after first run)
ensure_python_venv "$@"


# Parse docker-compose.yml and list services that include a given profile, without needing compose on the host.
# Usage: services_for_profile_from_yaml "elastic"


# -------- Podman compose selection (canonical) --------
compose_cmd() {
  if [[ "$(uname -s)" == "Darwin" ]]; then
    local name="${PODMAN_MACHINE_NAME:-default}"
    local active=""
    active="$(podman machine active 2>/dev/null || true)"

    if [[ -z "$active" ]]; then
      if ! podman machine list >/dev/null 2>&1; then
        echo "⚠️  'podman machine list' failed; is Podman installed?" >&2
        return 1
      fi
      if ! podman machine list | awk 'NR>1{print $1}' | sed "s/\*$//" | grep -qx "$name"; then
        echo "⚠️  No Podman machine named '\$name' found. Create it with:" >&2
        echo "    podman machine init --rootful && podman machine start" >&2
        return 1
      fi
    fi

    # Force provider + scrub Docker creds INSIDE the VM:
    #   - CONTAINERS_COMPOSE_PROVIDER=podman-compose
    #   - unset DOCKER_CONFIG/DOCKER_AUTH_CONFIG
    echo "podman machine ssh $name -- env -u DOCKER_CONFIG -u DOCKER_AUTH_CONFIG CONTAINERS_COMPOSE_PROVIDER=podman-compose sudo podman compose"
    return 0
  fi

  echo "podman compose"
  return 0
}

__compose_cmd() { compose_cmd; }


ensure_compose_file() {
  [[ -f "$COMPOSE_FILE" ]] || { echo "❌ Compose file not found: $COMPOSE_FILE" >&2; exit 1; }
}


echo "### Running podman_ready_once"
podman_ready_once

# SAFE: catch compose_cmd failures explicitly under `set -e`
if ! COMPOSE="$(compose_cmd)"; then
  echo "❌ compose_cmd failed. On macOS ensure a VM named '${PODMAN_MACHINE_NAME:-${PODMAN_MACHINE:-default}}' exists and is running:"
  echo "   podman machine list"
  echo "   podman machine init --rootful && podman machine start"
  exit 1
fi
export COMPOSE

echo "### Running ensure_compose_file"
ensure_compose_file


# Convenience wrappers
run() { echo "+ $*"; "$@"; }
c() { $COMPOSE -f "$COMPOSE_FILE" --profile "$PROFILE" "$@"; }

# -------- Service discovery --------

# Returns unique profile names for the active compose file, even under podman compose
discover_profiles() {
  # Logs → stderr, data (profile names one per line) → stdout
  echo "[discover_profiles] Invoked" >&2

  local CMD; CMD="$(__compose_cmd)" || { echo "[discover_profiles] ❌ no compose cmd" >&2; return 0; }

  # COMPOSE_FILE may be colon-separated
  local CF="${COMPOSE_FILE:-docker-compose.yml}"
  IFS=':' read -r -a FILES <<<"$CF"
  ((${#FILES[@]})) || FILES=("docker-compose.yml")

  echo "[discover_profiles] Using command: $CMD" >&2
  echo "[discover_profiles] Compose files:" >&2
  local f
  for f in "${FILES[@]}"; do
    echo "  • $f $([ -f "$f" ] && echo '(exists)' || echo '(MISSING)')" >&2
  done

  # -------- 1) Native path: `compose config --profiles` (union across files) ----
  echo "[discover_profiles] Probing native '--profiles'…" >&2
  local argv=(); for f in "${FILES[@]}"; do argv+=(-f "$f"); done
  local native_out="" native_rc=1
  if $CMD "${argv[@]}" config --profiles >/dev/null 2>&1; then
    native_out="$($CMD "${argv[@]}" config --profiles 2>/dev/null | awk 'NF' | sort -u)"
    native_rc=$?
    echo "[discover_profiles] native rc=${native_rc} count=$(printf '%s\n' "$native_out" | awk 'NF' | wc -l | tr -d ' ')" >&2
  else
    echo "[discover_profiles] '--profiles' unsupported by this engine" >&2
  fi

  # -------- 2) YAML fallback (Python + PyYAML first; then AWK) ------------------
  echo "[discover_profiles] Fallback: parsing source YAML…" >&2
  local parsed_all="" py_rc=99

  if command -v python3 >/dev/null 2>&1; then
    # Try Python + PyYAML (most reliable for all YAML constructs)
    parsed_all="$(
      python3 - "$@" <<'PY' "${FILES[@]}"
import sys
files = sys.argv[1:]
try:
    import yaml  # PyYAML
except Exception:
    sys.exit(90)  # signal "PyYAML missing"

profiles = set()
for path in files:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
    except Exception:
        continue
    services = doc.get("services") or {}
    if isinstance(services, dict):
        for name, svc in services.items():
            if not isinstance(svc, dict):
                continue
            p = svc.get("profiles")
            if isinstance(p, str):
                profiles.add(p.strip())
            elif isinstance(p, (list, tuple)):
                for v in p:
                    if isinstance(v, str) and v.strip():
                        profiles.add(v.strip())

for p in sorted(profiles):
    print(p)
PY
    )"
    py_rc=$?
    if (( py_rc == 0 )); then
      echo "[discover_profiles] PyYAML parse count=$(printf '%s\n' "$parsed_all" | awk 'NF' | wc -l | tr -d ' ')" >&2
    elif (( py_rc == 90 )); then
      echo "[discover_profiles] python3 present but PyYAML missing; using AWK fallback" >&2
      parsed_all=""
    else
      echo "[discover_profiles] python3 parse failed rc=$py_rc; using AWK fallback" >&2
      parsed_all=""
    fi
  else
    echo "[discover_profiles] python3 not found; using AWK fallback" >&2
  fi

  # AWK fallback if Python path didn’t produce results
  if [[ -z "$parsed_all" ]]; then
    local parsed_this=""
    for f in "${FILES[@]}"; do
      if [[ ! -f "$f" ]]; then
        echo "[discover_profiles]   skip (missing): $f" >&2
        continue
      fi
      parsed_this="$(
        awk '
          function indent(s){match(s,/^[ \t]*/); return RLENGTH}
          BEGIN{ in_prof=0; prof_i=-1 }
          {
            li = indent($0)
            # Any occurrence of "profiles:" (we will validate by indentation for list items)
            if ($0 ~ /^[ \t]*profiles:[ \t]*/) {
              in_prof = 1
              prof_i  = li
              # Grab anything inline: e.g., "profiles: elastic" OR "profiles: [a, b]"
              rest=$0
              sub(/^[ \t]*profiles:[ \t]*/, "", rest)
              # If flow list: [a, b]
              if (rest ~ /\[[^]]*\]/) {
                gsub(/\[/, "", rest); gsub(/\]/, "", rest)
                n=split(rest, arr, /[ \t,]+/)
                for (i=1; i<=n; i++) if (arr[i]!="") print arr[i]
                in_prof=0
                next
              }
              # If scalar: "profiles: elastic"
              if (rest ~ /[^ \t]/) {
                gsub(/^[ \t]+|[ \t]+$/, "", rest)
                if (rest!="") print rest
                in_prof=0
                next
              }
              # Otherwise expect block list items on following lines
              next
            }
            if (in_prof) {
              # list item under profiles: (must be further indented)
              if ($0 ~ /^[ \t]*-[ \t]*[A-Za-z0-9._-]+[ \t]*$/ && li > prof_i) {
                p=$0; sub(/^[ \t]*-[ \t]*/, "", p); sub(/[ \t]*$/, "", p); print p
                next
              }
              # End of profiles block: dedent to <= prof_i or new key at same/lower indent
              if (li <= prof_i || $0 ~ /^[ \t]*[A-Za-z0-9._-]+:[ \t]*$/) {
                in_prof=0
              }
            }
          }
        ' "$f"
      )"
      if [[ -n "$parsed_this" ]]; then
        while IFS= read -r line; do
          [[ -z "$line" ]] && continue
          echo "[discover_profiles] parsed ($f) → $line" >&2
        done <<<"$parsed_this"
        parsed_all+=$'\n'"$parsed_this"
      else
        echo "[discover_profiles] parsed ($f) → <none>" >&2
      fi
    done
  fi

  # -------- 3) Union results (native + parsed) ----------------------------------
  local combined
  combined="$( (printf '%s\n' "$native_out"; printf '%s\n' "$parsed_all") | awk 'NF' | sort -u )"
  echo "[discover_profiles] combined count=$(printf '%s\n' "$combined" | awk 'NF' | wc -l | tr -d ' ')" >&2

  if [[ -n "$combined" ]]; then
    printf '%s\n' "$combined"
  else
    echo "[discover_profiles] ❌ No profiles discovered." >&2
    echo "  Hints:" >&2
    echo "   • Ensure each service defines a 'profiles:' list (block, flow [a,b], or scalar)." >&2
    echo "   • Verify COMPOSE_FILE points to the right file(s); multiple files use ':' separators." >&2
    echo "   • Try: grep -nE \"^[[:space:]]*profiles:[[:space:]]*(\\[.*\\]|[[:alnum:]_.-]+)?$\" ${FILES[*]}" >&2
    echo "   • Try: $CMD ${argv[*]} config --services" >&2
  fi
}



# get compose project name the same way compose will (respect env/flags)
__compose_project_name() {
  # Respect COMPOSE_PROJECT_NAME if set; otherwise let compose compute.
  if [ -n "${COMPOSE_PROJECT_NAME:-}" ]; then
    echo "$COMPOSE_PROJECT_NAME"
  else
    # Ask the compose CLI directly (works with both podman-compose and docker compose)
    # Falls back to directory name if config doesn’t expose name.
    local CMD; CMD="$(__compose_cmd)" || return $?
    # docker compose: `config --services` doesn’t show project; but `config --hash` not universal.
    # Use ps to read labels if running; else derive from current dir.
    local pn
    pn="$($CMD config 2>/dev/null | awk -F: '/^name:/{gsub(/[[:space:]]/,"",$2);print $2; exit}')" || true
    if [ -n "$pn" ]; then echo "$pn"; else basename "$PWD"; fi
  fi
}

compose_down_profile() {
  local prof="$1"
  # Try a native compose down first (best at cleaning pods, networks, orphans)
  # Fall back silently if the CLI doesn’t support flags.
  set +e
  compose_stop_rm_profile "$prof" 2>/dev/null
  rc=$?
  set -e
  return $rc
}

# list profiles (quote-safe)
# List unique compose profiles (multi-file aware, verbose when COMPOSE_PROFILES_VERBOSE/VERBOSE/DEBUG set)

# Back-compat shim for older callsites
__compose_services_for_profile() { compose_services_for_profile "$@"; }

# services for a given profile (quote-safe)
# Return services in a profile that have a 'build:' section
__compose_services_with_build_for_profile() {
  local prof="$1"
  local cfg allowed=()

  # Services that belong to this profile (from the compose file itself)
  mapfile -t allowed < <(__compose_services_for_profile "$prof")

  # Try a profile-scoped config (compose v2); fall back to full config
  if ! cfg="$($COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config 2>/dev/null)"; then
    cfg="$($COMPOSE -f "$COMPOSE_FILE" config 2>/dev/null || true)"
  fi

  # Parse config YAML for services that contain a top-level 'build:' key
  mapfile -t all_with_build < <(awk '
    BEGIN{in_services=0; svc=""; has_build=0}
    /^[[:space:]]*services[[:space:]]*:/ {in_services=1; next}
    in_services {
      # leaving services block
      if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) {
        if (svc!="" && has_build) print svc
        in_services=0; svc=""; has_build=0; next
      }
      # service header
      if ($0 ~ /^[[:space:]]{2}[A-Za-z0-9._-]+:[[:space:]]*$/) {
        if (svc!="" && has_build) print svc
        line=$0; sub(/^[[:space:]]+/,"",line); sub(/:.*/,"",line)
        svc=line; has_build=0; next
      }
      # build key at indent 4
      if (svc!="" && $0 ~ /^[[:space:]]{4}build[[:space:]]*:/) { has_build=1 }
    }
    END{ if (svc!="" && has_build) print svc }
  ' <<<"$cfg")

  # If we know which services are in the profile, filter against them
  if ((${#allowed[@]})); then
    for s in "${all_with_build[@]}"; do
      for a in "${allowed[@]}"; do
        [[ "$s" == "$a" ]] && echo "$s" && break
      done
    done | awk 'NF && !seen[$0]++'
  else
    printf "%s\n" "${all_with_build[@]}" | awk 'NF && !seen[$0]++'
  fi
}

# Prompt to rebuild images for services with build: in a profile
maybe_build_profile() {
  local prof="$1"
  mapfile -t build_svcs < <(__compose_services_with_build_for_profile "$prof")
  ((${#build_svcs[@]})) || return 0

  echo "🧱 The following services in profile '${prof}' have a build section:"
  echo "    ${build_svcs[*]}"

  local ans; read -rp "Rebuild these images before starting '${prof}'? [y/N] " ans || true
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    local nocache=""
    read -rp "Use --no-cache? [y/N] " ans || true
    [[ "$ans" =~ ^[Yy]$ ]] && nocache="--no-cache"

    echo "+ $COMPOSE -f \"$COMPOSE_FILE\" --profile \"$prof\" build $nocache ${build_svcs[*]}"
    env -u DOCKER_CONFIG -u DOCKER_AUTH_CONFIG -u DOCKER_HOST -u CONTAINER_HOST \
    $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" build $nocache "${build_svcs[@]}"

  fi
}


compose_profiles() {
  # Emits unique profile names found in services.*.profiles (inline list or multiline).
  local file="${COMPOSE_FILE:-docker-compose.yml}"
  local v=0
  [[ -n "$COMPOSE_PROFILES_VERBOSE" || -n "$VERBOSE" || -n "$DEBUG" ]] && v=1

  awk -v verbose="$v" -v FILE="$file" '
    function dbg(msg){ if (verbose) print msg > "/dev/stderr" }

    BEGIN{
      in_services=0; svc=""; in_profiles=0
      dbg("» scanning compose file: " FILE)
    }

    /^[[:space:]]*services[[:space:]]*:/ {
      in_services=1
      dbg(sprintf("[L%05d] enter services", NR))
      next
    }

    in_services {
      # top-level key ends services
      if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) {
        dbg(sprintf("[L%05d] leave services", NR))
        in_services=0; next
      }

      # service header (two spaces then "name:")
      if ($0 ~ /^[[:space:]][[:space:]][A-Za-z0-9._-]+:[[:space:]]*$/) {
        svc=$0; sub(/^[[:space:]]+/, "", svc); sub(/:.*/, "", svc); in_profiles=0
        dbg(sprintf("[L%05d] service: %s", NR, svc))
        next
      }

      # inline profiles: "    profiles: [a,b,c]"
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*\[/) {
        s=$0; sub(/^[^[]*\[/,"",s); sub(/\].*$/,"",s)
        raw=s
        gsub(/[[:space:]]/,"",s)
        dbg(sprintf("[L%05d] %s: inline profiles raw: [%s]", NR, svc, raw))
        n=split(s, arr, ",")
        for(i=1;i<=n;i++) if (arr[i]!="") { seen[arr[i]]=1; dbg("           -> +" arr[i]) }
        next
      }

      # multiline profiles: start
      if (svc && $0 ~ /^[[:space:]]{4}profiles:[[:space:]]*$/) {
        in_profiles=1
        dbg(sprintf("[L%05d] %s: profiles list start", NR, svc))
        next
      }

      # multiline items: "      - prof"
      if (in_profiles && $0 ~ /^[[:space:]]{6}-[[:space:]]*[A-Za-z0-9._-]+/) {
        p=$0; sub(/^[^ -]*-/,"",p); gsub(/^[[:space:]]+|[[:space:]]+$/,"",p)
        if (p!="") { seen[p]=1; dbg("           -> +" p) }
        next
      }

      # any new key at indent 4 ends profiles block
      if (in_profiles && $0 ~ /^[[:space:]]{4}[A-Za-z0-9._-]+:/) {
        in_profiles=0
        dbg(sprintf("[L%05d] %s: profiles list end", NR, svc))
      }
    }

    END{
      if (verbose) {
        dbg("== collected profiles ==")
        for (k in seen) dbg("  * " k)
        dbg("== end ==")
      }
      for (k in seen) print k
    }
  ' "$file" | sort -u
}

compose_services_base() {
  local out
  if out="$($COMPOSE -f "$COMPOSE_FILE" config --services 2>/dev/null)" && [[ -n "$out" ]]; then
    printf '%s\n' "$out" | sed '/^\s*$/d'
  else
    awk '
      /^services:[[:space:]]*$/ { in_services=1; next }
      in_services && /^[^[:space:]]/ { in_services=0 }
      in_services && /^[[:space:]]{2}[A-Za-z0-9_.-]+:[[:space:]]*$/ {
        s=$0; sub(/^[[:space:]]+/, "", s); sub(/:.*/, "", s); print s
      }
    ' "$COMPOSE_FILE" | sed '/^\s*$/d' | sort -u
  fi
}

# Return services for a profile, clean (one per line, no logs).
compose_services_for_profile() {
  local CMD="$1" FILE="$2" PROFILE="$3"
  "$CMD" -f "$FILE" --profile "$PROFILE" config --services 2>/dev/null | awk 'NF'
}


compose_services_all() {
  { compose_services_base; while read -r p; do [[ -n "$p" ]] && compose_services_for_profile "$p"; done < <(compose_profiles); } \
  | awk 'NF && !seen[$0]++' | sort -u
}

# -------- Host info --------



# -------- logs helpers --------
DEFAULT_TAIL_CONF="${XDG_CONFIG_HOME:-$HOME/.config}/osss-compose-repair.conf"
load_config(){ [[ -f "$DEFAULT_TAIL_CONF" ]] && source "$DEFAULT_TAIL_CONF"; : "${DEFAULT_TAIL:=${DEFAULT_TAIL:-200}}"; }
save_config(){ mkdir -p "$(dirname "$DEFAULT_TAIL_CONF")"; printf "DEFAULT_TAIL=%s\n" "$DEFAULT_TAIL" > "$DEFAULT_TAIL_CONF"; echo "Saved -> $DEFAULT_TAIL_CONF"; }
load_config

last_container_id() {
  local svc="$1" newest="" created_newest="" id created
  mapfile -t ids < <(sudo podman ps -a \
  --filter "label=io.podman.compose.project=${COMPOSE_PROJECT_NAME}" \
  --filter "label=io.podman.compose.service=${svc}" \
  -q 2>/dev/null || true)

  for id in "${ids[@]:-}"; do
    created=$(sudo podman inspect -f '{{.Created}}' "$id" 2>/dev/null || true)
    [[ -z "$created" ]] && continue
    if [[ -z "$created_newest" || "$created" > "$created_newest" ]]; then created_newest="$created"; newest="$id"; fi
  done
  [[ -n "$newest" ]] && echo "$newest"
}

logs_tail_service_any(){
  local svc="$1" lines="${2:-$DEFAULT_TAIL}" rc=0
  [[ "$lines" =~ ^[0-9]+$ ]] || lines="$DEFAULT_TAIL"
  echo "📜 Last ${lines} lines for '${svc}':"
  set +e
  $COMPOSE -f "$COMPOSE_FILE" logs --no-color --tail "$lines" "$svc" 2>&1
  rc=$?
  set -e
  if (( rc != 0 )); then
    local cid; cid=$(last_container_id "$svc" || true)
    if [[ -n "${cid:-}" ]]; then
      echo "(compose logs unavailable; showing last container $cid)"
      sudo podman logs --tail "$lines" "$cid" || true
    else
      echo "(no logs found for service '$svc')"
    fi
  fi
}

logs_follow_service_any(){
  local svc="$1" rc=0
  echo "📜 Following logs for '${svc}'. Press Ctrl-C to return."
  trap 'echo; echo "↩ Back to logs menu"; trap - INT; return 0' INT
  set +e
  $COMPOSE -f "$COMPOSE_FILE" logs -f --tail "$DEFAULT_TAIL" "$svc"
  rc=$?
  set -e
  if (( rc != 0 )); then
    local cid; cid=$(last_container_id "$svc" || true)
    if [[ -n "${cid:-}" ]]; then
      echo "(compose stream unavailable; following last container $cid)"
      sudo podman logs -f --tail "$DEFAULT_TAIL" "$cid" || true
    else
      echo "(no container found to follow for service '$svc')"
    fi
  fi
  trap - INT
}

list_services_logs(){ compose_services_all; }

logs_tail_all_any(){
  local n="${1:-$DEFAULT_TAIL}"
  [[ "$n" =~ ^[0-9]+$ ]] || n="$DEFAULT_TAIL"
  echo "📜 Last ${n} lines for ALL services:"
  while read -r svc; do
    [[ -z "$svc" ]] && continue
    echo; echo "===== ${svc} ====="
    logs_tail_service_any "$svc" "$n" || true
  done < <(list_services_logs)
}

set_default_tail(){
  local n; read -rp "Enter default tail size (current ${DEFAULT_TAIL}): " n || return 0
  [[ "$n" =~ ^[0-9]+$ ]] || { echo "Not a number."; return 1; }
  DEFAULT_TAIL="$n"; save_config
}

# --- Return-to-menu prompt ---

prompt_return() {
  # Print a subtle prompt and wait for the user to press Enter
  printf "\n↩ Press Enter to return to the menu..."
  # shellcheck disable=SC2162
  read _
  printf "\n"
}


# Force-recreate all services in a given profile (works with both `sudo podman compose` and `sudo podman-compose`)
up_force_profile() {
  local prof="$1"
  echo "[up_force_profile] Invoked with profile: '$prof'"

  # Prefer compose CLI; fall back to awk parser
  echo "[up_force_profile] Resolving services for profile '$prof'..."
  mapfile -t svcs < <($COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF')
  echo "[up_force_profile] Found ${#svcs[@]} service(s) from compose CLI: ${svcs[*]:-<none>}"

  if ((${#svcs[@]}==0)); then
    echo "[up_force_profile] Falling back to compose_services_for_profile..."
    mapfile -t svcs < <(compose_services_for_profile "$prof" 2>/dev/null || true)
    echo "[up_force_profile] Found ${#svcs[@]} service(s) via fallback: ${svcs[*]:-<none>}"
  fi

  if ((${#svcs[@]}==0)); then
    echo "⚠️  No services declare profile '${prof}' in ${COMPOSE_FILE:-docker-compose.yml}."
    echo "[up_force_profile] Exiting early, nothing to do"
    prompt_return
    return 0
  fi

  echo "🛠️  Forcing recreate of ${#svcs[@]} service(s) in profile '${prof}': ${svcs[*]}"

  # make this block failure-tolerant, then restore -e
  echo "[up_force_profile] Disabling 'set -e' to tolerate failures..."
  set +e

  # Stop via compose first (ok if already stopped)
  echo "[up_force_profile] Stopping services via compose..."
  $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" stop "${svcs[@]}"

  # Hard-stop & remove any existing containers/pods that belong to these services
  for svc in "${svcs[@]}"; do
    echo "[up_force_profile] Checking for existing containers of service '$svc'..."
    ids=$(sudo podman ps -a \
      --filter "label=io.podman.compose.project=${COMPOSE_PROJECT_NAME}" \
      --filter "label=io.podman.compose.service=${svc}" -q 2>/dev/null)

    if [[ -n "$ids" ]]; then
      echo "[up_force_profile] Found containers for '$svc': $ids"
      pods=$(sudo podman inspect -f '{{.PodName}}' $ids 2>/dev/null | awk 'NF && $0!="<no value>" && !seen[$0]++')

      if [[ -n "$pods" ]]; then
        echo "[up_force_profile] Stopping pods: $pods"
        sudo podman pod stop $pods >/dev/null 2>&1
      fi

      echo "[up_force_profile] Removing containers + anon volumes for '$svc'..."
      sudo podman rm -f -v $ids >/dev/null 2>&1

      if [[ -n "$pods" ]]; then
        echo "[up_force_profile] Removing pods: $pods"
        sudo podman pod rm -f $pods >/dev/null 2>&1
      fi
    else
      echo "[up_force_profile] No containers found for service '$svc'"
    fi
  done

  # Bring them back up (ignore “network in use”/pod removal errors, compose will reuse)
  echo "[up_force_profile] Starting services with 'up -d --no-deps --force-recreate'..."
  $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d --no-deps --force-recreate

  echo "[up_force_profile] Restoring 'set -e'"
  set -e

  echo "[up_force_profile] Completed, returning to menu..."
  prompt_return
  return 0
}



start_profile_with_build_prompt() {
  local prof="$1"

  echo "[start_profile_with_build_prompt] Maybe building profile: '$prof'"
  maybe_build_profile "$prof"
  echo "[start_profile_with_build_prompt] Build check complete for profile '$prof'"

  if compose_supports_profile; then
    echo "[start_profile_with_build_prompt] Backend supports profiles"
    echo "[start_profile_with_build_prompt] Running compose up with: $COMPOSE -f \"$COMPOSE_FILE\" --profile \"$prof\" up -d --no-deps"
    run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d --no-deps
    echo "[start_profile_with_build_prompt] Compose up complete (profile mode)"
  else
    echo "[start_profile_with_build_prompt] Backend does NOT support profiles → falling back to manual service resolution"
    mapfile -t svcs < <(compose_services_for_profile "$prof" 2>/dev/null || true)
    echo "[start_profile_with_build_prompt] Resolved ${#svcs[@]} service(s) for profile '$prof': ${svcs[*]:-<none>}"

    if ((${#svcs[@]}==0)); then
      echo "⚠️  No services declare profile '${prof}' in ${COMPOSE_FILE:-docker-compose.yml}."
      echo "[start_profile_with_build_prompt] Exiting early, nothing to start"
      prompt_return
      return 1
    fi

    echo "⚠️  Backend lacks profile support; starting services only: ${svcs[*]}"
    echo "[start_profile_with_build_prompt] Running compose_up_services with: ${svcs[*]}"
    compose_up_services "${svcs[@]}"   # calls: up -d --no-deps <services...>
    echo "[start_profile_with_build_prompt] Compose up complete (manual fallback)"
  fi

  echo "[start_profile_with_build_prompt] Returning to menu..."
  prompt_return
  echo "[start_profile_with_build_prompt] Finished execution"
}


start_profile_services() {
  echo "[start_profile_services] Invoked with profile: '$prof'"

  echo "[start_profile_services] Determining compose command..."
  local CMD; CMD="$(__compose_cmd)" || {
    echo "[start_profile_services] Failed to determine compose command → exiting with error"
    return $?
  }
  echo "[start_profile_services] Using compose command: $CMD"

  echo "[start_profile_services] Resolving services via compose CLI for profile '$prof'..."
  mapfile -t svcs < <($CMD -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF')
  echo "[start_profile_services] Found ${#svcs[@]} service(s) from compose CLI: ${svcs[*]:-<none>}"

  if [ "${#svcs[@]}" -eq 0 ]; then
    echo "[start_profile_services] Falling back to compose_services_for_profile..."
    mapfile -t svcs < <(compose_services_for_profile "$prof" 2>/dev/null || true)
    echo "[start_profile_services] Found ${#svcs[@]} service(s) via fallback: ${svcs[*]:-<none>}"
  fi

  if ((${#svcs[@]}==0)); then
    echo "(no services discovered in profile '${prof}')"
    echo "[start_profile_services] Nothing to start, returning to menu"
    prompt_return
    return 1
  fi

  echo "▶️  Starting ${#svcs[@]} service(s) in profile '${prof}': ${svcs[*]}"
  echo "[start_profile_services] Running: $COMPOSE -f \"$COMPOSE_FILE\" --profile \"$prof\" up -d"
  run $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d
  echo "[start_profile_services] Compose up complete for profile '$prof'"

  echo "[start_profile_services] Returning to menu..."
  prompt_return
  echo "[start_profile_services] Finished execution"
}

# Override: start_keycloak_services to ensure external networks first
start_keycloak_services() {
  echo "[start_keycloak_services] Invoked"

  echo "[start_keycloak_services] Determining compose command..."
  local CMD; CMD="$(__compose_cmd)" || {
    echo "[start_keycloak_services] Failed to determine compose command → exiting"
    return $?
  }
  echo "[start_keycloak_services] Using compose command: $CMD"

  echo "[start_keycloak_services] Determining project name..."
  local PROJECT; PROJECT="$(__compose_project_name)"
  echo "[start_keycloak_services] Project: $PROJECT"
  echo "[start_keycloak_services] Compose file: ${COMPOSE_FILE:-docker-compose.yml}"

  echo "[start_keycloak_services] Ensuring external networks exist (non-destructive)..."
  echo "[start_keycloak_services] External networks ensured"

  local svcs=()
  if compose_supports_profile; then
    echo "[start_keycloak_services] Backend supports profiles, checking profile 'keycloak'..."
    mapfile -t svcs < <($CMD -f "$COMPOSE_FILE" --profile "keycloak" config --services 2>/dev/null | awk 'NF')
    echo "[start_keycloak_services] Found ${#svcs[@]} service(s) in 'keycloak' profile via compose CLI: ${svcs[*]:-<none>}"

    if [ "${#svcs[@]}" -eq 0 ]; then
      echo "[start_keycloak_services] Falling back to compose_services_for_profile 'keycloak'..."
      mapfile -t svcs < <(compose_services_for_profile "keycloak" 2>/dev/null || true)
      echo "[start_keycloak_services] Found ${#svcs[@]} service(s) via fallback: ${svcs[*]:-<none>}"
    fi
  else
    echo "[start_keycloak_services] Backend does NOT support profiles → skipping profile resolution"
  fi

  if ((${#svcs[@]})); then
    echo "[start_keycloak_services] Profile 'keycloak' detected with ${#svcs[@]} service(s): ${svcs[*]}"
    echo "[start_keycloak_services] Maybe building profile 'keycloak'..."
    maybe_build_profile keycloak
    echo "[start_keycloak_services] Build check complete"

    echo "[start_keycloak_services] Running: $CMD --profile keycloak up -d --no-deps ${svcs[*]}"
    $CMD --profile keycloak up -d --no-deps "${svcs[@]}"
    echo "[start_keycloak_services] Compose up complete for profile 'keycloak'"
    echo "[start_keycloak_services] Returning to menu..."
    prompt_return
    echo "[start_keycloak_services] Finished execution"
    return 0
  fi

  echo "[start_keycloak_services] No 'keycloak' profile found, falling back to direct service detection..."
  mapfile -t ALL_SERVS < <(compose_list_services)
  echo "[start_keycloak_services] All available services: ${ALL_SERVS[*]}"

  want=(keycloak kc_postgres)
  chosen=()
  for w in "${want[@]}"; do
    for s in "${ALL_SERVS[@]}"; do
      if [[ "$s" == "$w" ]]; then
        echo "[start_keycloak_services] Matched service '$w'"
        chosen+=("$w")
        break
      fi
    done
  done

  if ((${#chosen[@]}==0)); then
    echo "⚠️  Neither a 'keycloak' profile nor 'keycloak' service was detected."
    echo "   Services available: ${ALL_SERVS[*]}"
    echo "[start_keycloak_services] Exiting, nothing to start"
    prompt_return
    return 1
  fi

  echo "[start_keycloak_services] Starting services directly (no profile): ${chosen[*]}"
  compose_up_services "${chosen[@]}"
  echo "[start_keycloak_services] Compose up complete (direct services)"
  echo "[start_keycloak_services] Returning to menu..."
  prompt_return
  echo "[start_keycloak_services] Finished execution"
}

# --- Run a compose command *inside* the Podman VM (macOS) ---
# Usage: vm_compose_in_dir "$PWD" -f docker-compose.yml up -d svc1 svc2 ...


# Return list of services in a profile (1 per line)
__services_for_profile() {
  local prof="$1"
  $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF'
}

__rm_existing_for_profile() {
  local prof="$1"
  local project; project="$(__compose_project_name)"
  mapfile -t svcs < <(__services_for_profile "$prof")
  ((${#svcs[@]})) || return 0

  # Use VM if present to avoid host/VM storage path issues
  if pm_ssh -h >/dev/null 2>&1; then
    for s in "${svcs[@]}"; do
      local cmd="sudo podman ps -a \
        --filter 'label=io.podman.compose.project=${project}' \
        --filter 'label=io.podman.compose.service=${s}' -q \
        | xargs -r podman rm -f -v || true
      if [ \$(sudo podman ps -a \
        --filter 'label=com.docker.compose.project=${project}' \
        --filter 'label=com.docker.compose.service=${s}' -q | wc -l) -gt 0 ]; then
        sudo podman ps -a \
          --filter 'label=com.docker.compose.project=${project}' \
          --filter 'label=com.docker.compose.service=${s}' -q \
          | xargs -r sudo podman rm -f -v || true
      fi"
      echo "  - VM cleanup for service: $s"
      pm_ssh ssh -- bash -lc "$cmd"
    done
  else
    # Host fallback
    for s in "${svcs[@]}"; do
      mapfile -t ids < <(sudo podman ps -a \
        --filter "label=io.podman.compose.project=${project}" \
        --filter "label=io.podman.compose.service=${s}" -q 2>/dev/null)
      ((${#ids[@]}==0)) && mapfile -t ids < <(sudo podman ps -a \
        --filter "label=com.docker.compose.project=${project}" \
        --filter "label=com.docker.compose.service=${s}" -q 2>/dev/null)
      ((${#ids[@]})) || continue
      sudo podman rm -f "${ids[@]}" >/dev/null 2>&1 || true
    done
  fi
}


# Detect whether the Podman VM has the overlay-containers path (needed by filebeat)
__podman_vm_has_overlay() {
  if command -v sudo podman >/dev/null 2>&1 && pm_ssh -h >/dev/null 2>&1; then
    pm_ssh ssh -- test -d /var/lib/containers/storage/overlay-containers
    return $?
  fi
  return 1
}

# Recreate all containers in a given profile (stop → rm → maybe build → up)
recreate_profile() {
  local prof="${1:-elastic}"
  echo "🔄 Recreating all containers for profile: ${prof}"

  echo "# 0) Ensure external networks"
  prompt_return

  echo "# 1) Down (ignore noisy 'no such container') --profile ${prof}"
  prompt_return
  compose_stop_rm_profile "$prof"

  echo "# 2) Extra cleanup of anything lingering with compose labels (profile-scoped)"
  __rm_existing_for_profile "$prof"

  echo "# 3) Rebuild images if needed"
  maybe_build_profile "$prof"

  echo "# 4) Decide service set (optionally skip filebeat if VM path missing)"
  local -a SVCS=()
  mapfile -t SVCS < <($COMPOSE -f "$COMPOSE_FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF')

  # Drop filebeat when overlay path isn’t visible in the Podman VM
  if [[ " ${SVCS[*]} " == *" filebeat "* ]] && ! __podman_vm_has_overlay; then
    echo "⚠️  Skipping 'filebeat' (Podman VM overlay path not visible)."
    SVCS=("${SVCS[@]/filebeat}")
  fi

  echo "# 5) Up"
  if ((${#SVCS[@]})); then
    echo "▶️  Up: ${SVCS[*]}"
    $COMPOSE -f "$COMPOSE_FILE" --profile "$prof" up -d --force-recreate "${SVCS[@]}"
  else
    echo "ℹ️  No services resolved for profile '${prof}'"
  fi
}


# Simple interactive prompt
prompt_recreate_profile() {
  echo
  echo "🔧 Recreate Containers"
  echo "======================"
  echo "This will stop, remove, rebuild, and restart all containers in a profile."
  echo
  echo "Available profiles:"
  compose_profiles
  echo
  read -rp "Enter profile to recreate [elastic]: " prof
  prof="${prof:-elastic}"
  read -rp "Are you sure you want to recreate ALL containers in profile '${prof}'? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { echo "❌ Cancelled."; return 0; }
  recreate_profile "$prof"
}

# --- Helper: resolve the current Podman VM name (Bash 3 & nounset safe) ---
podman_vm_name() {
  # Prefer explicit envs, fall back to active machine, then 'default'
  local name="${PODMAN_MACHINE_NAME:-${PODMAN_MACHINE:-}}"
  if [ -n "$name" ]; then
    printf '%s\n' "$name"
    return 0
  fi
  name="$(podman machine active 2>/dev/null || true)"
  if [ -n "$name" ]; then
    printf '%s\n' "$name"
  else
    printf '%s\n' "default"
  fi
}

# helper: try to remove a list of names if they exist
_remove_containers_if_exist() {
  local ENG="$1"; shift
  local -a NAMES=( "$@" ) FOUND=() n
  for n in "${NAMES[@]}"; do
    $ENG inspect "$n" >/dev/null 2>&1 && FOUND+=( "$n" )
  done
  ((${#FOUND[@]})) || return 0
  $ENG stop -t 10 "${FOUND[@]}" >/dev/null 2>&1 || true
  $ENG rm -f "${FOUND[@]}" >/dev/null 2>&1 || true
  echo "[down_all] Removed by name: ${FOUND[*]}"
}


down_all() {
  echo "[down_all] Invoked"

  # --- Detect compose command / engine ---
  local CMD; CMD="$(__compose_cmd)" || { echo "[down_all] cannot find compose cmd"; return $?; }
  local -a CMD_ARR; IFS=' ' read -r -a CMD_ARR <<< "$CMD"
  local ENGINE="${CMD_ARR[0]}"
  [[ "$ENGINE" == "docker-compose" ]] && ENGINE="docker"
  echo "[down_all] Engine: $ENGINE ; Compose: ${CMD_ARR[*]}"

  # --- Project & compose file ---
  local PROJECT; PROJECT="$(__compose_project_name)"
  local COMPOSE_FILE_LOCAL="${COMPOSE_FILE:-docker-compose.yml}"
  echo "[down_all] Project: $PROJECT ; Compose file: $COMPOSE_FILE_LOCAL"

  # --- Bring project down (all services/profiles) ---
  set +e
  "${CMD_ARR[@]}" -f "$COMPOSE_FILE_LOCAL" -p "$PROJECT" down --remove-orphans -v >/dev/null 2>&1
  set -e
  echo "[down_all] compose down done"

  # --- gather BOTH container_name: and service keys as candidates ---
  local -a CNAMES SVCNAMES
  if command -v yq >/dev/null 2>&1; then
    mapfile -t CNAMES   < <(yq -r '.services | to_entries[] | .value.container_name // empty' "$COMPOSE_FILE_LOCAL")
    mapfile -t SVCNAMES < <(yq -r '.services | keys[]' "$COMPOSE_FILE_LOCAL")
  else
    mapfile -t CNAMES < <(awk '
      /^[[:space:]]{2,}[a-zA-Z0-9_-]+:$/ {svc=$1; sub(":","",svc)}
      /^[[:space:]]+container_name:[[:space:]]/ {print $2}
    ' "$COMPOSE_FILE_LOCAL")
    mapfile -t SVCNAMES < <(awk '
      /^[[:space:]]{2,}[a-zA-Z0-9_-]+:$/ {svc=$1; sub(":","",svc); print svc}
    ' "$COMPOSE_FILE_LOCAL")
  fi

  # -------- Containers: kill by explicit container_name from compose --------
  echo "🧹 Removing containers by container_name from compose…"
  _remove_containers_if_exist "$ENGINE" "${CNAMES[@]}"

  # -------- Containers: kill by service-name & common compose variants --------
  echo "🧹 Removing containers by service name…"
  if ((${#SVCNAMES[@]})); then
    # generate variants: raw, proj_{svc}, proj-{svc}, and each with _1/-1 suffix
    VARS=()
    for s in "${SVCNAMES[@]}"; do
      VARS+=( "$s" "${PROJECT}_${s}" "${PROJECT}-${s}" \
              "${PROJECT}_${s}_1" "${PROJECT}-${s}-1" )
    done
    # de-dup
    mapfile -t VARS < <(printf "%s\n" "${VARS[@]}" | awk '!seen[$0]++')
    _remove_containers_if_exist "$ENGINE" "${VARS[@]}"
  else
    echo "[down_all] No service names found in compose"
  fi

  # --- Also gather top-level named volumes from compose (to remove later) ---
  local -a VOLS_DECLARED
  if command -v yq >/dev/null 2>&1; then
    mapfile -t VOLS_DECLARED < <(yq -r '.volumes | keys[]' "$COMPOSE_FILE_LOCAL" 2>/dev/null)
  else
    mapfile -t VOLS_DECLARED < <(awk '
      /^[[:space:]]*volumes:[[:space:]]*$/ {invol=1; next}
      invol && /^[[:space:]]{2,}[a-zA-Z0-9_.-]+:[[:space:]]*$/ {
        n=$1; sub(":","",n); gsub(/^[[:space:]]+|[[:space:]]+$/,"",n); print n
      }
      invol && /^[[:space:]]*[a-zA-Z_]/ {invol=0}
    ' "$COMPOSE_FILE_LOCAL")
  fi

  # --- Compose label keys (docker vs podman) ---
  local -a COMPOSE_LABEL_KEYS=("com.docker.compose.project" "io.podman.compose.project")

  # -------- Containers: kill by compose label --------
  echo "🧹 Removing leftover containers by label…"
  local cids=""
  for key in "${COMPOSE_LABEL_KEYS[@]}"; do
    cids+=" $($ENGINE ps -a --filter "label=${key}=${PROJECT}" -q 2>/dev/null)"
  done
  # uniq
  cids="$(echo "$cids" | xargs -r printf "%s\n" | sort -u | xargs -r)"
  echo "[down_all] Label-matched containers: ${cids:-<none>}"
  [[ -n "$cids" ]] && $ENGINE rm -f $cids >/dev/null 2>&1 || true

  # -------- Containers: kill by explicit container_name from compose --------
  echo "🧹 Removing containers by container_name from compose…"
  if ((${#CNAMES[@]})); then
    local -a FOUND
    local name
    for name in "${CNAMES[@]}"; do
      if $ENGINE inspect "$name" >/dev/null 2>&1; then
        FOUND+=("$name")
      fi
    done
    ((${#FOUND[@]})) && $ENGINE rm -f "${FOUND[@]}" >/dev/null 2>&1 || true
    echo "[down_all] Removed by name: ${FOUND[*]:-<none>}"
  else
    echo "[down_all] No container_name entries found in compose"
  fi

  # -------- Volumes attached to those containers (collect & remove) --------
  echo "🧹 Removing volumes attached to compose containers…"
  # Rebuild the set of candidate containers (some may still exist)
  local -a TARGETS
  # by label again
  mapfile -t TARGETS < <($ENGINE ps -a --filter "label=${COMPOSE_LABEL_KEYS[0]}=${PROJECT}" -q 2>/dev/null; \
                         $ENGINE ps -a --filter "label=${COMPOSE_LABEL_KEYS[1]}=${PROJECT}" -q 2>/dev/null | sort -u)
  # plus by name
  for name in "${CNAMES[@]}"; do
    if $ENGINE inspect "$name" >/dev/null 2>&1; then
      TARGETS+=("$name")
    fi
  done
  # Collect their mount volumes
  if ((${#TARGETS[@]})); then
    local -a ATTACHED_VOLUMES
    local t v
    for t in "${TARGETS[@]}"; do
      while IFS= read -r v; do
        [[ -n "$v" ]] && ATTACHED_VOLUMES+=("$v")
      done < <($ENGINE inspect -f '{{range .Mounts}}{{.Name}}{{"\n"}}{{end}}' "$t" 2>/dev/null | sed '/^$/d')
    done
    # uniq & remove
    if ((${#ATTACHED_VOLUMES[@]})); then
      mapfile -t ATTACHED_VOLUMES < <(printf "%s\n" "${ATTACHED_VOLUMES[@]}" | sort -u)
      $ENGINE volume rm -f "${ATTACHED_VOLUMES[@]}" >/dev/null 2>&1 || true
      echo "[down_all] Removed attached volumes: ${ATTACHED_VOLUMES[*]}"
    else
      echo "[down_all] No attached volumes found (containers likely gone)"
    fi
  else
    echo "[down_all] No remaining target containers to inspect for volumes"
  fi

  # -------- Remove top-level named volumes declared in compose --------
  echo "🧹 Removing top-level named volumes from compose…"
  if ((${#VOLS_DECLARED[@]})); then
    # Compose usually prefixes volumes with project_, but explicit names may exist.
    local -a CANDIDATES=("${VOLS_DECLARED[@]}")
    # Also try project-prefixed versions
    local vol
    for vol in "${VOLS_DECLARED[@]}"; do
      CANDIDATES+=("${PROJECT}_${vol}")
    done
    # Keep only existing
    local -a EXISTING
    for vol in "${CANDIDATES[@]}"; do
      $ENGINE volume inspect "$vol" >/dev/null 2>&1 && EXISTING+=("$vol")
    done
    ((${#EXISTING[@]})) && $ENGINE volume rm -f "${EXISTING[@]}" >/dev/null 2>&1 || true
    echo "[down_all] Removed declared volumes: ${EXISTING[*]:-<none>}"
  else
    echo "[down_all] No top-level volumes found in compose"
  fi

  # -------- Networks (ignore external osss-net) --------
  echo "🧹 Removing leftover networks…"
  local nids=""
  for key in "${COMPOSE_LABEL_KEYS[@]}"; do
    nids+=" $($ENGINE network ls --filter "label=${key}=${PROJECT}" -q 2>/dev/null)"
  done
  nids="$(echo "$nids" | xargs -r printf "%s\n" | sort -u | xargs -r)"
  [[ -n "$nids" ]] && $ENGINE network rm $nids >/dev/null 2>&1 || true
  # fallback common names (skip external osss-net)
  for net in "${PROJECT}_default"; do
    $ENGINE network inspect "$net" >/dev/null 2>&1 && $ENGINE network rm "$net" >/dev/null 2>&1 || true
  done

  # -------- Prune label-scoped (avoid template errors) --------
  echo "[down_all] Final prune pass…"
  $ENGINE container prune -f >/dev/null 2>&1 || true
  # Podman supports prune filters, but we’ll just do a general prune silently.
  $ENGINE volume prune -f >/dev/null 2>&1 || true
  $ENGINE network prune -f >/dev/null 2>&1 || true

  echo "✅ All compose-related resources removed for project '${PROJECT}'."
  prompt_return
}


start_profile_elastic() {
  echo "[start_profile_elastic] Ensuring hosts entry for keycloak..."




  # Start elastic stack in one shot
  prompt_recreate_profile elastic
  up_profile_with_podman elastic || { echo "❌ compose up failed (elastic)"; prompt_return; return 1; }
  prompt_return
}




start_profile_app()          { start_profile_with_build_prompt app; }
start_profile_web_app()      { start_profile_with_build_prompt web-app; }
start_profile_vault()        { start_profile_with_build_prompt vault; }

start_profile_trino() {
  up_force_profile trino
}

start_profile_airflow()      { start_profile_with_build_prompt airflow; }
start_profile_superset()     { start_profile_with_build_prompt superset; }


# ✅ Start all services for a profile in ONE compose call.
# Falls back to a sequenced bring-up for 'elastic' if the provider throws
# a "depends on container … not found in input list" error.
up_profile_with_podman() {
  podman_require_ready_or_die() { podman_ready_once; }

  set -Eeuo pipefail

  local CMD; CMD="$(__compose_cmd)" || return $?
  local FILE="${COMPOSE_FILE:-docker-compose.yml}"
  local PROFILE="${1:-elastic}"
  local PROJECT; PROJECT="$(__compose_project_name)"

  echo "CMD: ${CMD}"
  echo "FILE: ${FILE}"
  echo "PROFILE: ${PROFILE}"
  echo "PROJECT: ${PROJECT}"
  prompt_return             # defaults to "Press Enter to continue..."

  # Split provider ("podman compose" vs "podman-compose") into argv
  local -a CMDA; IFS=' ' read -r -a CMDA <<<"$CMD"

  # Resolve services that belong to the profile
  local -a SVCS=()
  if "${CMDA[@]}" -f "$FILE" --profile "$PROFILE" config --services >/dev/null 2>&1; then
    mapfile -t SVCS < <("${CMDA[@]}" -f "$FILE" --profile "$PROFILE" config --services 2>/dev/null | awk 'NF')
  else
    mapfile -t SVCS < <(services_for_profile_from_yaml "$PROFILE" 2>/dev/null || true)
  fi
  ((${#SVCS[@]})) || { echo "⚠️  No services for profile '$PROFILE' in $FILE"; return 1; }




  echo "[up_profile_with_podman] Provider: $CMD"
  echo "[up_profile_with_podman] File: $FILE   Profile: $PROFILE"
  echo "[up_profile_with_podman] Services: ${SVCS[*]}"
  echo "[up_profile_with_podman] 🧹 Pre-clean stale containers/pods for this profile…"

  prompt_return

  # Targeted cleanup: remove only containers/pods for these services (by label)
  local s ids pods
  for s in "${SVCS[@]}"; do

    echo "SVCS: ${s}"

    ids="$(sudo podman ps -a --filter "label=io.podman.compose.project=${PROJECT}" \
                      --filter "label=io.podman.compose.service=${s}" -q 2>/dev/null || true)"

    echo "ids: ${ids}"
    prompt_return


    if [[ -n "$ids" ]]; then
      pods="$(sudo podman inspect -f '{{.PodName}}' $ids 2>/dev/null | awk 'NF && $0!="<no value>" && !seen[$0]++' || true)"

      echo "about ready to stop these pods: ${pods}"
      prompt_return

      [[ -n "$pods" ]] && { echo "  - stopping pods: $pods"; sudo podman pod stop $pods >/dev/null 2>&1 || true; }
      echo "  - removing containers: $ids"
      sudo podman rm -f -v $ids >/dev/null 2>&1 || true
      [[ -n "$pods" ]] && { echo "  - removing pods: $pods"; sudo podman pod rm -f $pods >/dev/null 2>&1 || true; }
    fi
  done

  echo "[up_profile_with_podman] 🚀 Single compose call (no explicit services, force-recreate)…"
  set +e
  "${CMDA[@]}" -f "$FILE" --profile "$PROFILE" up -d --force-recreate
  local rc=$?
  set -e
  if (( rc == 0 )); then
    return 0
  fi

  if [[ "$PROFILE" == "elastic" ]]; then
    echo "[up_profile_with_podman] ⚠️ Compose failed; using elastic fallback sequencer…"

    echo "# starting phase 1: core"
    prompt_return             # defaults to "Press Enter to continue..."

    "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps shared-vol-init elasticsearch
    _wait_health "elasticsearch" 180

    echo "# starting phase 2: init + kibana"
    prompt_return             # defaults to "Press Enter to continue..."

    "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps kibana-pass-init
    _wait_exit0 "kibana-pass-init" 180
    "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps kibana

    echo "# starting phase 3: api key init"
    prompt_return             # defaults to "Press Enter to continue..."

    echo "# starting phase 4: filebeat (optional)"
    prompt_return             # defaults to "Press Enter to continue..."

    if "${CMDA[@]}" -f "$FILE" --profile elastic config --services 2>/dev/null | grep -qx 'filebeat-setup'; then
      "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps filebeat-setup
      _wait_exit0 "filebeat-setup" 180
    fi
    if "${CMDA[@]}" -f "$FILE" --profile elastic config --services 2>/dev/null | grep -qx 'filebeat'; then
      "${CMDA[@]}" -f "$FILE" --profile elastic up -d --no-deps filebeat
    fi

    return 0
  fi

  return $rc
}

# Wait until service’s newest container is healthy (or running with no HC)
_wait_health() {
  local svc="$1" timeout="${2:-180}" start now cid state health
  start="$(date +%s)"
  while :; do
    cid="$(last_container_id "$svc" || true)"
    [[ -n "$cid" ]] || sleep 1
    state="$(sudo podman inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || true)"
    health="$(sudo podman inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || true)"
    if { [[ "$health" == "healthy" ]] || { [[ "$health" == "none" ]] && [[ "$state" == "running" ]]; }; }; then
      echo "✅ $svc is ready"
      break
    fi
    now="$(date +%s)"; (( now - start > timeout )) && { echo "⏱️  $svc readiness timed out"; return 1; }
    sleep 2
  done
}



# Wait until an init/one-off container exits with code 0
_wait_exit0() {
  local svc="$1" timeout="${2:-180}" start now cid code
  start="$(date +%s)"
  while :; do
    cid="$(last_container_id "$svc" || true)"
    [[ -n "$cid" ]] || { sleep 1; continue; }
    code="$(sudo podman inspect -f '{{.State.ExitCode}}' "$cid" 2>/dev/null || echo '')"
    if [[ "$code" == "0" ]]; then
      echo "✅ $svc completed successfully"
      break
    fi
    now="$(date +%s)"; (( now - start > timeout )) && { echo "⏱️  $svc completion timed out"; return 1; }
    sleep 2
  done
}


start_profile_openmetadata() {
  echo "▶️  Starting profile 'openmetadata' inside the Podman VM (dependencies honored)…"
  pm_ssh ssh -- bash -lc "
set -Eeuo pipefail

# 👉 Adjust this to your project path inside the Podman VM if needed
cd /Users/rubelw/projects/OSSS

# --- Pick a compose provider in the VM ---
have_podman_compose() { sudo podman compose version >/dev/null 2>&1; }

install_compose_plugin() {
  # Install docker-compose v2 plugin into ~/.docker/cli-plugins/docker-compose (no root needed)
  local ver=\"\${COMPOSE_PLUGIN_VERSION:-v2.29.7}\"
  local arch=\"\$(uname -m)\"
  case \"\$arch\" in
    x86_64|amd64) arch=\"x86_64\" ;;
    aarch64|arm64) arch=\"aarch64\" ;;
    *) echo \"❌ Unsupported arch: \$arch\"; return 1 ;;
  esac
  local url=\"https://github.com/docker/compose/releases/download/\${ver}/docker-compose-linux-\${arch}\"
  local dst=\"\$HOME/.docker/cli-plugins/docker-compose\"
  mkdir -p \"\$(dirname \"\$dst\")\"
  echo \"⬇️  Installing docker-compose plugin \${ver} for \${arch} -> \$dst\"
  curl -fsSL \"\$url\" -o \"\$dst\"
  chmod +x \"\$dst\"
}

install_podman_compose_py() {
  echo \"ℹ️  Installing podman-compose via pip (user)…\"
  if ! python3 -m pip --version >/dev/null 2>&1; then
    echo \"ℹ️  Bootstrapping pip (user)…\"
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    python3 /tmp/get-pip.py --user
  fi
  export PATH=\"\$HOME/.local/bin:\$PATH\"
  python3 -m pip install --user --upgrade podman-compose
}

PROVIDER=\"\"
if have_podman_compose; then
  PROVIDER=\"sudo podman compose\"
else
  if install_compose_plugin && have_podman_compose; then
    PROVIDER=\"sudo podman compose\"
  else
    if command -v podman-compose >/dev/null 2>&1; then
      PROVIDER=\"sudo podman-compose\"
    else
      install_podman_compose_py
      PROVIDER=\"sudo podman-compose\"
    fi
  fi
fi

echo \"ℹ️  Compose provider in VM: \$PROVIDER\"

# --- Phase 1: bring up ONLY MySQL ---
\$PROVIDER -f docker-compose.yml up -d mysql


# --- Phase 2: wait until MySQL is healthy ---
echo \"⏳ waiting for mysql to be healthy…\"
for i in \$(seq 1 240); do
  # get the exact container id
  CID=\$(sudo podman ps -aq --filter name=^mysql\$ | head -n1)
  echo \"\$CID\"

  if [ -z \"\$CID\" ]; then
    echo \"❌ mysql not found\"
    exit 1
  fi

  # read state + health (health can be nil if no healthcheck)
  state=\$(sudo podman inspect -f '{{.State.Status}}' \"\$CID\" 2>/dev/null || echo unknown)
  health=\$(sudo podman inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \"\$CID\" 2>/dev/null || echo unknown)
  echo \"state=\$state health=\$health\"

  if [ \"\$health\" = \"healthy\" ] || { [ \"\$health\" = \"none\" ] && [ \"\$state\" = \"running\" ]; }; then
    echo \"✅ mysql is ready\"
    break   # keep if this lives inside a wait loop
  fi

  sleep 2
done

# --- Phase 3: now bring up OpenMetadata ---
\$PROVIDER -f docker-compose.yml --profile openmetadata up -d openmetadata-server
\$PROVIDER -f docker-compose.yml --profile openmetadata up -d openmetadata-ingestion

"
  prompt_return
}



start_profile_consul()       { start_profile_with_build_prompt consul; }


# Keycloak start with realm bootstrap
run_build_realm() {
  local script_dir; script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local py="python"; in_venv || py="$(ensure_python_cmd)"
  local script_path=""
  if   [[ -f "$script_dir/build_realm.py" ]]; then script_path="$script_dir/build_realm.py"
  elif [[ -f "./build_realm.py" ]]; then         script_path="./build_realm.py"
  else script_path="$(find_upwards "build_realm.py" "$script_dir" || true)"
  fi
  [[ -z "$script_path" ]] && { echo "ℹ️  build_realm.py not found; skipping."; return 0; }
  local url="${KEYCLOAK_URL:-http://localhost:8080}"
  if command -v curl >/dev/null 2>&1; then
    echo "⏳ Waiting for Keycloak at ${url} …"
    local i=0; local max=60
    until curl -fsS "${url}" >/dev/null 2>&1 || (( i >= max )); do sleep 1; i=$((i+1)); done
  fi
  echo "🔧 Running realm bootstrap: ${script_path}"
  "$py" -u "$script_path" || echo "⚠️ build_realm.py exited non-zero (continuing)."
}

# --- stop + remove containers for a profile, independent of shim limitations ---
# Stop & remove ONLY the services in the given profile (keeps other profiles running)
compose_stop_rm_profile() {
  local prof="$1"
  # get services belonging to this profile from the compose file
  mapfile -t svcs < <(services_for_profile_from_yaml "$prof")
  if ((${#svcs[@]}==0)); then
    echo "ℹ️ No services found for profile '$prof' in $COMPOSE_FILE"; return 0
  fi

  echo "+ $COMPOSE -f \"$COMPOSE_FILE\" stop ${svcs[*]}"
  $COMPOSE -f "$COMPOSE_FILE" stop "${svcs[@]}" || true

  # Try native 'rm'; if unavailable (sudo podman-compose), fall back to label-based rm
  if $COMPOSE -f "$COMPOSE_FILE" rm -f -v "${svcs[@]}" 2>/dev/null; then
    :
  else
    echo "ℹ️  Using label-based cleanup (compose provider has no 'rm')"
    local project; project="$(__compose_project_name)"
    for s in "${svcs[@]}"; do
      # Remove containers just for this service in this project
      sudo podman ps -a \
        --filter "label=com.docker.compose.project=${project}" \
        --filter "label=com.docker.compose.service=${s}" -q \
      | xargs -r sudo podman rm -f -v
    done
  fi
}


# -------- Trino cert helpers --------
create_trino_cert() {
  local dir="config_files/trino/etc/keystore"
  local ks="$dir/trino-keystore.p12"
  mkdir -p "$dir"

  echo "▶️  Recreating self-signed cert + PKCS#12 keystore for Trino in $dir"

  rm -f "$ks"

  keytool -genkeypair \
    -alias trino \
    -keyalg RSA -keysize 2048 \
    -storetype PKCS12 \
    -keystore "$ks" \
    -storepass changeit -keypass changeit \
    -validity 825 \
    -dname "CN=trino" \
    -ext "SAN=dns:localhost,dns:trino,dns:trino.local,dns:trino.osss.local,dns:host.docker.internal,ip:127.0.0.1,ip:0.0.0.0" \
    -ext "BasicConstraints=ca:false" \
    -ext "ExtendedKeyUsage=serverAuth" \
    -noprompt || { echo "❌ keytool failed"; prompt_return; return 1; }

  echo "✅ Trino keystore created: $ks (password: changeit)"
  echo "🔎 Keystore contents:"
  keytool -list -keystore "$ks" -storepass changeit
  prompt_return
}
# -------- keycloak cert helpers --------
create_keycloak_cert() {
  set -euo pipefail
  local dir="config_files/keycloak"
  mkdir -p "${dir}/secrets/ca" "${dir}/secrets/keycloak"

  # 1) Root CA (self-signed)
  #    Includes CA extensions so it’s clearly a CA cert
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 \
    -subj "/CN=osss-dev-ca" \
    -keyout "${dir}/secrets/ca/ca.key" \
    -out    "${dir}/secrets/ca/ca.crt" \
    -addext "basicConstraints = critical, CA:true" \
    -addext "keyUsage = critical, keyCertSign, cRLSign"

  # 2) Keycloak server key + CSR with SANs
  openssl req -new -nodes -newkey rsa:2048 \
    -subj "/CN=keycloak" \
    -keyout "${dir}/secrets/keycloak/server.key" \
    -out    "${dir}/secrets/keycloak/server.csr" \
    -addext "subjectAltName = DNS:keycloak, DNS:keycloak.local, DNS:localhost, IP:127.0.0.1"

  # 3) Sign the server cert with the CA, adding server extensions
  #    Use a temporary extfile to include SAN + EKU/KU, and ensure CA:false
  tmp_ext="$(mktemp)"
  cat > "$tmp_ext" <<'EOF'
basicConstraints = CA:false
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:keycloak, DNS:keycloak.local, DNS:localhost, IP:127.0.0.1
EOF

  openssl x509 -req -days 365 \
    -in  "${dir}/secrets/keycloak/server.csr" \
    -CA  "${dir}/secrets/ca/ca.crt" \
    -CAkey "${dir}/secrets/ca/ca.key" \
    -CAcreateserial \
    -out "${dir}/secrets/keycloak/server.crt" \
    -extfile "$tmp_ext"

  rm -f "$tmp_ext" "${dir}/secrets/ca/ca.srl" 2>/dev/null || true

  # 4) Create a proper CA bundle (PEM **only**). Since you have no intermediates,
  #    the CA bundle is just the CA certificate.
  cp "${dir}/secrets/ca/ca.crt" "${dir}/secrets/ca/ca-bundle.pem"

  # 5) Quick sanity checks
  echo "== Bundle BEGIN markers =="
  grep -n "BEGIN CERTIFICATE" "${dir}/secrets/ca/ca-bundle.pem"
  echo "== Verify server against CA =="
  openssl verify -CAfile "${dir}/secrets/ca/ca-bundle.pem" "${dir}/secrets/keycloak/server.crt" || true

  echo "✅ Created:"
  echo "  CA key:   ${dir}/secrets/ca/ca.key"
  echo "  CA cert:  ${dir}/secrets/ca/ca.crt"
  echo "  Bundle:   ${dir}/secrets/ca/ca-bundle.pem"
  echo "  Server key: ${dir}/secrets/keycloak/server.key"
  echo "  Server crt: ${dir}/secrets/keycloak/server.crt"

  prompt_return
}

# compose_diagnose_restart: ask for a container name and show compose/service logs
# --- Diagnose why a container is restarting (rootful compose aware) ---
compose_diagnose_restart() {
  local vm name qname
  vm="$(podman machine active 2>/dev/null || echo default)"

  if [[ -z "${1:-}" ]]; then
    read -rp "Container name to diagnose (e.g., chat-ui): " name
  else
    name="$1"
  fi
  [[ -z "$name" ]] && { echo "❌ Cancelled."; return 1; }

  # Escape for safe insertion into the remote heredoc
  qname="$(printf "%q" "$name")"

  echo "🔎 Inspecting container '$name' in VM '$vm'…"

  # 1) Inspect + recent logs + compose labels + compose logs
  podman machine ssh "$vm" 'bash -s' <<EOF
set -euo pipefail
NAME=$qname

if ! sudo podman inspect "\$NAME" >/dev/null 2>&1; then
  echo "⚠️  Container not found: \$NAME"
  exit 1
fi

echo "— state —"
sudo podman inspect --format 'Status={{.State.Status}}  ExitCode={{.State.ExitCode}}  OOM={{.State.OOMKilled}}  StartedAt={{.State.StartedAt}}  FinishedAt={{.State.FinishedAt}}' "\$NAME" || true

echo
echo "— recent logs (tail 200) —"
sudo podman logs --tail 200 "\$NAME" || true

echo
echo "— compose labels —"
proj=\$(sudo podman inspect --format '{{ index .Config.Labels "io.podman.compose.project" }}' "\$NAME" 2>/dev/null || true)
[[ -z "\$proj" ]] && proj=\$(sudo podman inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' "\$NAME" 2>/dev/null || true)
svc=\$(sudo podman inspect --format '{{ index .Config.Labels "io.podman.compose.service" }}' "\$NAME" 2>/dev/null || true)
[[ -z "\$svc" ]] && svc=\$(sudo podman inspect --format '{{ index .Config.Labels "com.docker.compose.service" }}' "\$NAME" 2>/dev/null || true)
echo " project: \${proj:-<none>}"
echo " service: \${svc:-<none>}"

if [[ -n "\$proj" && -n "\$svc" ]]; then
  echo
  echo "— compose logs (tail 100) for \${proj}/\${svc} —"
  if [[ -f /work/docker-compose.yml ]]; then
    sudo podman compose -p "\$proj" -f /work/docker-compose.yml logs --tail 100 --no-color "\$svc" || true
  else
    sudo podman compose -p "\$proj" logs --tail 100 --no-color "\$svc" || true
  fi
fi
EOF

  # 2) Optional live follow
  read -rp "▶ Follow live logs? (y/N) " yn
  if [[ "$yn" =~ ^[Yy]$ ]]; then
    podman machine ssh "$vm" 'bash -s' <<EOF
set +e
sudo podman logs -f --tail 50 $qname || true
EOF
  fi
}



# -------- openmetadata truststore (for OIDC over HTTPS) --------
create_openmetadata_truststore() {
  set -euo pipefail
  local ca="config_files/keycloak/secrets/ca/ca.crt"     # from your create_keycloak_cert()
  local dir="config_files/openmetadata/certs"
  local ts="$dir/om-truststore.p12"
  mkdir -p "$dir"

  if [[ ! -s "$ca" ]]; then
    echo "❌ CA not found at $ca. Run create_keycloak_cert first."
    prompt_return; return 1
  fi

  echo "▶️  Recreating OpenMetadata truststore at $ts"
  rm -f "$ts"

  keytool -importcert \
    -alias keycloak-ca \
    -file "$ca" \
    -storetype PKCS12 \
    -keystore "$ts" \
    -storepass changeit \
    -noprompt

  echo "✅ Truststore created: $ts (password: changeit)"
  echo "🔎 Contents:"
  keytool -list -keystore "$ts" -storepass changeit
  prompt_return
}

# -------- teardown & cleanup --------

__compose_named_volumes_for_service() {
  # Arg1: service name
  local svc="$1"
  awk -v target="$svc" '
    BEGIN{
      in_services=0; in_svc=0; in_vols=0; in_item=0; # YAML-ish state
    }
    /^[[:space:]]*services[[:space:]]*:/ { in_services=1; next }

    in_services {
      # leaving services block
      if ($0 ~ /^[^[:space:]]/ && $0 !~ /^[[:space:]]/) { in_services=0; in_svc=0; in_vols=0; next }

      # service header (two spaces, then "<name>:")
      if ($0 ~ /^[[:space:]]{2}[A-Za-z0-9._-]+:[[:space:]]*$/) {
        line=$0; sub(/^[[:space:]]+/,"",line); sub(/:.*/,"",line);
        in_svc = (line==target); in_vols=0; in_item=0; next
      }

      # only parse volumes inside the target service
      if (in_svc) {
        # start of volumes block
        if ($0 ~ /^[[:space:]]{4}volumes:[[:space:]]*$/) { in_vols=1; in_item=0; next }

        # inline list: volumes: [a:/x, b:/y]
        if ($0 ~ /^[[:space:]]{4}volumes:[[:space:]]*\[/) {
          s=$0; sub(/^[^[]*\[/,"",s); sub(/\].*$/,"",s)
          n=split(s, arr, ",")
          for(i=1;i<=n;i++){
            v=arr[i]; gsub(/^[[:space:]]+|[[:space:]]+$/,"",v)
            # grab left of ":" if present
            split(v, kv, ":"); src=kv[1]
            # ignore binds like ./ or / or ${...}
            if (src !~ /^(\.\/|\/|\$\{)/ && src!="") print src
          }
          next
        }

        if (in_vols) {
          # end volumes block if new key at same indent
          if ($0 ~ /^[[:space:]]{4}[A-Za-z0-9._-]+:/) { in_vols=0; in_item=0; next }

          # list item start
          if ($0 ~ /^[[:space:]]{6}-[[:space:]]*/) {
            in_item=1
            # shorthand: "- volname:/container/path"
            item=$0; sub(/^[^ -]*-[[:space:]]*/,"",item)
            if (item ~ /:/) {
              split(item, kv, ":"); src=kv[1]
              gsub(/[[:space:]]*/,"",src)
              if (src !~ /^(\.\/|\/|\$\{)/ && src!="") print src
              in_item=0
            }
            next
          }

          # long form inside list item: "source: volname"
          if (in_item && $0 ~ /^[[:space:]]{8}source:[[:space:]]*/) {
            src=$0; sub(/^[^:]*:[[:space:]]*/,"",src)
            gsub(/^[[:space:]]+|[[:space:]]+$/,"",src)
            if (src !~ /^(\.\/|\/|\$\{)/ && src!="") print src
            next
          }
        }
      }
    }
  ' "${COMPOSE_FILE:-docker-compose.yml}" | awk 'NF && !seen[$0]++'
}

# Return 0 if compose supports --profile (podman compose / docker compose), 1 otherwise (podman-compose)
compose_supports_profile() {
  local cmd="$(__compose_cmd)" || return 1
  # crude but reliable: podman-compose is a python wrapper and doesn't accept 'help --profile'
  if command -v sudo podman-compose >/dev/null 2>&1 && [[ "$cmd" == podman-compose* ]]; then
    return 1
  fi
  return 0
}

# Safe "config --services" into a bash array
compose_list_services() {
  local cmd="$(__compose_cmd)" || return 1
  mapfile -t __SERVS < <($cmd config --services 2>/dev/null | awk 'NF')
  printf "%s\n" "${__SERVS[@]}"
}

# Convenience runner that prints the command first
compose_up_services() {
  local cmd="$(__compose_cmd)" || return 1
  echo "+ $cmd up -d --no-deps $*"
  $cmd up -d --no-deps "$@"
}

# Return top-level *volume keys* from the rendered compose config.
# e.g. outputs: es-data, es-shared, ...
compose_top_level_volume_keys() {
  local CMD; CMD="$(__compose_cmd)" || return $?
  local FILE="${COMPOSE_FILE:-docker-compose.yml}"
  local -a CMDA; IFS=' ' read -r -a CMDA <<<"$CMD"

  "${CMDA[@]}" -f "$FILE" config 2>/dev/null | awk '
    function indent(s){ match(s, /^[ \t]*/); return RLENGTH }
    BEGIN { in_vols=0; vindent=-1 }
    /^[ \t]*volumes:[ \t]*$/ { in_vols=1; vindent=indent($0); next }
    {
      if (in_vols) {
        line_indent = indent($0)
        if ($0 ~ /^[ \t]*$/) next
        # leave volumes when dedent to top or next top-level key
        if (line_indent <= vindent && $0 !~ /^[ \t]/) { in_vols=0; next }
        # keys under volumes: "  es-data:" → print "es-data"
        if ($0 ~ /^[ \t]*[A-Za-z0-9._-]+:[ \t]*$/ && line_indent > vindent) {
          k=$0; sub(/^[ \t]+/,"",k); sub(/:.*/,"",k); print k
        }
      }
    }'
}



# --- find named volumes for services via normalized compose config ---
compose_named_vols_for_services_cli() {
  local PROFILE="$1"; shift
  local SERVICES=("$@")
  local CMD; CMD="$(__compose_cmd)" || return 0

  # split "podman compose" / "docker compose" into argv
  local -a CMD_ARR; IFS=' ' read -r -a CMD_ARR <<< "$CMD"

  local FILE="${COMPOSE_FILE:-docker-compose.yml}"
  local cfg=""
  if ! cfg="$("${CMD_ARR[@]}" -f "$FILE" --profile "$PROFILE" config 2>/dev/null)"; then
    cfg="$("${CMD_ARR[@]}" -f "$FILE" config 2>/dev/null || true)"
  fi
  [[ -z "$cfg" ]] && return 0

  # ✅ correct way to pass a shell var to BSD awk:
  local list; list="$(printf '%s ' "${SERVICES[@]}")"

  printf '%s\n' "$cfg" | awk -v list="$list" '
    function has(x, s,   i,n,a){ n=split(s,a," "); for(i=1;i<=n;i++) if(a[i]==x) return 1; return 0 }
    function indent(s){ match(s,/^[ \t]*/); return RLENGTH }

    BEGIN { in_services=0; in_target=0; in_vols=0; in_item=0; sind=-1; vind=-1; svc="" }

    /^[ \t]*services:[ \t]*$/ { in_services=1; sind=indent($0); next }

    in_services {
      lin=indent($0)
      # leaving services section
      if (lin <= sind && $0 !~ /^[ \t]*$/) { in_services=0; in_target=0; in_vols=0; in_item=0; next }

      # service header "<name>:"
      if (match($0,/^[ \t]*([A-Za-z0-9._-]+):[ \t]*$/,m)) { svc=m[1]; in_target=has(svc,list); in_vols=0; in_item=0; next }
      if (!in_target) next

      # start of volumes block
      if ($0 ~ /^[ \t]*volumes:[ \t]*$/) { in_vols=1; vind=lin; in_item=0; next }

      # inline volumes: [a:/x, b:/y]
      if ($0 ~ /^[ \t]*volumes:[ \t]*\[/) {
        s=$0; sub(/^[^[]*\[/,"",s); sub(/\].*$/,"",s)
        n=split(s,a,","); for(i=1;i<=n;i++){
          v=a[i]; gsub(/^[ \t]+|[ \t]+$/,"",v)
          split(v,kv,":"); src=kv[1]
          if (src !~ /^(\/|\.\/|\$\{)/ && src!="") print src
        }
        next
      }

      if (in_vols) {
        # end of block when dedent or new key
        if (lin <= vind && $0 !~ /^[ \t]*$/) { in_vols=0; in_item=0; next }

        # short form: "- vol:/path"
        if ($0 ~ /^[ \t]*-[ \t]*[^:]+:[^:]+$/) {
          item=$0; sub(/^[^ -]*-[ \t]*/,"",item)
          split(item,kv,":"); src=kv[1]; gsub(/[ \t]/,"",src)
          if (src !~ /^(\/|\.\/|\$\{)/ && src!="") print src
          next
        }

        # start of long form item "-"
        if ($0 ~ /^[ \t]*-[ \t]*$/) { in_item=1; next }

        # long form field "source: volname"
        if (in_item && $0 ~ /^[ \t]*source:[ \t]*/) {
          src=$0; sub(/^[^:]*:[ \t]*/,"",src); gsub(/^[ \t]+|[ \t]+$/,"",src)
          if (src !~ /^(\/|\.\/|\$\{)/ && src!="") print src
          next
        }

        # next item
        if (in_item && $0 ~ /^[ \t]*-[ \t]*/) { in_item=0 }
      }
    }'
}

# -------- Host info --------
show_status(){
  echo "▶️  Containers (all projects)"
  printf "NAMES\tSTATUS\tNETWORKS\n"

  sudo podman ps -a --format '{{.Names}}\t{{.Status}}\t{{.Networks}}' | awk 'NF' || true

  echo
  echo "▶️  Networks:"
  sudo podman network ls | (head -n1; awk 'NR==1{print}; NR>1{print "  "$0}') || true

  echo
  echo "ℹ️  Hint: use 'podman logs <container>' or 'sudo podman inspect <container>' for details."
}



# --- remove project volumes for selected services (works even if no containers exist) ---
remove_volumes_for_services() {
  local project="$1"; shift
  local prof="$1"; shift
  local svcs=("$@")

  # Which engine are we talking to?
  local ENGINE; ENGINE="$(get_compose_engine)"

  # 1) Collect attached volumes from existing containers (if any)
  local project_label service_label
  if [[ "$ENGINE" == "podman" ]]; then
    project_label="io.podman.compose.project"
    service_label="io.podman.compose.service"
  else
    project_label="com.docker.compose.project"
    service_label="com.docker.compose.service"
  fi

  local -a ps_args=('ps' '-a' '--format' '{{.ID}}' '--filter' "label=${project_label}=${project}")
  local s
  for s in "${svcs[@]}"; do
    ps_args+=(--filter "label=${service_label}=${s}")
  done

  local CIDS
  CIDS="$(engine_exec "$ENGINE" "${ps_args[@]}" | awk 'NF')" || CIDS=""

  local VOL_ATTACHED=""
  if [[ -n "$CIDS" ]]; then
    VOL_ATTACHED="$(
      engine_exec "$ENGINE" inspect -f '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{"\n"}}{{end}}{{end}}' $CIDS \
        | awk 'NF && !seen[$0]++'
    )"
  fi

  # 2) Collect named volumes from compose config for the same services
  local -a base_vols=()
  # readarray is shimmed to mapfile in this script for Bash 3.x
  # tolerate awk/parse failure without tripping set -euo pipefail
  if ! readarray -t base_vols < <(compose_named_vols_for_services_cli "$prof" "${svcs[@]}" 2>/dev/null || true); then
    base_vols=()
  fi

  # Elastic-specific safety net (if parsing ever returns empty)
  if [[ "$prof" == "elastic" && ${#base_vols[@]} -eq 0 ]]; then
    base_vols=(es-data es-shared)
  fi

  # 3) Union of everything we’ve found
  local -a to_remove=()
  if [[ -n "$VOL_ATTACHED" ]]; then
    while IFS= read -r v; do
      [[ -n "$v" ]] && to_remove+=("$v")
    done <<<"$VOL_ATTACHED"
  fi

  if ((${#base_vols[@]})); then
    for v in "${base_vols[@]}"; do
      to_remove+=("$v" "${project}_${v}")
    done
  fi

  # 4) Dedup (portable) and remove only those that actually exist
  #    (mapfile is shimmed on macOS Bash 3.x)
  mapfile -t to_remove < <(printf '%s\n' "${to_remove[@]}" | awk 'NF && !seen[$0]++')

  if ((${#to_remove[@]})); then
    local vname
    for vname in "${to_remove[@]}"; do
      # Check existence before removing
      if $ENGINE volume inspect "$vname" >/dev/null 2>&1; then
        echo "🧹 Removing volume: $vname"
        $ENGINE volume rm -f "$vname" >/dev/null 2>&1 || true
      fi
    done
  fi
}



# --- helpers ---------------------------------------------------------------

__compose_label_keys() {
  local CMD; CMD="$(__compose_cmd)" || return 1
  local ENGINE
  ENGINE="$(printf '%s\n' "$CMD" | awk '{print $1}')"  # "podman" or "docker"
  if [[ "$ENGINE" == "podman" ]]; then
    PROJECT_LABEL="io.podman.compose.project"
    SERVICE_LABEL="io.podman.compose.service"
  else
    PROJECT_LABEL="com.docker.compose.project"
    SERVICE_LABEL="com.docker.compose.service"
  fi
}

# --- resolve services in a profile using compose itself ---
compose_services_for_profile() {
  local prof="$1"
  local CMD; CMD="$(__compose_cmd)" || return 1
  local FILE="${COMPOSE_FILE:-docker-compose.yml}"
  "$CMD" -f "$FILE" --profile "$prof" config --services 2>/dev/null | awk 'NF'
}

# -------- Podman reset helper --------
reset_podman_machine() {
  echo "⚠️  This will wipe all Podman machine state and start clean."
  read -rp "Proceed? [y/N] " ans || true
  [[ ! "$ans" =~ ^[Yy]$ ]] && { echo "❌ Cancelled."; prompt_return; return 0; }

  set -euo pipefail

  sudo podman --version || true

  # Decide a machine name: use active if present, else 'default'
  NAME="${PODMAN_MACHINE_NAME:-$(podman machine active 2>/dev/null || echo default)}"

  # 1) Stop if it exists
  if podman machine inspect "$NAME" >/dev/null 2>&1; then
    echo "▶️  Stopping podman machine '$NAME'…"
    podman machine stop "$NAME" || true
    echo "🗑  Removing '$NAME'…"
    podman machine rm -f "$NAME" || true
  else
    echo "(no VM named '$NAME' to stop/remove)"
  fi

  # 2) Drop stale connections (both rootless/root)
  podman system connection rm "$NAME" "$NAME-root" 2>/dev/null || true

  # 3) macOS: clear any leftover local state safely (best-effort)
  if [[ "$(uname -s)" == "Darwin" ]]; then
    rm -rf ~/.config/containers/podman/machine \
           ~/.local/share/containers/podman/machine \
           ~/.ssh/"$NAME"* 2>/dev/null || true
  fi

  # 4) Recreate + start
  echo "🛠  Initializing '$NAME'…"
  podman machine init "$NAME" \
  --rootful \
  --cpus "${PODMAN_MACHINE_CPUS:-12}" \
  --memory "${PODMAN_MACHINE_MEM_MB:-40960}" \
  --disk-size "${PODMAN_MACHINE_DISK_GB:-100}" \
  --volume "${PWD}:/work"

  echo "▶️  Starting '$NAME'…"
  podman machine start "$NAME"


  # 5) Make it the default connection if possible
  podman system connection default "$NAME" 2>/dev/null \
    || podman system connection default "$NAME-root" 2>/dev/null \
    || true

  # 6) Sanity test
  sudo podman run --rm quay.io/podman/hello || true
  prompt_return
}


# Return 0 if safe to proceed; nonzero if storage looks broken.
# Logs only; does NOT modify system state. You can opt-in to auto fixes via env flags.
# Preflight: detect Podman graph root robustly, across versions and remote/local.
preflight_podman_storage() {
  echo "[preflight_podman_storage] Running…"

  # 1) Grab JSON info (prefer this over plain text/greps)
  local INFO RC
  INFO="$(sudo podman info --format '{{json .}}' 2>/dev/null)"; RC=$?
  if ((RC!=0)) || [[ -z "$INFO" ]]; then
    echo "[preflight_podman_storage] ❌ Could not run 'sudo podman info' (rc=$RC)"
    return 1
  fi
  echo "[preflight_podman_storage] Successfully retrieved 'podman info'"

  # 2) Detect remote mode (best-effort; schema differs by version)
  # Try top-level remoteClient, fall back to host.remoteSocket.path presence
  local REMOTE=""
  REMOTE="$(printf '%s' "$INFO" | sed -n 's/.*"remoteClient":[[:space:]]*\(true\|false\).*/\1/p')"
  if [[ -z "$REMOTE" ]]; then
    # If we see a remote socket path, assume remote
    if printf '%s\n' "$INFO" | grep -q '"host"[^{]*"remoteSocket"'; then
      REMOTE=true
    fi
  fi
  echo "[preflight_podman_storage] remoteClient (best-effort): ${REMOTE:-unknown}"

  # 3) Get graph root from JSON first
  local GRAPHROOT=""
  GRAPHROOT="$(printf '%s' "$INFO" | sed -n 's/.*"graphRoot":[[:space:]]*"\([^"]*\)".*/\1/p')"

  # 4) If empty, try Go template key (works across many versions)
  if [[ -z "$GRAPHROOT" ]]; then
    GRAPHROOT="$(sudo podman info --format '{{ .Store.GraphRoot }}' 2>/dev/null || true)"
  fi

  # 5) If still empty on macOS, ask inside the VM directly
  if [[ -z "$GRAPHROOT" && "$(uname -s)" == "Darwin" ]] && pm_ssh inspect >/dev/null 2>&1; then
    GRAPHROOT="$(pm_ssh ssh -- podman info --format '{{ .Store.GraphRoot }}' 2>/dev/null || true)"
    echo "[preflight_podman_storage] Queried VM for GraphRoot."
  fi

  # 6) Final check
  if [[ -z "$GRAPHROOT" ]]; then
    echo "[preflight_podman_storage] ⚠️  Could not detect GraphRoot in this Podman build."
    echo "[preflight_podman_storage] Store section follows (for debugging):"
    sudo podman info --format '{{json .Store}}' || true
    echo "   Tip: ensure your default connection is the VM:"
    echo "        podman system connection default podman-machine-default"
    echo "        pm_ssh start"
    return 1
  fi

  echo "[preflight_podman_storage] GraphRoot: $GRAPHROOT"
  return 0
}






# Run a compose command; print only the command's stdout.
# All our wrapper logs go to stderr so they never leak into argv.
compose_exec() {
  # USAGE: compose_exec <cmd> <args...>
  echo "[compose_exec] ${*}" >&2
  "$@"                             # stream stdout as-is
  local rc=$?
  echo "[compose_exec] rc=$rc" >&2
  return $rc
}

# --- main -----------------------------------------------------------------



down_profile_interactive() {
  echo "[down_profile_interactive] Invoked"

  echo "[down_profile_interactive] Determining compose command..."
  local CMD; CMD="$(__compose_cmd)" || {
    echo "[down_profile_interactive] Failed to determine compose command → exiting"
    return $?
  }
  echo "[down_profile_interactive] Using compose command: $CMD"

  echo "[down_profile_interactive] Determining project/file..."
  local PROJECT; PROJECT="$(__compose_project_name)"
  local COMPOSE_FILE_LOCAL="${COMPOSE_FILE:-docker-compose.yml}"
  echo "[down_profile_interactive] Project: $PROJECT"
  echo "[down_profile_interactive] Compose file: $COMPOSE_FILE_LOCAL"

  echo "[down_profile_interactive] Splitting compose command to detect engine..."
  local -a CMD_ARR; IFS=' ' read -r -a CMD_ARR <<< "$CMD"
  local ENGINE="${CMD_ARR[0]}"; [[ "$ENGINE" == "docker-compose" ]] && ENGINE="docker"
  echo "[down_profile_interactive] Engine: $ENGINE | argv: ${CMD_ARR[*]}"

  echo "ℹ️ ---- Podman storage preflight ------------------------------------------"
  if [[ "$ENGINE" == podman* ]]; then
    if ! preflight_podman_storage "$ENGINE"; then
      echo "⚠️  Podman storage/VM looks unhealthy. Aborting teardown to avoid errors." >&2
      echo "   Run: 'pm_ssh start' and/or 'podman system migrate', then retry." >&2
      prompt_return
      return 1
    fi
  fi

  echo "ℹ️  Using compose command: $CMD"
  echo "ℹ️  Compose project: $PROJECT"
  echo "ℹ️  Compose file:    $COMPOSE_FILE_LOCAL"

  echo "[down_profile_interactive] Discovering profiles..."
  mapfile -t PROFILES < <(discover_profiles)
  echo "🔎 Detected profiles: ${PROFILES[*]:-(none)}"
  if [ "${#PROFILES[@]}" -eq 0 ]; then
    echo "⚠️  No profiles found."
    echo "[down_profile_interactive] Exiting early (no profiles)"
    return 0
  fi

  echo "[down_profile_interactive] Presenting interactive menu..."
  echo "Available profiles:"
  local i=1
  for p in "${PROFILES[@]}"; do printf "  %2d) %s\n" "$i" "$p"; i=$((i+1)); done
  echo "  q) Cancel"
  read -r -p "Select a profile to take down: " choice || {
    echo "[down_profile_interactive] Read aborted; exiting"
    return 0
  }
  case "$choice" in
    q|Q) echo "❌ Cancelled."; echo "[down_profile_interactive] User cancelled"; return 0 ;;
  esac
  echo "[down_profile_interactive] Raw selection: '$choice'"

  local prof
  if [[ "$choice" =~ ^[0-9]+$ ]] && [ "$choice" -ge 1 ] && [ "$choice" -le "${#PROFILES[@]}" ]; then
    prof="${PROFILES[$((choice-1))]}"
    echo "✅ Selected by number: $prof"
  else
    prof="$choice"
    echo "✅ Selected by name: $prof"
  fi


  {
    echo "[down_profile_interactive] Entering teardown (set -x enabled for commands)"
    set -x

    echo "ℹ️ Stop and remove via compose first (engine-agnostic)"
    #compose_exec "${CMD_ARR[@]}" -f "$COMPOSE_FILE_LOCAL" stop "${SVCS[@]}" || true

    # On the HOST shell (where $PWD is your project)
      podman machine ssh default -- bash -lc "
        set -euo pipefail
        HOST_PROJ=\"/work\"
        SERVICE=$prof
        PODMAN_OVERLAY_DIR=$PODMAN_OVERLAY_DIR
        declare -a SVCS=()
        declare -a CIDS=()
        declare -a VOLS=()

        echo \"HOST_PROJ: \${HOST_PROJ}\"
        echo \"PODMAN_OVERLAY_DIR: \${PODMAN_OVERLAY_DIR}\"
        cd \"\$HOST_PROJ\" || { echo '❌ Path not visible inside VM:' \"\$HOST_PROJ\"; exit 1; }

        test -r docker-compose.yml || { echo \"❌ docker-compose.yml not readable here: \$PWD\"; ls -la; exit 1; }


        # Pick compose provider + the correct remove-volumes flag
        if sudo podman compose version >/dev/null 2>&1; then
          COMPOSE=\"sudo podman compose\"
          DOWN_VOL_FLAG=\"--volumes\"
        elif command -v sudo podman-compose >/dev/null 2>&1; then
          COMPOSE=\"sudo podman-compose\"
          DOWN_VOL_FLAG=\"-v\"
        else
          echo \"❌ Neither podman compose nor podman-compose found.\"
          exit 1
        fi

        # Ensure project name matches compose default (lowercased basename)
        PROJECT=\"\${COMPOSE_PROJECT_NAME:-\$(basename \"\$PWD\" | tr '[:upper:]' '[:lower:]')}\"
        export COMPOSE_PROJECT_NAME=\"\$PROJECT\"
        echo \"PROJECT: \$PROJECT\"
        echo \"▶️  Teardown for profile=\$SERVICE (targeted: services & volumes only)\"

        # Services in this profile
        SVCS=()  # ensure declared under set -u
        mapfile -t SVCS < <(\$COMPOSE -f \"\$HOST_PROJ/docker-compose.yml\" --profile \"\$SERVICE\" \
          config --services 2>/dev/null | awk 'NF') || true

        if ((\${#SVCS[@]}==0)); then
          echo \"ℹ️ No services found for profile '\$SERVICE' (nothing to clean).\"
          exit 0
        fi

        # 2) Pick correct compose label keys (keep for logs only)
        # 2) Pick correct compose label keys (keep for logs only)
        project_label=\"io.podman.compose.project\"
        service_label=\"io.podman.compose.service\"
        if ! podman ps -a --filter \"label=\${project_label}=\${PROJECT}\" -q | grep -q .; then
          project_label=\"com.docker.compose.project\"
          service_label=\"com.docker.compose.service\"
        fi

        # Containers for this project + those services (UNION both label namespaces)
        CIDS=() VOLS=()
        tmp_ids=()
        for s in \"\${SVCS[@]}\"; do
          mapfile -t ids1 < <(sudo podman ps -a -q \
            --filter \"label=io.podman.compose.project=\${PROJECT}\" \
            --filter \"label=io.podman.compose.service=\${s}\" 2>/dev/null || true)
          mapfile -t ids2 < <(sudo podman ps -a -q \
            --filter \"label=com.docker.compose.project=\${PROJECT}\" \
            --filter \"label=com.docker.compose.service=\${s}\" 2>/dev/null || true)
          tmp_ids+=(\"\${ids1[@]:-}\" \"\${ids2[@]:-}\")
        done
        # unique
        mapfile -t CIDS < <(printf '%s\n' \"\${tmp_ids[@]:-}\" | awk 'NF && !seen[\$0]++')
        echo \"→ Matched \${#CIDS[@]} container(s) for services: \${SVCS[*]}\"

        if ((\${#CIDS[@]})); then
          # Volumes mounted by those containers
          mapfile -t VOLS < <(
            sudo podman inspect -f '{{range .Mounts}}{{if eq .Type \"volume\"}}{{.Name}}{{\"\n\"}}{{end}}{{end}}' \
              \"\${CIDS[@]}\" | awk 'NF && !seen[\$0]++'
          ) || true

          echo \"⏹  Stopping containers...\"
          sudo podman stop -t 10 \"\${CIDS[@]}\" >/dev/null 2>&1 || true
          echo \"🗑️  Removing containers...\"
          sudo podman rm -f \"\${CIDS[@]}\" >/dev/null 2>&1 || true





          if ((\${#VOLS[@]})); then
            echo \"🧹 Removing profile volumes: \${VOLS[*]}\"
            sudo podman volume rm -f \"\${VOLS[@]}\" >/dev/null 2>&1 || true
          else
            echo \"ℹ️ No named volumes attached to \${SVCS[*]}.\"
          fi
        else
          echo \"ℹ️ No containers found for services: \${SVCS[*]}\"
          echo \"   (Tip: containers may exist under the other label namespace or a different project name)\"
        fi

      "


  }


  echo "ℹ️ Post-teardown hook (optional per-profile cleanup)"
  if type down_profile_clean >/dev/null 2>&1; then
    # Run for all profiles…
    # down_profile_clean "$prof"

    # …or only for elastic:
    case "$prof" in
      elastic) down_profile_clean "elastic" ;;
    esac
  fi


  echo "✅ Done with profile '${prof}'."
  echo "[down_profile_interactive] Returning to menu..."
  prompt_return
  echo "[down_profile_interactive] Finished execution"
  set +x
}



# -------- Podman VM management --------
# Returns the name of a running VM, or "default" if none running
__podman_vm_name() {
  local n
  n="$(pm_ssh list --format '{{.Name}} {{.Running}}' 2>/dev/null \
       | awk '$2=="true"{print $1; exit}')" || true
  echo "${n:-default}"
}

# Run a command inside the VM (nounset-safe)
pm_ssh() {
  local vm; vm="$(__podman_vm_name)"
  podman machine ssh "$vm" -- "$@"
}

podman_vm_stop() {
  if ! command -v podman >/dev/null 2>&1; then
    echo "Podman not installed."
    return 1
  fi
  local NAME; NAME="$(podman_vm_name)"
  echo "▶️  Stopping pm_ssh '$NAME'…"
  pm_ssh stop "$NAME" || {
    echo "(already stopped or not present)"
    return 0
  }
  echo "✅ Stopped."
}
podman_vm_destroy() {
  if ! command -v sudo podman >/dev/null 2>&1; then
    echo "Podman not installed."
    return 1
  fi
  local NAME; NAME="$(podman_vm_name)"
  echo "⚠️  This will remove the Podman VM '$NAME' and its data (images/containers inside the VM)."
  read -rp "Type the machine name '$NAME' to confirm destroy (or leave blank to cancel): " ans || return 1
  if [[ "$ans" != "$NAME" ]]; then
    echo "Cancelled."
    return 1
  fi
  echo "▶️  Stopping (if running)…"; pm_ssh stop "$NAME" >/dev/null 2>&1 || true
  echo "🗑  Removing pm_ssh '$NAME'…"
  pm_ssh rm -f "$NAME"
  echo "✅ Destroyed pm_ssh '$NAME'."
}


# -------- menu --------
refresh_services() { :; } # compatibility no-op

logs_menu() {
  local tail_n="${TAIL:-$DEFAULT_TAIL}"
  local choice svc_count svc
  local __LOG_SERVICES=()

  # Resolve compose command into an ARRAY (handles spaces in "podman compose" or "podman machine ssh -- podman compose")
  local -a C
  IFS=' ' read -r -a C <<< "${COMPOSE:-podman compose}"

  local file="${COMPOSE_FILE:-docker-compose.yml}"
  local project="${COMPOSE_PROJECT_NAME:-$(basename "$PWD")}"

  echo
  echo "[logs_menu] COMPOSE: ${COMPOSE:-podman compose}"
  echo "[logs_menu] COMPOSE_FILE: ${file}"
  echo "[logs_menu] COMPOSE_PROJECT_NAME: ${project}"
  echo "[logs_menu] TAIL lines: ${tail_n}"
  if [[ -n "${SERVICE:-}" ]]; then
    echo "[logs_menu] SERVICE env detected: ${SERVICE}  (note: unrelated to compose services)"
  fi

  while true; do
    # Prefer running services; fall back to all defined services
    if mapfile -t __LOG_SERVICES < <("${C[@]}" -f "$file" ps --services 2>/dev/null); then
      :
    else
      __LOG_SERVICES=()
    fi
    if (( ${#__LOG_SERVICES[@]} == 0 )); then
      mapfile -t __LOG_SERVICES < <("${C[@]}" -f "$file" config --services 2>/dev/null || true)
    fi

    svc_count="${#__LOG_SERVICES[@]}"
    echo
    echo "==== Logs Menu (${project}) ===="
    echo "Enter a number to follow that service's logs."
    echo "a) follow ALL services"
    echo "t) tail ALL services (no follow)"
    echo "s) set default tail (currently ${DEFAULT_TAIL})"
    echo "r) refresh services   b) back   q) quit"
    echo

    if (( svc_count == 0 )); then
      echo "(No services found for project ${project})"
      echo "[diag] '${C[*]} -f \"$file\" config --services' returned:"
      "${C[@]}" -f "$file" config --services 2>&1 | sed 's/^/  > /'
    else
      local i
      for ((i=0;i<svc_count;i++)); do
        printf "  %2d) %s\n" "$((i+1))" "${__LOG_SERVICES[$i]}"
      done
    fi

    read -rp "Choice: " choice || return 0
    case "$choice" in
      b|B) return 0 ;;
      q|Q) echo "Bye!"; exit 0 ;;
      r|R) continue ;;
      s|S) set_default_tail ;;
      a|A)
        echo "Following logs for ALL services. Ctrl-C to return…"
        ( trap - INT; "${C[@]}" -f "$file" logs -f --tail "$tail_n" ) || true
        ;;
      t|T)
        echo "Tailing (no follow) logs for ALL services…"
        "${C[@]}" -f "$file" logs --tail "$tail_n" || true
        ;;
      *)
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice>=1 && choice<=svc_count )); then
          svc="${__LOG_SERVICES[$((choice-1))]}"
          echo "Following logs for service: ${svc} (Ctrl-C to return)…"
          ( trap - INT; "${C[@]}" -f "$file" logs -f --tail "$tail_n" "$svc" ) || true
        else
          echo "Unknown choice: ${choice}"
        fi
        ;;
    esac
  done
}


# --- Override: start_keycloak_services (ensure network first) ---
ensure_osss_net() {
  if ! sudo podman network exists osss-net 2>/dev/null; then
    echo "➕ Creating external network: osss-net"
    sudo podman network create osss-net >/dev/null || echo "⚠️  Could not create osss-net (continuing)"
  fi
}


# Follow logs for a single container; Ctrl-C cleanly returns to menu
logs_follow_container() {
  local name="$1"
  local tail_n="${2:-$DEFAULT_TAIL}"
  local vm use_vm="0" state rc=0

  # Detect active VM and whether it's running
  vm="$(podman machine active 2>/dev/null || echo default)"
  state="$(podman machine inspect "$vm" --format '{{.State}}' 2>/dev/null || echo '')"
  case "$state" in
    running|Running) use_vm="1" ;;
  esac

  echo "Following logs for container: ${name} (Ctrl-C to return)…"

  # Run follower in a subshell; clear INT trap so Ctrl-C stops it; don't kill menu on nonzero exit
  set +e
  if [[ "$use_vm" == "1" ]]; then
    # Ensure ROOTFUL podman.socket is up inside the VM, then follow logs via rootful engine
    (
      trap - INT
      podman machine ssh "$vm" -- bash -lc '
        # make sure rootful socket is active (idempotent)
        sudo systemctl enable --now podman.socket >/dev/null 2>&1 || true
        # follow logs using ROOTFUL podman
        sudo podman logs -f --tail '"$tail_n"' "'"$name"'"
      '
    ) || true
  else
    # Fallback: host (Linux without VM)
    ( trap - INT; sudo podman logs -f --tail "$tail_n" "$name" ) || true
  fi
  rc=$?
  set -e

  echo "↩ Back to menu"
  return $rc
}


logs_menu() {
  while true; do
    echo
    echo "==============================================="
    echo " Logs"
    echo "==============================================="
    echo "1) Logs container 'ai-redis'"
    echo "2) Logs container 'ai-postgres'"
    echo "3) Logs container 'airflow-init'"
    echo "4) Logs container 'airflow-redis'"
    echo "5) Logs container 'airflow-scheduler'"
    echo "6) Logs container 'airflow-webserver'"
    echo "7) Logs container 'app'"
    echo "8) Logs container 'consul'"
    echo "9) Logs container 'consul-jwt-init'"
    echo "10) Logs container 'elasticsearch'"
    echo "11) Logs container 'execute_migrate_all'"
    echo "12) Logs container 'filebeat'"
    echo "13) Logs container 'filebeat-setup'"
    echo "14) Logs container 'kc_postgres'"
    echo "15) Logs container 'keycloak'"
    echo "16) Logs container 'kibana'"
    echo "17) Logs container 'kibana-pass-init'"
    echo "18) Logs container 'minio'"
    echo "19) Logs container 'ollama'"
    echo "20) Logs container 'om-elasticsearch'"
    echo "21) Logs container 'openmetadata-ingestion'"
    echo "22) Logs container 'openmetadata-mysql'"
    echo "23) Logs container 'openmetadata-server'"
    echo "24) Logs container 'osss_postgres'"
    echo "25) Logs container 'postgres-airflow'"
    echo "26) Logs container 'postgres-superset'"
    echo "27) Logs container 'qdrant'"
    echo "28) Logs container 'redis'"
    echo "29) Logs container 'shared-vol-init'"
    echo "30) Logs container 'superset'"
    echo "31) Logs container 'superset-init'"
    echo "32) Logs container 'superset_redis'"
    echo "33) Logs container 'trino'"
    echo "34) Logs container 'vault'"
    echo "35) Logs container 'vault-oidc-setup'"
    echo "36) Logs container 'vault-seed'"
    echo "37) Logs container 'web'"
    echo "38) Logs container 'chat-ui'"
    echo "39) Logs container 'rasa-mentor'"
    echo "  q) Back"
    echo "-----------------------------------------------"
    read -rp "Select an option: " choice || return 0
    case "$choice" in
      1) logs_follow_container "ai-redis" ;;
      2) logs_follow_container "ai-postgres" ;;
      3)  logs_follow_container "airflow-init" ;;
      4)  logs_follow_container "airflow-redis" ;;
      5)  logs_follow_container "airflow-scheduler" ;;
      6)  logs_follow_container "airflow-webserver" ;;
      7)  logs_follow_container "app" ;;
      8)  logs_follow_container "consul" ;;
      9)  logs_follow_container "consul-jwt-init" ;;
      10)  logs_follow_container "elasticsearch" ;;
      11) logs_follow_container "execute_migrate_all" ;;
      12)  logs_follow_container "filebeat" ;;
      13)  logs_follow_container "filebeat-setup" ;;
      14)  logs_follow_container "kc_postgres" ;;
      15)  logs_follow_container "keycloak" ;;
      16) logs_follow_container "kibana" ;;
      17) logs_follow_container "kibana-pass-init" ;;
      18) logs_follow_container "minio" ;;
      19) logs_follow_container "ollama" ;;
      20) logs_follow_container "om-elasticsearch" ;;
      21) logs_follow_container "openmetadata-ingestion" ;;
      22) logs_follow_container "mysql" ;;
      23) logs_follow_container "openmetadata-server" ;;
      24) logs_follow_container "osss_postgres" ;;
      25) logs_follow_container "postgres-airflow" ;;
      26) logs_follow_container "postgres-superset" ;;
      27) logs_follow_container "qdrant" ;;
      28) logs_follow_container "redis" ;;
      29) logs_follow_container "shared-vol-init" ;;
      30) logs_follow_container "superset" ;;
      31) logs_follow_container "superset-init" ;;
      32) logs_follow_container "superset_redis" ;;
      33) logs_follow_container "trino" ;;
      34) logs_follow_container "vault" ;;
      35) logs_follow_container "vault-oidc-setup" ;;
      36) logs_follow_container "vault-seed" ;;
      37) logs_follow_container "web" ;;
      38) logs_follow_container "chat-ui" ;;
      39) logs_follow_container "rasa-mentor" ;;
      q|Q|b|B) return 0 ;;
      *) echo "Unknown choice: ${choice}" ;;
    esac
  done
}


down_profiles_menu() {
  while true; do
    echo
    echo "==============================================="
    echo " Utilities"
    echo "==============================================="
    echo " 1) Destroy profile 'keycloak'"
    echo " 2) Destroy profile 'app'"
    echo " 3) Destroy profile 'web-app'"
    echo " 4) Destroy profile 'elastic'"
    echo " 5) Destroy profile 'vault'"
    echo " 6) Destroy profile 'consul'"
    echo " 7) Destroy profile 'trino'"
    echo " 8) Destroy profile 'airflow'"
    echo "9) Destroy profile 'superset'"
    echo "10) Destroy profile 'openmetadata'"
    echo "11) Destroy profile 'ai'"
    echo "  q) Back"
    echo "-----------------------------------------------"
    read -rp "Select an option: " choice || return 0
    case "$choice" in
      1)
        # Destroy keycloak'
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="keycloak"
          PROJECT="osss-keycloak"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"   # set to "" if you want to keep volumes

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES
        '

        prompt_return
        ;;
      2)
        # Destroy app'
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="app"
          PROJECT="osss-app"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"   # set to "" if you want to keep volumes

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES
        '
        prompt_return
        ;;
      3)
        # Destroy web-app'
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="web-app"
          PROJECT="osss-web-app"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"   # set to "" if you want to keep volumes

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES
        '
        prompt_return
        ;;
      4)
        # Destroy elastic
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="elastic"
          PROJECT="osss-elastic"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"   # set to "" if you want to keep volumes

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES
        '

        prompt_return
        ;;
      5)
        # Destroy vault'
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="vault"
          PROJECT="osss-vault"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"   # set to "" if you want to keep volumes

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES
        '
        prompt_return
        ;;
      6)
        # Destroy consol'
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="consul"
          PROJECT="osss-consul"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"   # set to "" if you want to keep volumes

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES
        '
        prompt_return
        ;;
      7)
        # Destroy trino'
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="trino"
          PROJECT="osss-trino"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"   # set to "" if you want to keep volumes

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES
        '
        prompt_return
        ;;
      8)
        # Destroy airflow'
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="airflow"
          PROJECT="osss-airflow"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"   # set to "" if you want to keep volumes

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES
        '

        prompt_return
        ;;
      9)
        # Destroy superset'
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="superset"
          PROJECT="osss-superset"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"   # set to "" if you want to keep volumes

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES
        '
        prompt_return
        ;;
      10)
        # Destroy openmetadata'
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="openmetadata"
          PROJECT="osss-openmetadata"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"   # set to "" if you want to keep volumes

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES
        '
        prompt_return
        ;;
      11)
        # Destroy ai
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/destroy-profile.sh"
          PROFILE="ai"
          PROJECT="osss-ai"
          FILE="/work/docker-compose.yml"
          REMOVE_VOLUMES="--volumes"

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          [ -f "$FILE" ]   || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }
          chmod +x "$SCRIPT" || true

          echo "▶ Running: $SCRIPT --profile $PROFILE --project $PROJECT --file $FILE $REMOVE_VOLUMES"
          # Force the project name for every compose operation in the script
          export COMPOSE_PROJECT_NAME="$PROJECT"

          "$SCRIPT" --profile "$PROFILE" --project "$PROJECT" --file "$FILE" $REMOVE_VOLUMES

          echo "— post-clean check for stragglers —"
          # If any service containers lack the compose project label, kill them explicitly.
          for name in chat-ui dvc ai-postgres ai-redis minio qdrant ollama; do
            if sudo podman ps -a --format "{{.Names}}" | grep -qx "$name"; then
              # Remove only if container is NOT labeled with our compose project
              lbl="$(sudo podman inspect --format "{{ index .Config.Labels \"com.docker.compose.project\"}}" "$name" 2>/dev/null || true)"
              plbl="$(sudo podman inspect --format "{{ index .Config.Labels \"io.podman.compose.project\"}}" "$name" 2>/dev/null || true)"
              if [ "$lbl" != "$PROJECT" ] && [ "$plbl" != "$PROJECT" ]; then
                echo "⚠️  Removing stray container not owned by project ($name)"
                sudo podman rm -f "$name" || true
              fi
            fi
          done

          # Also nuke the compose pod if it’s around
          sudo podman pod rm -f "$PROJECT" 2>/dev/null || true
        '

        prompt_return
        ;;
      q|Q|b|B) return 0 ;;
      *) echo "Unknown choice: ${choice}" ;;
    esac
  done
}


utilities_menu() {
  while true; do
    echo
    echo "==============================================="
    echo " Utilities"
    echo "==============================================="
    echo " 1) Show Podman version inside the VM"
    echo " 2) Show Podman GraphRoot inside the VM"
    echo " 3) Install podman-compose inside the VM"
    echo " 4) Stop podman machine default"
    echo " 5) Remove podman machine default"
    echo " 6) Connect to default machine"
    echo " 7) List running containers in VM"
    echo " 8) List images"
    echo " 9) Delete specific rootful Podman image"
    echo " 10) Diagnose container restart"
    echo "  q) Back"
    echo "-----------------------------------------------"
    read -rp "Select an option: " choice || return 0
    case "$choice" in
      1)
        # Pick an active VM if available, otherwise use 'default'
        local vm
        vm="$(podman machine active 2>/dev/null || echo default)"
        echo "▶️ Podman version in VM '${vm}':"
        podman machine ssh "$vm" -- bash -lc 'podman --version || podman version' || \
          echo "⚠️ Could not get Podman version inside VM '${vm}'."
        ;;
      2)
        local vm
        vm="$(podman machine active 2>/dev/null || echo default)"
        echo "▶️ Podman GraphRoot in VM '${vm}':"
        podman machine ssh "$vm" -- bash -lc 'podman info --format "{{ .Store.GraphRoot }}"' || \
          echo "⚠️ Could not get GraphRoot inside VM '${vm}'."
        ;;
      3)
        local vm
        vm="$(podman machine active 2>/dev/null || echo default)"
        echo "▶️ Installing podman-compose inside VM '${vm}' (if missing)…"
        podman machine ssh "$vm" -- bash -lc '
          set -euo pipefail
          if ! command -v podman-compose >/dev/null 2>&1; then
            sudo dnf -y install podman-compose || sudo apt-get update && sudo apt-get -y install podman-compose
          else
            echo "podman-compose already installed."
          fi
        ' || echo "⚠️ Install may have failed inside VM '${vm}'."
        ;;
      4)
        podman_vm_stop
        ;;
      5)
        podman_vm_destroy
        ;;
      6)
        # Attach a shell to the active/default VM
        local vm
        vm="$(podman machine active 2>/dev/null || echo default)"
        echo "🔌 Connecting to VM '${vm}'… (exit to return)"
        podman machine ssh "$vm"
        ;;
      7)
        # List running containers in the VM (both rootless + rootful)
        vm="$(podman machine active 2>/dev/null || echo default)"
        echo "📦 Running containers in VM '${vm}':"
        podman machine ssh "$vm" 'bash -s' <<'REMOTE'
set -euo pipefail

echo "── rootless (podman ps) ─────────────────────────────────"
if podman ps --format '{{.ID}}' >/dev/null 2>&1; then
  podman ps --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' || true
else
  podman ps || true
fi

echo
echo "── rootful (sudo podman ps) ─────────────────────────────"
if sudo podman ps --format '{{.ID}}' >/dev/null 2>&1; then
  sudo podman ps --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' || true
else
  sudo podman ps || true
fi

echo
echo "Tip: your compose runs with 'sudo podman', so containers will appear in the rootful section."
REMOTE
        ;;
      8)
        echo "📸 Rootful Podman images in VM 'default':"
        podman machine ssh default -- sudo podman images || echo "❌ Unable to list images."
        prompt_return
        ;;
      9)
        echo "🗑️ Delete a specific rootful Podman image in VM 'default'"
        echo "📸 Current images:"
        podman machine ssh default -- sudo podman images || true
        echo ""
        read -rp "Enter IMAGE ID or NAME:TAG to delete (or blank to cancel): " img
        if [[ -z "$img" ]]; then
          echo "❌ Cancelled."
        else
          echo "⚠️ Deleting image '$img'..."
          podman machine ssh default -- sudo podman rmi -f "$img" && echo "✅ Image '$img' deleted." || echo "❌ Failed to delete image '$img'."
        fi
        prompt_return
        ;;
      10)
        # Diagnose a container that keeps restarting
        read -rp "Container name to diagnose (e.g., chat-ui): " cname
        [[ -z "$cname" ]] && { echo "❌ Cancelled."; continue; }
        compose_diagnose_restart "$cname"
        ;;
      q|Q|b|B)
        return 0
        ;;
      *)
        echo "Unknown choice: ${choice}"
        ;;
    esac
  done
}

# prompt_rebuild
# - Interactively ask whether to rebuild the Docker image (default: No).
# - Sets REBUILD=1 if user answers yes; otherwise REBUILD=0.
# - Returns 0 when rebuilding, 1 when skipping.
prompt_rebuild() {
  # If non-interactive, default to No.
  if ! [ -t 0 ] && ! [ -t 1 ]; then
    REBUILD=0
    echo "No TTY detected; defaulting to No (skip rebuild)."
    return 1
  fi

  local ans
  # Prefer /dev/tty when available so it works even if stdin is redirected.
  if [ -r /dev/tty ]; then
    read -r -p "Rebuild Docker image? [y/N] " ans </dev/tty
  else
    read -r -p "Rebuild Docker image? [y/N] " ans
  fi

  case "$ans" in
    [Yy]|[Yy][Ee][Ss])
      REBUILD=1
      echo "Selected: Yes (rebuild)."
      return 0
      ;;
    ""|[Nn]|[Nn][Oo])
      REBUILD=0
      echo "Selected: No (skip rebuild)."
      return 1
      ;;
    *)
      REBUILD=0
      echo "Selected: No (unrecognized input: '$ans')."
      return 1
      ;;
  esac
}


menu() {
  ensure_hosts_keycloak

  while true; do
    echo
    echo "==============================================="
    echo " Menu (project: ${COMPOSE_PROJECT_NAME})"
    echo " File: ${COMPOSE_FILE}   Profile: ${PROFILE}"
    echo "==============================================="
    echo " 1) Start profile 'keycloak' (!!! MUST BE DEPLOYED FIRST !!!)"
    echo " 2) Start profile 'app' (keycloak must be up)"
    echo " 3) Start profile 'web-app' (keycloak must be up)"
    echo " 4) Start profile 'elastic'"
    echo " 5) Start profile 'vault' (keycloak must be up)"
    echo " 6) Start profile 'consul'"
    echo " 7) Start profile 'trino' (keycloak must be up)"
    echo " 8) Start profile 'airflow' (keycloak must be up)"
    echo "9) Start profile 'superset' (keycloak must be up)"
    echo "10) Start profile 'openmetadata' (keycloak should be up)"
    echo "11) Start profile 'ai' (keycloak should be up)"
    echo "12) Down a profile (remove-orphans, volumes)"
    echo "13) Down ALL (remove-orphans, volumes)"
    echo "14) Show status"
    echo "15) Logs submenu"
    echo "16) Create Trino server certificate + keystore"
    echo "17) Create Keycloak server certificate"
    echo "18) Reset Podman machine (wipe & restart)"
    echo "19) Stop Podman VM"
    echo "20) Destroy Podman VM"
    echo "21) Run tests with Keycloak CA bundle"
    echo "22) Utilities"
    echo "23) Create Trino truststore"
    echo "24) Create Openmetadata truststore"
    echo "  q) Quit"
    echo "-----------------------------------------------"
    read -rp "Select an option: " ans || exit 0
    case "${ans}" in
      1)
        # Deploy keycloak
        if prompt_rebuild; then
          REBUILD=1
        else
          REBUILD=0
        fi

        podman machine ssh default -- bash -lc "
          export REBUILD=$REBUILD;
          set -euo pipefail;
          cd /work || { echo '❌ Path not visible inside VM: /work'; exit 1; };

          SCRIPT='/work/scripts/deploy-profile.sh';
          PROFILE='keycloak';
          PROJECT='osss-keycloak';
          REBUILD=\$REBUILD;
          FILE='/work/docker-compose.yml';

          echo '▶ Running:' \"\$SCRIPT\" \"\$PROFILE\" -p \"\$PROJECT\" -f \"\$FILE\" '(REBUILD='\$REBUILD')'; \
          \"\$SCRIPT\" \"\$PROFILE\" -p \"\$PROJECT\" -f \"\$FILE\"
        "
        prompt_return

        ;;
      2)
        # Deploy app
        if prompt_rebuild; then
          REBUILD=1
        else
          REBUILD=0
        fi

        podman machine ssh default -- bash -lc "
          set -euo pipefail;
          export REBUILD=$REBUILD;
          echo \"Rebuild is: \${REBUILD}\"

          cd /work || { echo '❌ Path not visible inside VM: /work'; exit 1; };

          SCRIPT='/work/scripts/deploy-profile.sh';
          PROFILE='app';
          PROJECT='osss-app';
          REBUILD=\$REBUILD;
          FILE='/work/docker-compose.yml';

          echo '▶ Running:' \"\$SCRIPT\" \"\$PROFILE\" -p \"\$PROJECT\" -f \"\$FILE\" '(REBUILD='\$REBUILD')'; \
          \"\$SCRIPT\" \"\$PROFILE\" -p \"\$PROJECT\" -f \"\$FILE\"
        "
        prompt_return

        ;;
      3)
        # Deploy webapp
        if prompt_rebuild; then
          REBUILD=1
        else
          REBUILD=0
        fi

        podman machine ssh default -- bash -lc "
          set -euo pipefail;
          export REBUILD=$REBUILD;
          echo \"Rebuild is: \${REBUILD}\"

          cd /work || { echo '❌ Path not visible inside VM: /work'; exit 1; };

          SCRIPT='/work/scripts/deploy-profile.sh';
          PROFILE='web-app';
          PROJECT='osss-web-app';
          REBUILD=\$REBUILD;
          FILE='/work/docker-compose.yml';

          echo '▶ Running:' \"\$SCRIPT\" \"\$PROFILE\" -p \"\$PROJECT\" -f \"\$FILE\" '(REBUILD='\$REBUILD')'; \
          \"\$SCRIPT\" \"\$PROFILE\" -p \"\$PROJECT\" -f \"\$FILE\"
        "
        prompt_return

        ;;
      4)
        # Deploy elastic (VM-local, same pattern as Keycloak)
        podman machine ssh default -- bash -lc '
          set -euo pipefail

          # Project path inside the VM (your 9p mount)
          HOST_PROJ="/work"

          PROJECT=osss-elastic
          PROFILE=elastic
          COMPOSE_FILE=docker-compose.yml

          ensure_regular_file() {
            local SRC="$1" DST="$2"
            [ -d "$DST" ] && rm -rf "$DST"
            if [ -f "$SRC" ]; then
              install -D -m0644 "$SRC" "$DST"
            else
              install -d -m0755 "$(dirname "$DST")"
              cat > "$DST" <<'"EOF_MIN_FBEAT"'
filebeat.inputs: []
output.console:
  pretty: true
EOF_MIN_FBEAT
              chmod 0644 "$DST"
            fi
          }

          verify_file() { local P="$1"; stat -c "%F %n" "$P" || ls -ld "$P"; echo "----"; head -n 20 "$P" || true; }

          # Make sure the Filebeat config exists inside the VM
          FBEAT_SRC="${HOST_PROJ}/config_files/filebeat/filebeat.podman.yml"
          FBEAT_DST="/var/home/core/OSSS/config_files/filebeat/filebeat.podman.yml"
          ensure_regular_file "$FBEAT_SRC" "$FBEAT_DST"
          verify_file "$FBEAT_DST"

          cd "$HOST_PROJ" || { echo "❌ Path not visible inside VM: $HOST_PROJ"; exit 1; }

          # Choose a rootful compose frontend
          export PODMAN_COMPOSE_PROVIDER=native
          if sudo -E podman compose version >/dev/null 2>&1; then
            pc="sudo -E PODMAN_COMPOSE_PROVIDER=native podman compose"
          elif command -v sudo podman-compose >/dev/null 2>&1; then
            pc="sudo -E podman-compose"   # fallback
          else
            echo "❌ Neither podman compose nor podman-compose installed" >&2; exit 1
          fi
          echo "▶️ Compose provider (rootful): $pc"

          # Ensure network (rootful)
          sudo podman network exists osss-net >/dev/null 2>&1 || sudo podman network create osss-net

          # Helpers (rootful inspection)
          cid_for() {
            local svc="$1"
            sudo podman ps -a \
              --filter label=io.podman.compose.project=$PROJECT \
              --filter label=com.docker.compose.project=$PROJECT \
              --filter label=io.podman.compose.service=$svc \
              --filter label=com.docker.compose.service=$svc \
              --format "{{.ID}}" | head -n1
          }

          wait_completed_ok() {
            local svc="$1"; local timeout="${2:-600}"; local start=$(date +%s)
            local cid status code
            echo "⏳ Waiting for one-shot '\''$svc'\'' to complete..."
            while :; do
              cid=$(cid_for "$svc" || true)
              if [ -n "$cid" ]; then
                status=$(sudo podman inspect -f "{{.State.Status}}" "$cid" 2>/dev/null || true)
                code=$(sudo podman inspect -f "{{.State.ExitCode}}" "$cid" 2>/dev/null || echo 1)
                if [ "$status" = "exited" ]; then
                  if [ "$code" = "0" ]; then
                    echo "✅ $svc exited 0 (success)"
                    break
                  else
                    echo "❌ $svc exited non-zero ($code). Recent logs:" >&2
                    sudo podman logs --tail=200 "$cid" || true
                    exit 1
                  fi
                fi
              fi
              if [ $(( $(date +%s) - start )) -ge "$timeout" ]; then
                echo "❌ Timeout waiting for '\''$svc'\'' to complete" >&2
                [ -n "$cid" ] && sudo podman logs --tail=200 "$cid" || true
                exit 1
              fi
              sleep 2
            done
          }

          wait_http_200_401() {
            local url="$1" timeout="${2:-300}" start=$(date +%s) code
            echo "⏳ Waiting for HTTP 200/401 from $url..."
            while :; do
              code=$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)
              if [ "$code" = "200" ] || [ "$code" = "401" ]; then
                echo "✅ $url responded $code"
                break
              fi
              if [ $(( $(date +%s) - start )) -ge "$timeout" ]; then
                echo "❌ Timeout waiting for $url (last code=$code)" >&2
                exit 1
              fi
              sleep 3
            done
          }

          echo "🚀 [elastic-start] Using compose file: $HOST_PROJ/$COMPOSE_FILE"

          # Bring up ES + Kibana (rootful)
          COMPOSE_PROJECT_NAME=$PROJECT $pc -f "$COMPOSE_FILE" --profile "$PROFILE" up -d \
            --force-recreate --remove-orphans elasticsearch kibana kibana-pass-init api-key-init shared-vol-init

          # Quick readiness checks (ES first, then Kibana)
          echo "⏳ Waiting for TCP localhost:9200..."
          timeout 300 bash -lc '\''while ! (echo > /dev/tcp/localhost/9200) 2>/dev/null; do sleep 2; done'\'' && echo "✅ TCP localhost:9200 is accepting connections"
          wait_http_200_401 "http://localhost:9200" 300

          echo "⏳ Waiting for TCP localhost:5601..."
          timeout 600 bash -lc '\''while ! (echo > /dev/tcp/localhost/5601) 2>/dev/null; do sleep 3; done'\'' || { echo "❌ Kibana port not open in time"; exit 1; }
          # Optional: give Kibana a breath to finish boot
          sleep 5

          # Run setup as a one-shot (rootful)
          COMPOSE_PROJECT_NAME=$PROJECT $pc -f "$COMPOSE_FILE" --profile "$PROFILE" up -d --no-deps --no-recreate filebeat-setup
          wait_completed_ok filebeat-setup 600

          # Start filebeat after setup completed OK (rootful)
          COMPOSE_PROJECT_NAME=$PROJECT $pc -f "$COMPOSE_FILE" --profile "$PROFILE" up -d --no-deps --no-recreate filebeat

          echo "📋 Active (rootful) containers:"
          sudo podman ps --filter label=io.podman.compose.project=$PROJECT --format "{{.Names}}\t{{.Status}}"
        '

        prompt_return
        ;;
      5)
        # Deploy vault
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/deploy-profile.sh"
          PROFILE="vault"
          PROJECT="osss-vault"
          FILE="/work/docker-compose.yml"

          [ -f "$SCRIPT" ] || { echo "❌ Not found: $SCRIPT"; ls -la /work/scripts || true; exit 1; }
          chmod +x "$SCRIPT" || true
          [ -f "$FILE" ] || { echo "❌ Not found: $FILE"; ls -la /work || true; exit 1; }

          echo "▶ Running: $SCRIPT $PROFILE -p $PROJECT -f $FILE"
          "$SCRIPT" "$PROFILE" -p "$PROJECT" -f "$FILE"
        '
        prompt_return

        ;;
      6)
        # Deploy consul
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/deploy-profile.sh"
          PROFILE="consul"
          PROJECT="osss-consul"
          FILE="/work/docker-compose.yml"

          echo "▶ Running: $SCRIPT $PROFILE -p $PROJECT -f $FILE"
          "$SCRIPT" "$PROFILE" -p "$PROJECT" -f "$FILE"
        '
        ;;
      7)
        # Deploy trino
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/deploy-profile.sh"
          PROFILE="trino"
          PROJECT="osss-trino"
          FILE="/work/docker-compose.yml"

          echo "▶ Running: $SCRIPT $PROFILE -p $PROJECT -f $FILE"
          "$SCRIPT" "$PROFILE" -p "$PROJECT" -f "$FILE"
        '
        ;;
      8)
        # Deploy airflow
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/deploy-profile.sh"
          PROFILE="airflow"
          PROJECT="osss-airflow"
          FILE="/work/docker-compose.yml"


          echo "▶ Running: $SCRIPT $PROFILE -p $PROJECT -f $FILE"
          "$SCRIPT" "$PROFILE" -p "$PROJECT" -f "$FILE"
        '

        ;;
      9)
        # Deploy superset
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/deploy-profile.sh"
          PROFILE="superset"
          PROJECT="osss-superset"
          FILE="/work/docker-compose.yml"

          echo "▶ Running: $SCRIPT $PROFILE -p $PROJECT -f $FILE"
          "$SCRIPT" "$PROFILE" -p "$PROJECT" -f "$FILE"
        '
        ;;
      10)
        # Deploy openmetadata
        podman machine ssh default -- bash -lc '
          set -euo pipefail
          cd /work || { echo "❌ Path not visible inside VM: /work"; exit 1; }

          SCRIPT="/work/scripts/deploy-profile.sh"
          PROFILE="openmetadata"
          PROJECT="osss-openmetadata"
          FILE="/work/docker-compose.yml"

          echo "▶ Running: $SCRIPT $PROFILE -p $PROJECT -f $FILE"
          "$SCRIPT" "$PROFILE" -p "$PROJECT" -f "$FILE"
        '
        ;;
      11)
                # Deploy ai (with optional rebuild + clean redeploy)
        PROFILE="ai"
        PROJECT="osss-ai"
        FILE="docker-compose.yml"
        SCRIPT="/work/scripts/deploy-profile.sh"

        # Host-side helper (used only in the first validation call where we use double quotes)
        VM_COMPOSE='sudo -E env PATH=/usr/sbin:/usr/bin:/usr/local/bin:$PATH CONTAINERS_COMPOSE_PROVIDER=podman-compose podman compose'

        # Rebuild prompt (host-side only; actual build happens in-VM)
        echo "🧱 Services in profile (${PROFILE}) that have build steps can be rebuilt before deploy."
        _nocache=""
        read -r -p "Rebuild images for profile '${PROFILE}' now? [y/N] " _rb || true
        if [[ "${_rb}" =~ ^[Yy]$ ]]; then
          read -r -p "Use --no-cache for the rebuild? [y/N] " _nc || true
          [[ "${_nc}" =~ ^[Yy]$ ]] && _nocache="--no-cache"
        else
          echo "⏭️  Skipping image rebuild."
        fi

        # Clean redeploy?
        _redeploy="0"
        read -r -p "Do a clean redeploy (down + scrub + up) for '${PROFILE}'? [y/N] " _rd || true
        [[ "${_rd}" =~ ^[Yy]$ ]] && _redeploy="1"

        # (A) Validate compose inside the VM (double-quoted so $VM_COMPOSE expands on host)
        podman machine ssh default -- bash -lc "
          set -euo pipefail
          cd /work
          echo \"+ $VM_COMPOSE -f docker-compose.yml --profile ai config (validation)\"
          $VM_COMPOSE -f docker-compose.yml --profile ai config >/dev/null
        "

        # (B) Optional clean redeploy (full scrub to avoid "proxy already running")
        if [[ "${_redeploy}" = "1" ]]; then
          podman machine ssh default 'bash -s' <<'VMSCRUB'
set -euo pipefail
cd /work

# Ensure compose provider is discoverable in this shell and via sudo
export PATH=/usr/sbin:/usr/bin:/usr/local/bin:$PATH
export CONTAINERS_COMPOSE_PROVIDER=podman-compose
COMPOSE='sudo -E env PATH=/usr/sbin:/usr/bin:/usr/local/bin:$PATH CONTAINERS_COMPOSE_PROVIDER=podman-compose podman compose'

echo "== down --remove-orphans --volumes =="
$COMPOSE -f docker-compose.yml --profile ai down --remove-orphans --volumes || true

echo "== kill stale port-forward proxies =="
sudo pkill -f rootlessport  || true
sudo pkill -f slirp4netns   || true
sudo pkill -f gvproxy       || true
sudo pkill -f pasta         || true
sudo pkill -f conmon        || true

echo "== rm named containers =="
sudo podman rm -f ollama qdrant minio ai-redis ai-postgres dvc chat-ui 2>/dev/null || true

echo "== rm pods (project + leftovers) =="
sudo podman pod rm -f osss-ai 2>/dev/null || true
sudo podman pod rm -fa 2>/dev/null || true

echo "== prune networks (ignore errors) =="
sudo podman network rm osss-ai_default 2>/dev/null || true
sudo podman network rm osss-net        2>/dev/null || true

echo "== recreate external network =="
sudo podman network create osss-net >/dev/null
VMSCRUB
        else
          # Ensure external network exists
          podman machine ssh default 'bash -s' <<'VMNET'
set -euo pipefail
cd /work
export PATH=/usr/sbin:/usr/bin:/usr/local/bin:$PATH
export CONTAINERS_COMPOSE_PROVIDER=podman-compose

if ! sudo podman network exists osss-net 2>/dev/null; then
  echo "🌐 Creating external network: osss-net"
  sudo podman network create osss-net >/dev/null
else
  echo "🌐 Network osss-net already exists"
fi
VMNET
        fi

        # (C) Build inside the VM (use wrapper; inject NOCACHE via env)
        echo "+ VM build ${_nocache:-"(cached)"}"
        podman machine ssh default "NOCACHE_FLAG=${_nocache}" 'bash -s' <<'VMBUILD'
set -euo pipefail
cd /work
export PATH=/usr/sbin:/usr/bin:/usr/local/bin:$PATH
export CONTAINERS_COMPOSE_PROVIDER=podman-compose
COMPOSE='sudo -E env PATH=/usr/sbin:/usr/bin:/usr/local/bin:$PATH CONTAINERS_COMPOSE_PROVIDER=podman-compose podman compose'

echo "+ $COMPOSE -f docker-compose.yml --profile ai build ${NOCACHE_FLAG}"
$COMPOSE -f docker-compose.yml --profile ai build ${NOCACHE_FLAG}
VMBUILD

        # (D) Bring up (force-recreate) with auto-heal for "proxy already running"
        podman machine ssh default "COMPOSE_PROJECT_NAME=${PROJECT}" 'bash -s' <<'VMUP'
set -euo pipefail
cd /work

export PATH=/usr/sbin:/usr/bin:/usr/local/bin:$PATH
export CONTAINERS_COMPOSE_PROVIDER=podman-compose
COMPOSE='sudo -E env PATH=/usr/sbin:/usr/bin:/usr/local/bin:$PATH CONTAINERS_COMPOSE_PROVIDER=podman-compose podman compose'

attempt_up() {
  echo "▶ Up: ${COMPOSE_PROJECT_NAME} profile ai (force-recreate)"
  env -u DOCKER_CONFIG -u DOCKER_AUTH_CONFIG \
    $COMPOSE -f docker-compose.yml --profile ai up -d --force-recreate
}

deep_scrub_ports() {
  echo "⚠️  Detected stale port proxy; performing deep scrub..."
  $COMPOSE -f docker-compose.yml --profile ai down --remove-orphans --volumes || true

  echo "— show who’s listening on our ports —"
  (command -v ss >/dev/null && \
    sudo ss -ltnp | grep -E ":11434|:6333|:9000|:9001|:6382|:5436|:3001" || true)

  echo "— kill known helpers (best-effort) —"
  sudo pkill -f rootlessport || true
  sudo pkill -f gvproxy      || true
  sudo pkill -f slirp4netns  || true
  sudo pkill -f pasta        || true
  sudo pkill -f conmon       || true

  echo "— purge runtime dirs —"
  sudo rm -rf /run/netavark/*           2>/dev/null || true
  sudo rm -rf /run/podman/*             2>/dev/null || true
  sudo rm -rf /run/libpod/*             2>/dev/null || true
  sudo rm -rf /run/user/*/libpod/tmp/*  2>/dev/null || true
  sudo rm -rf /run/user/*/podman/pasta* 2>/dev/null || true
  for d in /var/lib/containers/storage/overlay-containers/*/userdata; do
    [ -d "$d" ] && sudo rm -rf "$d"/rootlessport* "$d"/pasta* 2>/dev/null || true
  done

  echo "— restart podman services —"
  sudo systemctl restart podman.socket || true
  sudo systemctl restart podman        || true

  echo "— prune & recreate external network —"
  sudo podman network rm osss-net 2>/dev/null || true
  sudo podman network prune -f 2>/dev/null || true
  sudo podman network create osss-net >/dev/null

  echo "— sanity after scrub —"
  (command -v ss >/dev/null && \
    sudo ss -ltnp | grep -E ":11434|:6333|:9000|:9001|:6382|:5436|:3001" || true)
}

hard_reset_daemon() {
  echo "🧹 Hard reset of Podman runtime (no image wipe)"
  sudo systemctl stop podman podman.socket || true
  sudo pkill -9 -f "(conmon|rootlessport|gvproxy|slirp4netns|pasta|netavark)" || true
  sudo rm -rf /run/podman/* /run/libpod/* /run/netavark/* /run/containers/* 2>/dev/null || true
  sudo systemctl start podman.socket || true
  sudo systemctl start podman || true
  sudo podman network create osss-net >/dev/null 2>&1 || true
}

# First attempt
if attempt_up 2>up.err; then
  echo "✅ Up succeeded"
  exit 0
fi

if grep -qi "proxy already running" up.err; then
  echo "⛔ First up failed with proxy error:"
  cat up.err
  deep_scrub_ports

  echo "🔁 Retrying up after deep scrub..."
  rm -f up.err
  if attempt_up 2>up.err; then
    echo "✅ Up succeeded after deep scrub"
    exit 0
  fi

  echo "🧹 Hard reset of Podman runtime (no image wipe)"
  hard_reset_daemon

  echo "🔁 Final retry after hard reset…"
  rm -f up.err
  if attempt_up 2>up.err; then
    echo "✅ Up succeeded after hard reset"
    exit 0
  fi

  if grep -qi "proxy already running" up.err; then
    echo "🧪 Applying targeted host-network override for ollama (bypass port proxy)…"
    cat >/work/docker-compose.ollama-hostnet.yml <<'YAML'
services:
  ollama:
    network_mode: host
    networks: null   # ensure inherited networks are removed
    ports: []        # no port publishing when using host network
YAML
    echo "🔁 Retrying with override file (ollama on host network)…"
    $COMPOSE -f /work/docker-compose.yml -f /work/docker-compose.ollama-hostnet.yml --profile ai down --remove-orphans || true
    if $COMPOSE -f /work/docker-compose.yml -f /work/docker-compose.ollama-hostnet.yml --profile ai up -d --force-recreate; then
      echo "✅ Up succeeded with ollama host-network override"
      exit 0
    else
      echo "❌ Up failed even with host-network override:"
      cat up.err || true
      exit 125
    fi
  fi

  echo "❌ Up failed after hard reset (different error):"
  cat up.err
  exit 125
else
  echo "❌ Up failed (non-proxy error):"
  cat up.err
  exit 125
fi
VMUP

        echo "✅ Deploy complete for profile '${PROFILE}'."
        ;;

      12) down_profiles_menu ;;
      13) down_all ;;
      14) show_status; prompt_return ;;
      15) logs_menu ;;
      16) create_trino_cert ;;
      17) create_keycloak_cert ;;
      18) reset_podman_machine ;;
      19) podman_vm_stop ;;
      20) podman_vm_destroy ;;
      21)
        echo "▶️ Running pytest with OSSS Keycloak CA bundle..."
        export REQUESTS_CA_BUNDLE="$(pwd)/config_files/keycloak/secrets/ca/ca.crt"
        export OSSS_CA_BUNDLE="$REQUESTS_CA_BUNDLE"

        export OSSS_TEST_CA_BUNDLE=config_files/keycloak/secrets/keycloak/server.crt
        export REQUESTS_CA_BUNDLE=config_files/keycloak/secrets/keycloak/server.crt

        # make sure nothing forces container-only hostnames or HTTP defaults
        unset KEYCLOAK_BASE_URL

        # Run pytest but don't fail the script if tests fail
        PYTEST_RC=0
        pytest -q || PYTEST_RC=$?

        if [ "$PYTEST_RC" -ne 0 ]; then
          echo "⚠️  pytest failed (exit $PYTEST_RC), continuing…"
        fi
        prompt_return
        ;;
      22) utilities_menu ;;
      23)
        echo "🛠️  Building Trino truststore..."
        build_trino_truststore
        prompt_return
        ;;
      24)
        echo "🛠️  Building Openmetadata truststore..."
        create_openmetadata_truststore
        prompt_return
        ;;
      q|Q) echo "Bye!"; exit 0 ;;
      *)   echo "Unknown choice: ${ans}"; prompt_return ;;
    esac
  done
}


menu