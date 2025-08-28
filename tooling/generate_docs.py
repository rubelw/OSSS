# tooling/generate_docs.py
"""
Generates lightweight Markdown "stubs" that mkdocstrings fills with Python API docs.
You get one page per top-level Python package/module inside src/OSSS.
"""

from pathlib import Path
import mkdocs_gen_files as gen

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "src" / "OSSS"   # adjust if your package path differs
DOCS_PREFIX = Path("api/python")

def dotted(mod_path: Path) -> str:
    rel = mod_path.relative_to(ROOT / "src")
    return ".".join(rel.with_suffix("").parts)

# Create an index page
with gen.open(DOCS_PREFIX / "index.md", "w") as f:
    f.write("# Python API\n\n")
    f.write("Auto-generated API reference for the `OSSS` package.\n\n")
    f.write("- [Package Reference](./OSSS.md)\n")

# One page for the OSSS package (recursive)
with gen.open(DOCS_PREFIX / "OSSS.md", "w") as f:
    f.write("# `OSSS` package\n\n")
    f.write("::: OSSS\n")
    f.write("    handler: python\n")
    f.write("    options:\n")
    f.write("      show_root_heading: true\n")
    f.write("      show_source: false\n")
    f.write("      docstring_style: google\n")
    f.write("      members_order: source\n")
    f.write("      show_signature: true\n")
