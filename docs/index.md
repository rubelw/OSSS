# Open Source School Software (OSSS)

**Open Source School Software (OSSS)** is an **open source school software** platform—a modern **K‑12 Student Information System (SIS)** built with **FastAPI**, **Keycloak**, and **SQLAlchemy**. OSSS focuses on **student records**, **governance & workflows**, and core SIS features (attendance, scheduling, staff & family access), designed for school districts that want a transparent, extensible stack.

OSSS ships as a developer‑friendly API with clean domain models and authentication via OpenID Connect (Keycloak). It’s designed to be easy to deploy on PostgreSQL and to extend with React/Next.js front ends.

!!! warning "Project status: active development"
    **OSSS is still being developed.** Community input and assistance are very welcome!
    - Share feedback and ideas via issues or discussions.
    - Open PRs for bug fixes and small improvements.
    - See [Contributing](#contributing) for guidelines.

---

## Why This Is Important

When Artificial General Intelligence (AGI) starts to emerge—potentially by 2030—districts will need to adjust governance, safety filters, and curricula rapidly. That kind of agility is exactly what community-maintained, open-source software delivers—without waiting on a vendor roadmap.

---

## What is in this repo?

The following layout is **generated automatically at build time**:

```bash
{# Disabled repo_tree macro – macro no longer configured in mkdocs.yaml
{{ repo_tree("docs", max_depth=2) }}
#}
```

Each directory contains an `app-specific` README describing its purpose.

---

## Getting started (local development)

### Quick start
```bash
git clone https://github.com/rubelw/OSSS.git
cd OSSS
python3 -m venv .venv
source .venv/bin/activate
./start_osss.sh
```

---

## Documentation

Docs are built with **MkDocs Material** and include generated TypeScript and Python API references.

- Backend API → [Python API](api/python/index.md)  
- Frontend API → [Web API](api/web/README.md)

---

## Contributing

We welcome pull requests! See `CONTRIBUTING.md` for guidelines.

---

## License

Apache‑2.0 — see `LICENSE`.

