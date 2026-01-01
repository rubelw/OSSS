# OSSS Docker Configuration & Images

The `docker/` directory defines how OSSS components are containerized for **local development, CI automation, and production deployments**.  
This README provides an expanded overview of each Dockerfile, how images are structured, and how they interact with other parts of the OSSS platform.

---

## 📂 Directory Structure

```
docker/
├── backend.Dockerfile         # OSSS FastAPI backend
├── web.Dockerfile             # Next.js web application (osss-web)
├── agent.Dockerfile           # A2A / orchestration agents (if enabled)
├── keycloak.Dockerfile        # Optional Keycloak customization
├── postgres.Dockerfile        # Custom Postgres image (extensions, init scripts)
├── consul.Dockerfile          # Consul customization (optional)
└── README.md                  # This file
```

> File names may vary slightly depending on branch/version — check your local tree to confirm.

---

## 🐳 Building Images

Each Dockerfile can be built independently, or via `docker-compose`.

### Backend API

```bash
docker build -f docker/backend.Dockerfile -t osss-backend .
```

### Web Application

```bash
docker build -f docker/web.Dockerfile -t osss-web .
```

### Agent Service

```bash
docker build -f docker/agent.Dockerfile -t osss-agent .
```

---

## ⚙️ Docker Compose Integration

Although Dockerfiles live here, **`docker-compose.yml` is in the repository root**.

To build and run everything together:

```bash
docker compose up --build
# or
docker-compose up --build
```

This spins up components such as:
- **Postgres**
- **Keycloak**
- **Backend API**
- **Web frontend**
- **Consul** *(optional depending on branch)*

---

## 🔌 Networking & Ports

Default ports (may change if proxied):

| Service | Port | Notes |
|---------|------|-------|
| Backend API | `8081` | `/openapi.json`, `/api/*`, `/healthz` |
| Web frontend | `3000` | Next.js app; proxies to backend in dev |
| Postgres | `5432` | Initial DB load via data model + migrations |
| Keycloak | `8080` | Identity / auth provider |
| Consul | `8500` | KV storage / service discovery (optional) |

---

## 🔑 Authentication & Environment Variables

**Backend:**
```
KEYCLOAK_BASE_URL=http://keycloak:8080
KEYCLOAK_REALM=OSSS
KEYCLOAK_AUDIENCE=osss-backend
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/osss
```

**Web app:**
```
NEXTAUTH_URL=http://localhost:3000
KEYCLOAK_ISSUER=http://keycloak:8080/realms/OSSS
WEB_KEYCLOAK_CLIENT_ID=osss-web
```

> In production, move secrets into Kubernetes `Secrets` or Vault — **do not bake secrets into images**.

---

## 🧪 Local Development Workflow

Recommended pattern:

```bash
# ensure DB + Keycloak + dependencies are running
docker compose up -d postgres keycloak consul

# start backend live reload from source
uvicorn OSSS.main:app --reload --port 8081

# start frontend live reload
npm run dev --prefix src/osss-web
```

This gives fast iteration **without rebuilding images**.

---

## 🚀 Production Build & Deploy Strategy

| Step | Responsibility |
|------|---------------|
| Build images | CI (GitHub Actions) |
| Push to registry | `ghcr.io/rubelw/OSSS/*` (recommended) |
| Deploy | Kubernetes / Nomad / ECS |
| Service mesh / proxy | Envoy / Traefik / NGINX |
| Storage | Postgres RDS / CloudSQL / Aurora |

**Recommended production practice**:
- keep `backend.Dockerfile` minimal (deps only)
- run migrations externally (`alembic upgrade head`)
- use reverse proxy termination to simplify TLS

---

## 🧱 Image Design Philosophy

| Principle | Explanation |
|----------|-------------|
| **Stateless images** | All writable data must be external (DB, object store) |
| **Multi-stage builds** | Reduce size and improve caching |
| **Non-root runtime users** | Required for hardened deployments |
| **Minimal base image** | `python:slim`, `node:alpine`, `distroless` for final stage |

---

## 🗺️ Related Documentation

| File | Purpose |
|------|---------|
| `/docker-compose.yml` | Infra + services orchestration |
| `/docs/backend/docker-compose.md` | Auto-generated docs for containers |
| `/data_model/` | Database schema + structured init data |
| `/config_files/` | ML components, policies, logging configs |
| `/consul_data/` | Optional KV bootstrap |

---

## ❓ Troubleshooting

| Issue | Fix |
|-------|----|
| Image rebuilds are slow | Enable build cache volume (`--mount=type=cache`) |
| Keycloak won't validate tokens | Check `KEYCLOAK_ISSUER` and time sync |
| DB init fails | Ensure migrations run once; remove stale volume |
| Next.js API conflicts | Avoid wildcard rewrite `/api/*` in production |

---

## 👥 Maintainers

| Name | Role |
|------|-----|
| @rubelw | Core maintainer |
| OSSS contributors | PRs welcome |

---

## 📝 License

See [LICENSE](../LICENSE) in the repository root.

---

If you'd like, I can now:
- auto-generate this README from code,
- link each image to CI build status,
- or export a version per git commit.

Just tell me! 💪
