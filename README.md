# (Currently in Development) Open Source School Software

A community-driven, modular suite of applications for K‑12 districts. This repo is a **polyglot monorepo** that hosts multiple apps (each independently deployable) plus shared packages and infra. Use the provided templates to spin up new apps quickly.

> **Highlight:** This repository includes an application called **School Board Management Software** (agendas, packets, policies, minutes, votes, and a public portal). See below for details.

---

## Contents

* [Goals](#goals)
* [Repository Layout](#repository-layout)
* [App Catalog](#app-catalog)
* [Getting Started (Dev)](#getting-started-dev)
* [App Template](#app-template)
* [School Board Management Software](#school-board-management-software)
* [Quality, Security & Compliance](#quality-security--compliance)
* [Contributing](#contributing)
* [Releases & Versioning](#releases--versioning)
* [License](#license)
* [Acknowledgements](#acknowledgements)

---

## Goals

* **Open standards first:** accessible, interoperable, export-friendly.
* **District reality:** support public meetings/open records, records retention, FERPA‑aware data handling.
* **Composable:** each app should be useful alone, but better together via shared packages.
* **Operationally sane:** containerized, IaC‑ready, observable.

---

## Repository Layout

```
open-source-school-software/
├─ apps/
│  ├─ school-board-management/          # featured app (see below)
│  ├─ student-information-system/       # template (placeholder)
│  ├─ facilities-booking/               # template (placeholder)
│  └─ communications-portal/            # template (placeholder)
├─ packages/
│  ├─ ui/                               # shared UI components (optional)
│  └─ shared/                           # shared libs (types, utils)
├─ infra/
│  ├─ docker/                           # docker-compose.*.yml for local dev
│  └─ terraform/                        # VPC, DB, object storage (baseline)
├─ .github/                              # workflows, issue templates, CODEOWNERS
├─ CODE_OF_CONDUCT.md
├─ SECURITY.md
├─ LICENSE
└─ README.md (this file)
```

> This repo embraces **polyglot** development (e.g., TypeScript, Python, Go). Each app documents its own stack and requirements.

---

## App Catalog

| App                                   | Path                               | Status   | Primary Tech                               | What it does                                              |
| ------------------------------------- | ---------------------------------- | -------- | ------------------------------------------ | --------------------------------------------------------- |
| **School Board Management Software**  | `apps/school-board-management/`    | **MVP**  | React/TypeScript, FastAPI/Python, Postgres | Agendas, packets, votes, policies, minutes, public portal |
| Student Information System (template) | `apps/student-information-system/` | Template | *(choose)*                                 | Enrollment, attendance, grades, transcripts               |
| Facilities Booking (template)         | `apps/facilities-booking/`         | Template | *(choose)*                                 | Room/field scheduling, approvals, fee schedules           |
| Communications Portal (template)      | `apps/communications-portal/`      | Template | *(choose)*                                 | Posts, alerts, newsletters, translation workflows         |

---

## Getting Started (Dev)

### Prereqs

* Git, Docker (or Podman), Docker Compose
* For app stacks: Node LTS (if web UI), Python 3.12+ (if FastAPI), or as specified

### Quick start

```bash
# clone
git clone https://github.com/<your-org>/open-source-school-software.git
cd open-source-school-software

# copy env templates (root + app-specific)
cp .env.example .env || true
cp apps/school-board-management/.env.example apps/school-board-management/.env || true

# run local stack (database, API, web)
docker compose -f infra/docker/docker-compose.dev.yml up --build
```

> Visit each app's README for detailed commands, migrations, and seed data.

---

## App Template

Create new apps under `apps/<your-app>/`. Use this **copy‑paste template** inside your app's `README.md` and fill in the blanks.

````markdown
# <App Name>

## Overview
Short paragraph on what the app does and the problem it solves.

## Features
- [ ] Core feature 1
- [ ] Core feature 2
- [ ] Accessibility (WCAG 2.2 AA)

## Architecture
- **Frontend:** <e.g., React + Vite + Tailwind>
- **Backend:** <e.g., FastAPI + SQLAlchemy>
- **Data:** <e.g., Postgres>
- **Storage & Search:** <e.g., S3-compatible, OpenSearch>

## Domain Model
_Describe key entities and relationships, or include an ERD._

## API
Link to `/docs` or describe main endpoints.

## Setup
```bash
# local
cp .env.example .env
make up  # or docker compose up
````

## Configuration

| Variable       | Example            | Purpose               |
| -------------- | ------------------ | --------------------- |
| `DATABASE_URL` | `postgresql://...` | Primary DB connection |
| `API_SECRET`   | `devsecret`        | Local auth/dev key    |

## Testing

```bash
make test
```

## Security & Compliance

* Data classification: Public / Internal / Confidential / Regulated
* PII handling: redaction, logging policy
* AuthN/Z: SSO (OIDC/SAML) support (planned/implemented)

## Deployment

* Docker image(s): `<registry>/<app>:<tag>`
* Terraform module(s): `infra/terraform/*`

## Roadmap

* [ ] Item A
* [ ] Item B

## License

Inherits repository license unless overridden.

````

---

## School Board Management Software
**Path:** `apps/school-board-management/`

### Scope (MVP)
- **Meetings:** agenda builder, attachments, consent calendar, packet PDF, minutes generation
- **Motions & Votes:** roll‑call capture, tallies, export
- **Policies:** library, versions, redline, adoption workflow, public search
- **Public Portal:** ADA‑compliant website for agendas, minutes, policies

### Suggested Stack
- **Frontend:** React + TypeScript + Vite + Tailwind
- **Backend:** FastAPI (Python) + SQLAlchemy + Alembic
- **DB:** PostgreSQL; **Files:** S3‑compatible storage (versioned)
- **Search:** OpenSearch/Elasticsearch (optional in MVP)
- **Auth:** Local dev JWT; ready for Keycloak/Entra/Google SSO

### Local Dev (example)
```bash
cd apps/school-board-management
cp .env.example .env
docker compose up --build
# API → http://localhost:8000/docs
# Web → http://localhost:5173
````

### Initial Entities (example)

* `Meeting(id, title, start_at, location, status)`
* `AgendaItem(id, meeting_id, parent_id, order_no, consent, executive_session)`
* `Motion(id, meeting_id, agenda_item_id, text, status)`
* `Vote(id, motion_id, voter_user_id, choice, timestamp)`
* `Policy(id, code, title, status, category)`
* `PolicyVersion(id, policy_id, version_no, body_md, adopted_on, effective_on)`

> A prebuilt FastAPI/React scaffold is available in this app folder; extend as needed.

---

## Quality, Security & Compliance

* **Accessibility:** target WCAG 2.2 AA for public pages and PDFs.
* **Security:** OWASP ASVS‑inspired checklists, SAST/DAST in CI, dependency scans.
* **Privacy:** follow least‑privilege, data minimization, and provide export tooling for records requests.
* **Observability:** structured logs, traces, metrics; dashboards included in `packages/`.
* **Backups & DR:** document RPO/RTO per app; use versioned object storage for published records.

### Issue Labels (suggested)

`good first issue`, `help wanted`, `a11y`, `security`, `infra`, `api`, `frontend`, `backend`, `docs`.

---

## Contributing

1. Read the [CODE\_OF\_CONDUCT.md](./CODE_OF_CONDUCT.md) and [SECURITY.md](./SECURITY.md).
2. Create a feature branch: `feat/<area>-<short-desc>`.
3. Use **Conventional Commits** (`feat:`, `fix:`, `docs:`…).
4. Add/Update tests and docs.
5. Open a PR with a clear description and screenshots where helpful.

We use ADRs (Architecture Decision Records). New decisions go under `docs/adrs/`.

---

## Releases & Versioning

* **Semantic Versioning** per app (e.g., `school-board-management@v0.3.0`).
* GitHub Releases include changelogs and migration notes.

---

## License

This repository is designed to work with either **Apache‑2.0** (permissive) **or** **AGPL‑3.0** (strong copyleft) depending on your goals. By default, we recommend **Apache‑2.0** for maximum adoption.

> Ensure you keep the `LICENSE` file at the repo root updated and include notices in downstream distributions. If you plan to dual‑license (e.g., AGPL + Commercial), add a `LICENSE-ENTERPRISE` file and a `NOTICE` file.

---

## Acknowledgements

Inspired by the needs of public school districts for transparent governance and modern, accessible software. Thanks to all contributors and the civic‑tech community.
