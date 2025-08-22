#!/usr/bin/env bash
# -------------------------------------------------------------------------------------------------
# stop_infra.sh
#
# Purpose
# -------
# Tear down the local test infrastructure (Keycloak + Postgres) that was started
# via Docker Compose. This stops and removes the containers and their default
# network so you can get a clean slate for the next test run.
#
# How it works
# ------------
# - Invokes `docker compose` with the compose file `keycloak_postgres.yaml`.
# - The `down` command stops running containers and removes them, along with the
#   default network created for this compose project.
#
# Assumptions / Paths
# -------------------
# - This script assumes the file `keycloak_postgres.yaml` is in the current dir.
#   If your compose file lives in `tests/`, run the script from there:
#       (cd tests && ./stop_infra.sh)
#
# Requirements
# ------------
# - Docker Engine running locally.
# - Docker Compose V2 CLI available as `docker compose` (not the legacy `docker-compose`).
#
# What this script does *not* do (by default)
# -------------------------------------------
# - It does **not** remove named volumes (so your Postgres data persists).
# - It does **not** remove images.
# - It does **not** prune networks that aren’t part of this compose project.
#
# Optional, more aggressive cleanup
# ---------------------------------
# If you want a truly clean environment (e.g., wipe DB data), you can use:
#   docker compose -f keycloak_postgres.yaml down --volumes --remove-orphans --rmi local
# Flags explained:
#   --volumes         : remove named volumes declared in the compose file (data loss!)
#   --remove-orphans  : remove containers for services not defined in the compose file
#   --rmi local       : remove images built by `docker compose build` (keeps pulled images)
#
# Exit behavior
# -------------
# - Exits with `docker compose`’s status code. Non-zero usually means Docker isn’t
#   running, the compose file path is wrong, or a container failed to stop.
# -------------------------------------------------------------------------------------------------

docker compose -f ../docker-compose.yml down

# Uncomment for destructive cleanup (use with caution):
# docker compose -f keycloak_postgres.yaml down --volumes --remove-orphans --rmi local
