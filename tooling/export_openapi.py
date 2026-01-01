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


# ---------------------------------------------------------------------------
# 2. Only run if core backend deps are available
# ---------------------------------------------------------------------------

if any(_missing(p) for p in ("fastapi", "pydantic_settings", "sqlalchemy")):
    print("[docs] Skipping OpenAPI export (backend deps missing).")
    sys.exit(0)

try:
    from OSSS.main import app  # FastAPI app
    from fastapi.openapi.utils import get_openapi
except Exception as e:
    print(f"[docs] Skipping OpenAPI export: {e}")
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
    # This writes into the real docs/ tree so MkDocs can still see it.
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
