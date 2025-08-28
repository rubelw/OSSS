!!! warning "Project status: active development"
    **OSSS is still being developed.** Community input and assistance are very welcome!
    - Share feedback and ideas via issues or discussions.
    - Open PRs for bug fixes and small improvements.

# Open Source School Software (OSSS)

A community-driven, modular suite of applications for K-12 districts.

> 📚 **Live documentation:** https://rubelw.github.io/OSSS/

This repository is a **polyglot monorepo** with a Next.js frontend (`src/osss-web`) and a FastAPI
backend (`src/OSSS`). Documentation is built with **MkDocs Material**, with API references
generated from source:

- **Frontend (TypeScript)** → TypeDoc → Markdown (`docs/api/web/*`)
- **Backend (Python)** → mkdocstrings renders code objects from `src/OSSS`
- **REST (OpenAPI)** → exported JSON rendered with ReDoc

The static site is output to `./documentation/`.

![Example Web View](https://raw.githubusercontent.com/rubelw/OSSS/main/docs/img/web_view.png)

---

## Why This Is Important

When Artificial General Intelligence (AGI) starts to emerge—potentially by 2030—districts will need to adjust governance, safety filters, and curricula rapidly. That kind of agility is exactly what community-maintained, open-source software delivers—without waiting on a vendor roadmap. Today, many incumbent systems are tied to legacy architectures and slow release cycles. While AI is already reshaping mainstream apps, most school platforms haven’t meaningfully evolved to leverage it.

I’m building the next generation of school software as an open, participatory project. Administrators, staff, students, and families will be able to propose enhancements, contribute code, and ship improvements together—so the platform keeps pace with classroom needs and policy changes.

---

## 📖 Documentation Quick Start

> Run all commands from the **repo root**. Create and activate a Python venv first.  
> Live docs are published at **https://rubelw.github.io/OSSS/**.

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

# Keycloak http://localhost:8085 with username 'admin' and password 'admin'
# FastApi  http://localhost:8081/docs# username 'activities_director@osss.local' and password 'password'
# Web: http://localhost:3000 username 'activities_director@osss.local' and password 'password'
```

Build the static site to `./documentation/`:

```bash
# Optional: regenerate TypeDoc first if code changed
npx typedoc --options typedoc.frontend.json
mkdocs build --clean
```

---

## 📁 Docs Layout (MkDocs)

```
docs/
├─ index.md                      # Landing page
├─ frontend/
│  └─ overview.md                # Next.js app overview
├─ backend/
│  └─ overview.md                # FastAPI app overview
├─ api/
│  ├─ web/                       # (generated) TypeDoc markdown for Next.js
│  └─ openapi/                   # (generated) openapi.json for ReDoc
└─ api/python/
   ├─ index.md                   # (generated) landing for Python API
   └─ OSSS.md                    # (generated) mkdocstrings page for OSSS package
```

> The pages under `docs/api/python/` and `docs/api/openapi/` are created during the MkDocs build by
> small helper scripts (see below). TypeDoc output is generated before the build runs.

---

## Demo

![OSSS demo](https://raw.githubusercontent.com/rubelw/OSSS/main/docs/demo.gif)


## ⚙️ MkDocs Configuration

`mkdocs.yml` at the repo root glues everything together. Key bits:

```yaml
site_name: OSSS Developer Documentation
site_url: https://rubelw.github.io/OSSS/
docs_dir: docs
site_dir: documentation

nav:
  - Overview: index.md
  - Frontend (Next.js):
      - Overview: frontend/overview.md
      - API (TypeScript): api/web/modules.md   # <-- match what TypeDoc emits (modules.md or index.md)
  - Backend (Python):
      - Overview: backend/overview.md
      - API (Python): api/python/OSSS.md
      - OpenAPI: backend/openapi.md

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: ["src"]           # import OSSS from ./src/OSSS
          options:
            show_source: false
            docstring_style: google
            members_order: source
  - gen-files:
      scripts:
        - tooling/generate_docs.py
        - tooling/export_openapi.py

# Optional: make pages wider site-wide, or include a page-class-based override
extra_css:
  - overrides/wide.css

# Load ReDoc globally so the OpenAPI page can initialize it
extra_javascript:
  - https://cdn.redoc.ly/redoc/latest/bundles/redoc.standalone.js
```

### Helper scripts (run during `mkdocs serve/build`)

- `tooling/generate_docs.py` — generates `docs/api/python/OSSS.md` that contains the `::: OSSS`
  directive; mkdocstrings renders it into API docs.

  ```python
  # tooling/generate_docs.py
  from pathlib import Path
  import mkdocs_gen_files as gen

  with gen.open("api/python/index.md", "w") as f:
      f.write("# Python API\n\n- [OSSS package](./OSSS.md)\n")

  with gen.open("api/python/OSSS.md", "w") as f:
      f.write("# `OSSS` package\n\n")
      f.write("::: OSSS\n")
      f.write("    handler: python\n")
      f.write("    options:\n")
      f.write("      show_root_heading: true\n")
      f.write("      show_source: false\n")
      f.write("      docstring_style: google\n")
      f.write("      members_order: source\n")
      f.write("      show_signature: true\n")
  ```

- `tooling/export_openapi.py` — writes `docs/api/openapi/openapi.json` from the FastAPI app.

  ```python
  # tooling/export_openapi.py
  import json
  import mkdocs_gen_files as gen
  from OSSS.main import app              # adjust if your FastAPI app lives elsewhere

  with gen.open("api/openapi/openapi.json", "w") as f:
      json.dump(app.openapi(), f, indent=2)
  ```

### ReDoc page (`docs/backend/openapi.md`)

```md
---
title: OSSS API (OpenAPI)
hide:
  - toc
class: full-width
---

> If the panel below stays blank, verify the JSON exists:
> **[OpenAPI JSON](../../api/openapi/openapi.json)**

<div id="redoc-container"></div>

<script>
(function () {
  function init() {
    var el = document.getElementById('redoc-container');
    if (window.Redoc && el) {
      // NOTE: two ".." segments from /backend/openapi → /api/openapi/openapi.json
      window.Redoc.init('../../api/openapi/openapi.json', {}, el);
    } else {
      setTimeout(init, 50);
    }
  }
  init();
})();
</script>

<noscript>
JavaScript is required to render the ReDoc UI. You can still download the
<a href="../../api/openapi/openapi.json">OpenAPI JSON</a>.
</noscript>
```

### Optional: widen pages

`docs/overrides/wide.css` (site-wide) or `docs/overrides/redoc-wide.css` (only OpenAPI page):

```css
/* Site-wide wider grid */
.md-grid { max-width: 1440px; }

/* Only pages with class: full-width */
.md-content__inner.full-width { max-width: none; padding-left: 0; padding-right: 0; }
#redoc-container { margin: 0; padding: 0; }
```

Reference in `mkdocs.yml` via `extra_css`.

---

## 🔐 Environment Notes

- **Python imports for docs**: run `mkdocs` with `PYTHONPATH=src` so mkdocstrings and the OpenAPI
  export can import `OSSS` from `src/OSSS`.
- **Frontend generator**: TypeDoc runs with your Next.js `tsconfig`. If the app declares
  "packageManager" in `src/osss-web/package.json`, use **npm** (not pnpm) for consistency.

---

## 🧪 CI Example (GitHub Actions)

`.github/workflows/docs.yml`

```yaml
name: Build Docs
on:
  push:
    branches: [ main ]
  workflow_dispatch:

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-docs.txt
          npm ci || npm i

      - name: Generate TypeScript API (TypeDoc → Markdown)
        run: npx typedoc --options typedoc.frontend.json

      - name: Build MkDocs site → ./documentation
        env:
          PYTHONPATH: src
        run: mkdocs build --clean

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: osss-docs
          path: documentation
```
---

## 📜 License

Apache-2.0 (see `LICENSE`).

