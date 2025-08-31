# OSSS: Open Student Support System

[![Build
Status](https://img.shields.io/github/actions/workflow/status/rubelw/OSSS/docs.yml?branch=main)](https://github.com/rubelw/OSSS/actions)
[![License](https://img.shields.io/github/license/rubelw/OSSS)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-latest-blue)](https://rubelw.github.io/OSSS/)

------------------------------------------------------------------------

## 📖 Project Description

**OSSS (Open Student Support System)** is an **open-source,
community-driven platform** for **K-12 school district governance and
student information management**.

It integrates **FastAPI**, **Keycloak**, and **SQLAlchemy** to provide a
modern, modular, and extensible **School Information System (SIS)** and
governance software suite. OSSS empowers administrators, educators,
students, and families to collaborate on district operations and
instructional support.

**Keywords:** Open Student Support System, K-12 school district
governance software, FastAPI + Keycloak + SQLAlchemy SIS platform

![Demo](https://raw.githubusercontent.com/rubelw/OSSS/main/docs/demo.gif)

------------------------------------------------------------------------

## 🚀 Features

-   **K-12 Governance Tools**: Manage boards of education,
    superintendent offices, schools, and leadership structures.
-   **Authentication/Authorization**: Keycloak-based user, role, and
    permissions management.
-   **FastAPI Backend**: High-performance REST API with OpenAPI docs.
-   **Next.js Frontend**: Modern TypeScript web app with interactive
    dashboards.
-   **Database & ORM**: PostgreSQL with SQLAlchemy and Alembic
    migrations.
-   **Documentation**: Built with MkDocs Material, TypeDoc, and
    mkdocstrings.
-   **Community Contributions**: Open, participatory development.

------------------------------------------------------------------------

## 🛠 Installation

Clone and set up the repository:

``` bash
git clone https://github.com/rubelw/OSSS.git
cd OSSS

# (optional) copy environment examples
cp .env.example .env || true

# create a venv
python3 -m venv .venv
source .venv/bin/activate

# start the stack
./start_osss.sh
```

### Local Services

-   Keycloak: http://localhost:8085 (admin/admin)
-   FastAPI: http://localhost:8081/docs (user:
    `activities_director@osss.local` / password: `password`)
-   Web App: http://localhost:3000 (same demo credentials)

------------------------------------------------------------------------

## 📚 Usage

-   **CLI:**

    ``` bash
    osss <TAB>
    ```

-   **Docs:** <https://rubelw.github.io/OSSS/>

-   **MkDocs Build:**

    ``` bash
    mkdocs build --clean
    ```

------------------------------------------------------------------------

## 🤝 Contributing

We welcome contributions! You can: - Open issues for bugs, questions, or
ideas. - Submit pull requests for new features or fixes. - Improve docs
or translations.

Check the [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

------------------------------------------------------------------------

## 📜 License

This project is licensed under the [Apache 2.0 License](LICENSE).

------------------------------------------------------------------------

## 📷 Screenshots & Docs

-   **Web UI:** ![Example Web
    View](https://raw.githubusercontent.com/rubelw/OSSS/main/docs/img/web_view.png)
-   **Demo GIF:** ![OSSS
    Demo](https://raw.githubusercontent.com/rubelw/OSSS/main/docs/demo.gif)
-   **Live Documentation:**
    [rubelw.github.io/OSSS](https://rubelw.github.io/OSSS/)
