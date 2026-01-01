#!/usr/bin/env python3

# tooling/export_openapi.py
"""
Fetch OpenAPI JSON from a running backend instance and write it to `docs/backend`.
Also generate an OpenAPI Markdown page that renders ReDoc and links to the JSON.

Run manually:
    ./export_openapi.py

Used automatically during MkDocs build via `gen-files`.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import request, error as urllib_error

from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[1]

# Load environment if available
env_path = project_root / ".env"
if env_path.exists():
    print(f"[docs] Loading environment from: {env_path}")
    load_dotenv(env_path)
else:
    print(f"[docs] WARNING: .env not found at: {env_path}")

# ---------------------------------------------------------------------------
# 1. Allow CI / local builds to skip this step explicitly
# ---------------------------------------------------------------------------

if os.getenv("DOCS_SKIP_OPENAPI") == "1":
    print("[docs] Skipping OpenAPI export (DOCS_SKIP_OPENAPI=1).")
    sys.exit(0)

# Endpoint to fetch from; overrideable via env if needed
OPENAPI_URL = os.getenv("OSSS_OPENAPI_URL", "http://localhost:8081/openapi.json")


def _write_stub(reason: str) -> None:
    """Write stub JSON + MD if schema cannot be fetched."""
    print(f"[docs] Writing stub OpenAPI docs (reason: {reason})")

    stub_spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {
            "title": "OSSS API (stub)",
            "version": "0.0.0",
            "description": f"Stub OpenAPI schema generated because: {reason}",
        },
        "paths": {},
    }

    try:
        import mkdocs_gen_files as gen

        # --- JSON ---
        with gen.open("backend/openapi.json", "w") as f:
            json.dump(stub_spec, f, indent=2)

        # --- Markdown (stub page, still using ../openapi.json links) ---
        with gen.open("backend/openapi.md", "w") as f:
            f.write("# OSSS API (OpenAPI)\n\n")
            f.write("> Stub schema generated — real backend not reachable.\n\n")
            f.write("> If the panel below stays blank, click this link to verify the JSON exists:\n")
            f.write("> **[OpenAPI JSON](../openapi.json)**\n\n")
            f.write('<div id="redoc-container"></div>\n\n')
            f.write("<script>\n")
            f.write("  (function () {\n")
            f.write("    function init() {\n")
            f.write("      var el = document.getElementById('redoc-container');\n")
            f.write("      if (window.Redoc && el) {\n")
            f.write("        window.Redoc.init('../openapi.json', {}, el);\n")
            f.write("      } else {\n")
            f.write("        setTimeout(init, 50);\n")
            f.write("      }\n")
            f.write("    }\n")
            f.write("    init();\n")
            f.write("  })();\n")
            f.write("</script>\n\n")
            f.write("<noscript>\n")
            f.write("  JavaScript is required to render the ReDoc UI. "
                    "You can still download the\n")
            f.write("  <a href=\"../openapi.json\">OpenAPI JSON</a>.\n")
            f.write("</noscript>\n")

        print("[docs] Stub written using mkdocs-gen-files")

    except Exception:
        # Fallback: write directly to ../docs/backend
        docs_dir = project_root / "docs" / "backend"
        docs_dir.mkdir(parents=True, exist_ok=True)

        json_path = docs_dir / "openapi.json"
        md_path = docs_dir / "openapi.md"

        with open(json_path, "w") as f:
            json.dump(stub_spec, f, indent=2)

        with open(md_path, "w") as f:
            f.write("# OSSS API (OpenAPI)\n\n")
            f.write("> Stub schema generated — real backend not reachable.\n\n")
            f.write("> If the panel below stays blank, click this link to verify the JSON exists:\n")
            f.write("> **[OpenAPI JSON](../openapi.json)**\n\n")
            f.write('<div id="redoc-container"></div>\n\n')
            f.write("<script>\n"
                    "  (function () {\n"
                    "    function init() {\n"
                    "      var el = document.getElementById('redoc-container');\n"
                    "      if (window.Redoc && el) {\n"
                    "        window.Redoc.init('../openapi.json', {}, el);\n"
                    "      } else {\n"
                    "        setTimeout(init, 50);\n"
                    "      }\n"
                    "    }\n"
                    "    init();\n"
                    "  })();\n"
                    "</script>\n\n")
            f.write("<noscript>\n"
                    "  JavaScript is required to render the ReDoc UI. "
                    "You can still download the\n"
                    "  <a href=\"../openapi.json\">OpenAPI JSON</a>.\n"
                    "</noscript>\n")

        print(f"[docs] Stub written on disk: {json_path}, {md_path}")


def _fetch_openapi(url: str) -> dict[str, Any]:
    print(f"[docs] Fetching OpenAPI schema from: {url}")
    try:
        with request.urlopen(url) as resp:
            if getattr(resp, "status", 200) != 200:
                raise RuntimeError(f"unexpected HTTP status {resp.status}")
            return json.loads(resp.read().decode("utf-8"))
    except (urllib_error.URLError, urllib_error.HTTPError,
            RuntimeError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Failed to fetch OpenAPI JSON from {url}: {e}") from e


def main() -> None:
    try:
        spec = _fetch_openapi(OPENAPI_URL)
    except Exception as e:
        print(f"[docs] Skipping real OpenAPI export: {e}")
        _write_stub(str(e))
        return

    # --------------------- Write via mkdocs-gen-files ---------------------
    try:
        import mkdocs_gen_files as gen

        # JSON
        with gen.open("backend/openapi.json", "w") as f:
            json.dump(spec, f, indent=2)

        # Markdown with ReDoc (your requested snippet)
        with gen.open("backend/openapi.md", "w") as f:
            f.write("# OSSS API (OpenAPI)\n\n")
            f.write("> If the panel below stays blank, click this link to verify the JSON exists:\n")
            f.write("> **[OpenAPI JSON](../openapi.json)**\n\n")

            f.write('<div id="redoc-container"></div>\n\n')
            f.write("<script>\n")
            f.write("  (function () {\n")
            f.write("    function init() {\n")
            f.write("      var el = document.getElementById('redoc-container');\n")
            f.write("      if (window.Redoc && el) {\n")
            f.write("        // From /OSSS/backend/openapi/ → /OSSS/backend/openapi.json\n")
            f.write("        window.Redoc.init('../openapi.json', {}, el);\n")
            f.write("      } else {\n")
            f.write("        setTimeout(init, 50);\n")
            f.write("      }\n")
            f.write("    }\n")
            f.write("    init();\n")
            f.write("  })();\n")
            f.write("</script>\n\n")

            f.write("<noscript>\n")
            f.write("  JavaScript is required to render the ReDoc UI. "
                    "You can still download the\n")
            f.write("  <a href=\"../openapi.json\">OpenAPI JSON</a>.\n")
            f.write("</noscript>\n")

        print("[docs] OpenAPI ReDoc page generated via mkdocs-gen-files.")

    # ------------------- Fallback write directly -------------------------
    except Exception:
        docs_dir = project_root / "docs" / "backend"
        docs_dir.mkdir(parents=True, exist_ok=True)

        json_path = docs_dir / "openapi.json"
        md_path = docs_dir / "openapi.md"

        with open(json_path, "w") as f:
            json.dump(spec, f, indent=2)

        with open(md_path, "w") as f:
            f.write("# OSSS API (OpenAPI)\n\n")
            f.write("> If the panel below stays blank, click this link to verify the JSON exists:\n")
            f.write("> **[OpenAPI JSON](../openapi.json)**\n\n")
            f.write('<div id="redoc-container"></div>\n\n')
            f.write("<script>\n"
                    "  (function () {\n"
                    "    function init() {\n"
                    "      var el = document.getElementById('redoc-container');\n"
                    "      if (window.Redoc && el) {\n"
                    "        // From /OSSS/backend/openapi/ → /OSSS/backend/openapi.json\n"
                    "        window.Redoc.init('../openapi.json', {}, el);\n"
                    "      } else {\n"
                    "        setTimeout(init, 50);\n"
                    "      }\n"
                    "    }\n"
                    "    init();\n"
                    "  })();\n"
                    "</script>\n\n")
            f.write("<noscript>\n"
                    "  JavaScript is required to render the ReDoc UI. "
                    "You can still download the\n"
                    "  <a href=\"../openapi.json\">OpenAPI JSON</a>.\n"
                    "</noscript>\n")

        print(f"[docs] OpenAPI ReDoc page generated on disk: {json_path}, {md_path}")


if __name__ == "__main__":
    main()
