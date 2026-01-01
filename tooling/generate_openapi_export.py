#!/usr/bin/env python3

# tooling/export_openapi.py
"""
Generate the OpenAPI schema for the OSSS FastAPI backend and expose it
to MkDocs under `backend/openapi.*`.

This script is invoked by the `gen-files` plugin during `mkdocs build`.
"""

import os
import sys
import json
import importlib.util

# ---------------------------------------------------------------------------
# 1. Allow CI / local builds to skip this step explicitly
# ---------------------------------------------------------------------------

if os.getenv("DOCS_SKIP_OPENAPI") == "1":
    print("[docs] Skipping OpenAPI export (DOCS_SKIP_OPENAPI=1).")
    sys.exit(0)


def _missing(pkg: str) -> bool:
    """Return True if the given package cannot be imported."""
    return importlib.util.find_spec(pkg) is None


def _write_stub(reason: str) -> None:
    """Write a minimal stub OpenAPI page so docs still build."""
    print(f"[docs] Writing stub OpenAPI docs (reason: {reason})")

    try:
        import mkdocs_gen_files as gen

        stub_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "OSSS API (stub)",
                "version": "0.0.0",
                "description": f"Stub OpenAPI schema generated because: {reason}",
            },
            "paths": {},
        }

        with gen.open("backend/openapi.json", "w") as f:
            json.dump(stub_spec, f, indent=2)

        with gen.open("backend/openapi.md", "w") as f:
            f.write("# OSSS OpenAPI schema (stub)\n\n")
            f.write(
                "The real backend could not be imported when building docs, "
                "so a minimal stub schema was generated instead.\n\n"
            )
            f.write("```json\n")
            json.dump(stub_spec, f, indent=2)
            f.write("\n```\n")

    except Exception:
        # Fallback to writing directly into docs/backend
        os.makedirs("docs/backend", exist_ok=True)
        json_path = os.path.join("docs", "backend", "openapi.json")
        md_path = os.path.join("docs", "backend", "openapi.md")

        stub_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "OSSS API (stub)",
                "version": "0.0.0",
                "description": f"Stub OpenAPI schema generated because: {reason}",
            },
            "paths": {},
        }

        with open(json_path, "w") as f:
            json.dump(stub_spec, f, indent=2)

        with open(md_path, "w") as f:
            f.write("# OSSS OpenAPI schema (stub)\n\n")
            f.write(
                "The real backend could not be imported when building docs, "
                "so a minimal stub schema was generated instead.\n\n"
            )
            f.write("```json\n")
            json.dump(stub_spec, f, indent=2)
            f.write("\n```\n")

        print(f"[docs] Stub OpenAPI spec generated on disk: {json_path}, {md_path}")


# ---------------------------------------------------------------------------
# 2. Only run if core backend deps are available
# ---------------------------------------------------------------------------

if any(_missing(p) for p in ("fastapi", "pydantic_settings", "sqlalchemy")):
    _write_stub("backend dependencies missing")
    sys.exit(0)

try:
    from OSSS.main import app  # FastAPI app
    from fastapi.openapi.utils import get_openapi
except Exception as e:
    # 🔁 Instead of just skipping, write a stub
    print(f"[docs] Skipping real OpenAPI export: {e}")
    _write_stub(str(e))
    sys.exit(0)

# ---------------------------------------------------------------------------
# 3. Build the OpenAPI spec from the FastAPI app
# ---------------------------------------------------------------------------

spec = get_openapi(
    title=getattr(app, "title", "OSSS API"),
    version=getattr(app, "version", "0.0.0"),
    routes=getattr(app, "routes", []),
)

# ---------------------------------------------------------------------------
# 4. Write schema into MkDocs' virtual docs tree (backend/openapi.*)
# ---------------------------------------------------------------------------

try:
    import mkdocs_gen_files as gen

    # JSON schema (useful for external tools)
    with gen.open("backend/openapi.json", "w") as f:
        json.dump(spec, f, indent=2)

    # Human-friendly markdown page that embeds the schema
    with gen.open("backend/openapi.md", "w") as f:
        f.write("# OSSS OpenAPI schema\n\n")
        f.write(
            "This page exposes the OpenAPI schema for the OSSS backend. "
            "You can use this JSON with tools like Postman, Insomnia, or code generators.\n\n"
        )
        f.write("```json\n")
        json.dump(spec, f, indent=2)
        f.write("\n```\n")

    print("[docs] OpenAPI spec generated via mkdocs-gen-files: backend/openapi.{json,md}")

except Exception:
    # Fallback for local runs without mkdocs-gen-files context.
    os.makedirs("docs/backend", exist_ok=True)

    json_path = os.path.join("docs", "backend", "openapi.json")
    md_path = os.path.join("docs", "backend", "openapi.md")

    with open(json_path, "w") as f:
        json.dump(spec, f, indent=2)

    with open(md_path, "w") as f:
        f.write("# OSSS OpenAPI schema\n\n")
        f.write(
            "This page exposes the OpenAPI schema for the OSSS backend. "
            "You can use this JSON with tools like Postman, Insomnia, or code generators.\n\n"
        )
        f.write("```json\n")
        json.dump(spec, f, indent=2)
        f.write("\n```\n")

    print(f"[docs] OpenAPI spec generated on disk: {json_path}, {md_path}")
