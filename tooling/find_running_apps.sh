#!/usr/bin/env bash
# check_ports.sh
# Finds apps running on ports 8081, 8080, or 3000

PORTS=(8081 8080 3000)

echo "Checking ports: ${PORTS[*]}"

for PORT in "${PORTS[@]}"; do
  echo "---- Port $PORT ----"
  # lsof is often installed; fall back to netstat/ss if not
  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"$PORT" -sTCP:LISTEN -n -P
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnp | grep ":$PORT"
  else
    netstat -tulnp 2>/dev/null | grep ":$PORT"
  fi
  echo
done
