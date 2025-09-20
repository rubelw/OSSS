#!/bin/sh
set -e

sleep 120  # Sleep to allow restart and import load

# 1) First check KC readiness endpoint
if ! curl -fsS http://keycloak:9000/health/ready >/dev/null; then
  exit 1
fi

# 2) Then check that the OSSS realm exists
if ! curl -fsS http://keycloak:8080/realms/OSSS/.well-known/openid-configuration >/dev/null; then
  exit 1
fi

exit 0
