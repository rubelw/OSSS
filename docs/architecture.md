# Architecture

OSSS (Open Source School Software) is a **modular, community-driven K-12 student information system (SIS)** designed to support the full lifecycle of school operations. It is built as a **polyglot monorepo** combining a modern frontend, a Python backend API, infrastructure integration (Keycloak, databases), and optional AI workflows. :contentReference[oaicite:0]{index=0}

---

## ⛓ High-Level System Overview

OSSS is architected as two principal subsystems:

1. **Frontend (Web client)**  
   - Built with **Next.js (App Router)** and **TypeScript**.  
   - Provides the user interface for administrators, teachers, parents, and students.  
   - Integrates authentication with **Auth.js (NextAuth)** and **Keycloak**.  
   - Shares static assets, UI components, utility libraries, and type definitions. :contentReference[oaicite:1]{index=1}

2. **Backend (API server)**  
   - Developed with **FastAPI** (Python) serving REST/JSON endpoints.  
   - Uses **SQLAlchemy** as the ORM.  
   - Integrates with **Keycloak** for authentication & authorization.  
   - Supports optional AI-driven orchestration and workflow patterns. :contentReference[oaicite:2]{index=2}

---

## 🏛 Logical Layers

### 1. **User Interface Layer (Frontend)**

- **Next.js App Router** organizes UI and route logic.  
- **Pages & API routes** under `app/` deliver HTML and handle client-side interactions.  
- UI logic imports shared components and utilities (`components/`, `lib/`, `types/`).  
- Auth flows (login, session, token refresh) are managed through NextAuth/Keycloak.  
- Static assets (favicon, logo, docs) are served from `public/`. :contentReference[oaicite:3]{index=3}

### 2. **Application API Layer (Backend)**

- **FastAPI** defines the REST API surface consumed by web clients and external systems.  
- Authorization and security are enforced via Keycloak tokens and scopes.  
- Data models and persistence logic live alongside business rules.  
- OpenAPI schema is auto-exported to drive docs or client SDK generation. :contentReference[oaicite:4]{index=4}

### 3. **Identity & Access Management**

- **Keycloak** manages authentication, user identity, realms, clients, and token issuance.  
- Both frontend (NextAuth) and backend validate Keycloak JWTs.  
- Role-based access rules ensure separation between admin, staff, parent, and student roles.

### 4. **Persistence Layer**

- **Relational Database (e.g., PostgreSQL)** stores primary SIS data (users, enrollments, grades, attendance).
- **Redis (optional)** serves caching or session store backends for scalability.
- Backend uses SQLAlchemy sessions and migrations for schema evolution.

### 5. **AI Orchestration (Optional)**

OSSS includes patterns for AI-assisted workflows:

- A high level “query orchestration” dispatches agent workflows.
- Graph abstractions and orchestrators define dynamic processing pipelines.
- External AI backends (Ollama, MetaGPT, etc.) can execute defined nodes. :contentReference[oaicite:5]{index=5}

---

## 🧠 Interaction & Data Flow

Below is a simplified view of typical interactions:

