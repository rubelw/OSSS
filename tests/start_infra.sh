#!/usr/bin/env bash
# -------------------------------------------------------------------------------------------------
# start_infra.sh
#
# Purpose
# -------
# Spin up the local test infrastructure (Keycloak + Postgres) using Docker Compose.
# This is intentionally minimal: it just starts the containers in the background.
# Readiness/health waiting is handled elsewhere (e.g., in tests/conftest.py).
#
# How it works
# ------------
# - Invokes `docker compose` with the compose file `keycloak_postgres.yaml`.
# - The `-d` flag starts services in detached mode (returns control immediately).
#
# Assumptions / Paths
# -------------------
# - This script assumes your current working directory contains the file:
#       keycloak_postgres.yaml
#   If your compose file lives under tests/, you can run:
#       (cd tests && ./start_infra.sh)
#
# Requirements
# ------------
# - Docker Engine running locally.
# - Docker Compose V2 CLI available as `docker compose` (not the old `docker-compose`).
#
# What this script does *not* do
# ------------------------------
# - It does not wait for services to become healthy.
#   The pytest session (via conftest.py) typically polls the OIDC discovery URL
#   until Keycloak is ready.
# - It does not validate whether Docker is installed or running.
#
# Exit behavior
# -------------
# - Returns the exit code from `docker compose ... up`. A non-zero exit code usually
#   means Docker isn’t running, the compose file path is wrong, or a service failed
#   to start.
# -------------------------------------------------------------------------------------------------

docker compose -f keycloak_postgres.yaml up -d
