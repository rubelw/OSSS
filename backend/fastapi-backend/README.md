# FastAPI + Postgres + Keycloak (Podman)

## Quick start (podman-compose)
```bash
# 1) Create your local env from the example:
cp .env.example .env

# 2) Boot everything:
podman-compose up --build

# API:      http://localhost:8000/docs  (Authorize → Keycloak)
# Keycloak: http://localhost:8080
```

## Cleanup
```bash
podman stop -a || true
podman rm -fa
podman pod rm -fa
podman volume rm -a -f
```
