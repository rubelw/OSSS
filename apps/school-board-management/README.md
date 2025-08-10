# OSSS Starter (FastAPI + React + Keycloak) — with Policy Redlines

An opinionated starter kit to prototype an open-source board management suite (agendas/packets, policies, votes, public portal) with **Keycloak SSO** and **policy redline diffs**.

## Quickstart
```bash
cp .env.example .env




# use the URI from your connection list
export CONTAINER_HOST='ssh://root@127.0.0.1:65299/run/podman/podman.sock'
# ssh key path from your list
export CONTAINER_SSHKEY="$HOME/.local/share/containers/podman/machine/machine"

# (help some versions)
export PODMAN_HOST="$CONTAINER_HOST"
export PODMAN_SSHKEY="$CONTAINER_SSHKEY"

# avoid Docker leaking in
unset DOCKER_HOST DOCKER_CONTEXT

podman info
podman-compose up --build


# Web: http://localhost:5173
# API: http://localhost:8000/docs
# Keycloak: http://localhost:8081  (admin/admin)
```

### Keycloak setup (dev)
- Realm: `oss`
- Client (Public SPA): `osss-web`
  - Redirect URIs: `http://localhost:5173/*`
  - Web origins: `http://localhost:5173`
- (Optional) Create roles `ADMIN`, `CLERK`, `MEMBER`, `PUBLIC`

**Note:** Backend checks tokens against `KEYCLOAK_ISSUER` and `KEYCLOAK_AUDIENCE` (defaults to `osss-web` for simplicity).

### Redline endpoint
`GET /policies/{id}/diff?from_id={v1}&to_id={v2}` returns HTML showing insertions/deletions.
