# tooling/export_openapi.py
import os, sys, json, importlib.util

# Allow CI to skip this step explicitly
if os.getenv("DOCS_SKIP_OPENAPI") == "1":
    print("[docs] Skipping OpenAPI export (DOCS_SKIP_OPENAPI=1).")
    sys.exit(0)

# If the backend stack isn't available, don't fail docs
def _missing(pkg: str) -> bool:
    return importlib.util.find_spec(pkg) is None

if any(_missing(p) for p in ("fastapi", "pydantic_settings", "sqlalchemy")):
    print("[docs] Skipping OpenAPI export (backend deps missing).")
    sys.exit(0)

try:
    from OSSS.main import app  # FastAPI app
    from fastapi.openapi.utils import get_openapi
except Exception as e:
    print(f"[docs] Skipping OpenAPI export: {e}")
    sys.exit(0)

spec = get_openapi(
    title=getattr(app, "title", "OSSS API"),
    version=getattr(app, "version", "0.0.0"),
    routes=getattr(app, "routes", []),
)

# Write via mkdocs_gen_files if present; else fall back to disk
try:
    import mkdocs_gen_files
    with mkdocs_gen_files.open("api/python/openapi.json", "w") as f:
        json.dump(spec, f, indent=2)
    print("[docs] OpenAPI spec generated: api/python/openapi.json")
except Exception:
    os.makedirs("docs/api/python", exist_ok=True)
    with open("docs/api/python/openapi.json", "w") as f:
        json.dump(spec, f, indent=2)
    print("[docs] OpenAPI spec generated: docs/api/python/openapi.json")
