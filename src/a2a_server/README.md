# A2A Server (Agent‑to‑Agent Service)

The **A2A Server** (Agent‑to‑Agent) is a backend service in the OSSS ecosystem responsible for executing
agent workflows, processing graph tasks, and coordinating autonomous operations between subsystems.

This service is designed to run as a container in development or production environments and interacts
with other OSSS components via REST or queue mechanisms depending on your deployment.

---

## 🚀 Purpose

The A2A Server’s responsibilities include:

- Executing agent workflows defined in orchestration graphs
- Responding to scheduled or event‑triggered tasks
- Managing nodes and micro‑workflows in a decoupled architecture
- Serving as a backend for agent pipelines that assist operational logic

---

## 📦 Overview

```
src/a2a_server/
├── __init__.py
├── main.py               # Entrypoint for the A2A FastAPI or background worker
├── api/                  # API route handlers (if present)
├── core/                 # Core orchestration and workflow logic
├── models/               # Data models
├── services/             # Internal service abstractions
├── settings.py           # Configuration for the A2A service
└── utils.py              # Shared utilities
```

> Actual top‑level files and structure may vary slightly depending on your current OSSS version.

---

## 🧠 Features

### ⚙️ Configuration

The A2A Server reads configuration from environment variables or a `.env` file:

| Variable               | Description                          |
|------------------------|--------------------------------------|
| `A2A_LOG_LEVEL`        | Logging verbosity                    |
| `A2A_DATABASE_URL`     | Connection for internal persistence  |
| `A2A_BROKER_URL`       | Message queue broker (optional)      |
| `KEYCLOAK_ISSUER`      | Keycloak realm issuer URL            |
| `KEYCLOAK_AUDIENCE`    | Client audience for token validation |
| `KEYCLOAK_BASE_URL`    | Identity provider base URL           |

*Replace with the actual variables used in your service settings.*

---

## 🧪 Running the Service

### 📌 Locally

From the repository root:

```bash
# Activate your Python environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r src/a2a_server/requirements.txt

# Run the A2A server
python src/a2a_server/main.py
```

> If the service uses FastAPI, it might run via Uvicorn:
>
> ```bash
> uvicorn a2a_server.main:app --reload --host 0.0.0.0 --port 8001
> ```

---

## 📦 Containerized Development

When running as part of Docker Compose:

```bash
docker compose up a2a-agent
```

This will start the `a2a-agent` service together with its dependencies.

---

## 🧩 How It Communicates

- **REST API** — If the server exposes HTTP endpoints, they are defined under `api/`
- **Message Queues** — Optional broker channels for background task processing
- **Database / Persistence** — For storing workflow state or results
- **Keycloak Auth** — Validates tokens if protected APIs are used

> For details, refer to your service’s router definitions and dependency wiring.

---

## 🧠 Code Style and Guidelines

- The service uses **FastAPI** conventions (if present)
- General Python structure follows OSSS backend patterns
- Modular code separates:
  - API layers
  - Business logic
  - Models and validation
  - Utilities

---

## 🧪 Testing

You can test A2A service components using your preferred test suite:

```bash
# Run unit tests
pytest --maxfail=1 --disable-warnings
```

> Extend tests in `tests/a2a_server/` if present.

---

## 🧾 License

This service is part of the OSSS project and subject to the same
[LICENSE](../../LICENSE) in the root of the repository.

---
