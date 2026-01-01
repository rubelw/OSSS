#!/usr/bin/env python3


# tooling/generate_openapi_page.py
from pathlib import Path
import mkdocs_gen_files as gen

DOCS_PREFIX = Path("api/rest")

with gen.open(DOCS_PREFIX / "index.md", "w") as f:
    f.write("# REST API\n\n")
    f.write("The OSSS backend exposes a FastAPI application.\n\n")
    f.write("::: swagger-ui\n")
    f.write("    type: redoc\n")
    f.write("    url: /openapi.json\n")