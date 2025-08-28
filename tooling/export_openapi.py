# tooling/export_openapi.py
import json
import mkdocs_gen_files as gen

# Import your FastAPI app object (adjust the import if your app lives elsewhere)
from OSSS.main import app

with gen.open("api/openapi/openapi.json", "w") as f:
    json.dump(app.openapi(), f, indent=2)
