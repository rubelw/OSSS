# OSSS Source Directory (`src/`)

This directory contains the core source code for the **Open Source School Software (OSSS)** platform — including backend services, frontend apps, AI agents, shared libraries, and integrations.

Each subdirectory in `src/` hosts a major component or package that together make up the OSSS monorepo.

## Overview of Subdirectories

```
src/
├── OSSS/              # Backend API (FastAPI)
├── a2a_server/        # Agent‑to‑Agent orchestration & execution service
├── graph_builder/     # Workflow and orchestration graph builder logic
├── metagpt/           # MetaGPT multi‑agent orchestrator + tools
├── osss-web/          # Next.js frontend (UI app)
├── data_model/        # Shared ORM/data model types (optional)
├── ...                # other core packages or helper modules
```

## OSSS Backend (`src/OSSS`)

FastAPI backend providing REST/JSON endpoints, Keycloak authentication, and database integration via SQLAlchemy.

## Frontend Web App (`src/osss-web`)

Next.js App Router UI application with NextAuth + Keycloak integration.

## A2A Server (`src/a2a_server`)

Agent‑to‑Agent service responsible for executing workflows and orchestration tasks.

## MetaGPT Integration (`src/metagpt`)

Multi‑agent orchestration leveraging structured tool schemas and agent reasoning.

## Graph Builder (`src/graph_builder`)

Utilities for creating and validating orchestration graphs.

## Development

### Backend

```bash
cd src/OSSS
uvicorn main:app --reload --port 8081
```

### Frontend

```bash
cd src/osss-web
npm install
npm run dev
```

## License

Code in this directory follows the OSSS project license.
