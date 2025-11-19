# Open Source School Software (OSSS)

**Open Source School Software (OSSS)** is an **open source school software** platform—a modern **K‑12 Student Information System (SIS)** built with **FastAPI**, **Keycloak**, and **SQLAlchemy**. OSSS focuses on **student records**, **governance & workflows**, and core SIS features (attendance, scheduling, staff & family access), designed for school districts that want a transparent, extensible stack.

OSSS ships as a developer‑friendly API with clean domain models and authentication via OpenID Connect (Keycloak). It’s designed to be easy to deploy on PostgreSQL and to extend with React/Next.js front ends.

!!! warning "Project status: active development"
    **OSSS is still being developed.** Community input and assistance are very welcome!
    - Share feedback and ideas via issues or discussions.
    - Open PRs for bug fixes and small improvements.
    - See [Contributing](#contributing) for guidelines.


> This `index.md` documents the repository at commit **e7c3fcf69557527d1c09b9d47096fac63c0af246**.

---

## Why This Is Important

When Artificial General Intelligence (AGI) starts to emerge—potentially by 2030—districts will need to adjust governance, safety filters, and curricula rapidly. That kind of agility is exactly what community-maintained, open-source software delivers—without waiting on a vendor roadmap. Today, many incumbent systems are tied to legacy architectures and slow release cycles. While AI is already reshaping mainstream apps, most school platforms haven’t meaningfully evolved to leverage it.

I’m building the next generation of school software as an open, participatory project. Administrators, staff, students, and families will be able to propose enhancements, contribute code, and ship improvements together—so the platform keeps pace with classroom needs and policy changes.

---

## What is in this repo?

- **Multiple apps and shared packages** in a single monorepo.
- **Backend (FastAPI/Python)** under `src/OSSS`.
- **Frontend (Next.js/TypeScript)** under `src/osss-web`.
- **Infrastructure & tooling**: Docker/Compose, K8s manifests, scripts, and CI.
- **Documentation** generated with **MkDocs**, output to `./documentation/`.

> The repository emphasizes openness (export-friendly), modularity, and operational sanity (containers, IaC, observability).

---

## Repository layout (high level)

```
.
├─ src/
│  ├─ OSSS/         # Python backend (FastAPI app, domain, services)
│  └─ osss-web/     # Next.js frontend (App Router, NextAuth, Keycloak integration)
├─ data_model/      # Database schema / migrations helpers
├─ docker/          # Docker/Compose files (local dev)
├─ k8s/             # Kubernetes manifests (optional)
├─ tests/           # Unit/integration tests
├─ documentation/   # Built MkDocs site (HTML output)
├─ docs/            # MkDocs content & auto-generated API docs
└─ scripts/         # Developer scripts & automation
```

> Exact paths may evolve; check app‑specific READMEs for authoritative details.

---

## Apps catalog (starter)

| App | Path | Status | Tech | What it does |
|---|---|---|---|---|
| **School Board Management** | `apps/school-board-management/` | MVP | React/TypeScript, FastAPI/Python, Postgres | Agendas, packets, votes, policies, minutes, public portal |
| **Student Information System (template)** | `apps/student-information-system/` | Template | (choose) | Enrollment, attendance, grades, transcripts |
| **Facilities Booking (template)** | `apps/facilities-booking/` | Template | (choose) | Room/field scheduling, approvals |
| **Communications Portal (template)** | `apps/communications-portal/` | Template | (choose) | Posts, alerts, newsletters, translation workflows |

> Use the template as a starting point when adding a new app to the monorepo.

---

## Getting started (local development)

### Prerequisites
- Git, Docker (or Podman), Docker Compose
- Node.js LTS (for the web UI), Python 3.10+ (for FastAPI) — per app stack

### Quick start
```bash
# clone
git clone https://github.com/rubelw/OSSS.git
cd OSSS

# (optional) copy environment examples
cp .env.example .env || true

# create a venv in a folder named .venv (inside your project)
python3 -m venv .venv
source .venv/bin/activate

# build + run local stack (database, API, web)
./start_osss.sh

# to run the cli
osss <TAB>

# Keycloak http://localhost:8080 with username 'a2a' and password 'a2a'
# FastApi  http://localhost:8081/docs# username 'activities_director@osss.local' and password 'password'
# Web: http://localhost:3000 username 'activities_director@osss.local' and password 'password'
```

Visit the app-specific README(s) for service URLs (e.g. API docs at `/docs`, web at `http://localhost:3000` for Next.js or `5173` for Vite).

---

[![Web UI preview](img/web_view.png)](img/web_view.png)


## Frontend (Next.js) highlights

- **App Router** with `app/` directory and segment‑scoped `layout.tsx`, `page.tsx`, and API routes.
- **Authentication with NextAuth (Auth.js)** and **Keycloak** provider; JWT sessions by default.
- **Edge/Node split**: Edge middleware for light auth checks; Node runtime for Redis‑backed storage.
- **UI components** under `components/`, shared utilities under `lib/` and types in `types/`.

> See `src/osss-web/` for code and detailed READMEs.

---

## Backend (FastAPI) highlights

- **Python 3.10+ FastAPI service** with typed routers, Pydantic models, and OpenAPI docs.
- **Auth integration** (Keycloak/SSO ready), database setup, and migration tooling (Alembic).
- **Testing** via `pytest`, configuration via `pyproject.toml`/`setup.cfg`.

> See `src/OSSS/` and the app‑specific README for endpoints and dev commands.

---

## Documentation (MkDocs)

We build docs to `./documentation/` using **MkDocs Material** and a mix of generated API references:

- **Frontend API (TypeScript)** via TypeDoc → Markdown placed in `docs/api/web/`.
- **Backend API (Python)** via mkdocstrings (`::: OSSS`) rendered from `src/OSSS`.
- Hand‑written guides live in `docs/` (e.g., `docs/frontend/overview.md`, `docs/backend/overview.md`).

### Common commands
```bash
# Generate TypeScript API pages
npm run docs:typedoc

# Serve MkDocs locally
mkdocs serve -a 127.0.0.1:8000

# Build static site to ./documentation/
mkdocs build --clean
```

---

## Quality, Security & Compliance

- **Accessibility**: target WCAG 2.2 AA for public pages and PDFs.
- **Security**: OWASP ASVS‑inspired checklists; SAST/DAST in CI; dependency scanning.
- **Privacy**: least‑privilege, data minimization, export tooling for records requests.
- **Observability**: structured logs, traces, metrics.

---

## Demo

![OSSS Demo](demo.gif)

## Contributing

1. Create a feature branch: `feat/<area>-<short-desc>`  
2. Use Conventional Commits (`feat:`, `fix:`, `docs:` …)  
3. Add/update tests and docs  
4. Open a PR with a clear description and screenshots when helpful

We use ADRs (Architecture Decision Records). New decisions go under `docs/adrs/`.

---

## License

This repository uses **Apache‑2.0** by default. See `LICENSE` at the repo root.  
Third‑party notices are in `THIRD_PARTY_NOTICES.md`.

---

## Links

- Source: https://github.com/rubelw/OSSS  
- Commit documented here: e7c3fcf69557527d1c09b9d47096fac63c0af246
