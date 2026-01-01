# tooling/generate_docs.py
"""
Generates lightweight Markdown "stubs" that mkdocstrings fills with Python API docs.

Improvements:
- One page per Python module/package in src/OSSS (not just the top package).
- Auto-generated navigation that mirrors the OSSS package structure.
- mkdocstrings options tuned for FastAPI-style endpoints (clear signatures, Google docstrings).
"""

from pathlib import Path

import mkdocs_gen_files as gen
from mkdocs_gen_files import Nav

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
PKG_DIR = SRC_DIR / "OSSS"  # adjust if your package path differs
DOCS_PREFIX = Path("api/python")


def dotted(mod_path: Path) -> str:
    """
    Convert a Python file path under src/ into a dotted import path.

    Example:
        src/OSSS/api/routes/users.py -> OSSS.api.routes.users
    """
    rel = mod_path.relative_to(SRC_DIR)
    # Strip ".py" and join all parts with dots
    module = ".".join(rel.with_suffix("").parts)
    # Normalize package __init__ modules to the package name
    if module.endswith(".__init__"):
        module = module[: -len(".__init__")]
    return module


nav = Nav()

# ---------------------------------------------------------------------------
# Index page
# ---------------------------------------------------------------------------

with gen.open(DOCS_PREFIX / "index.md", "w") as f:
    f.write("# Python API\n\n")
    f.write(
        "Auto-generated API reference for the `OSSS` package, including FastAPI "
        "apps, routers, and shared utilities.\n\n"
    )
    f.write("- [Package Overview](./OSSS.md)\n")
    f.write("- [Full Module Reference](./SUMMARY.md)\n")

# ---------------------------------------------------------------------------
# Top-level OSSS package page (good landing page for FastAPI users too)
# ---------------------------------------------------------------------------

with gen.open(DOCS_PREFIX / "OSSS.md", "w") as f:
    f.write("# `OSSS` package\n\n")
    f.write("::: OSSS\n")
    f.write("    handler: python\n")
    f.write("    options:\n")
    f.write("      show_root_heading: true\n")
    f.write("      show_source: false\n")
    f.write("      docstring_style: google\n")
    f.write("      members_order: source\n")
    f.write("      separate_signature: true\n")
    f.write("      show_signature: true\n")
    f.write("      show_signature_annotations: true\n")
    f.write("      filters:\n")
    f.write("        - '!^_'  # hide private members\n")

# ---------------------------------------------------------------------------
# Per-module pages (including FastAPI apps/routers)
# ---------------------------------------------------------------------------

for path in sorted(PKG_DIR.rglob("*.py")):
    # Skip __main__ and tests by default
    if path.name == "__main__.py":
        continue
    # You can tweak these filters if you want tests documented too:
    if "tests" in path.parts:
        continue

    module = dotted(path)

    # We already created a custom page for the top-level `OSSS` package
    if module == "OSSS":
        continue

    # Example: OSSS.api.routes.users -> api/python/OSSS/api/routes/users.md
    doc_path = DOCS_PREFIX / (module.replace(".", "/") + ".md")
    doc_path.parent.mkdir(parents=True, exist_ok=True)

    # Build nav structure, e.g. ["OSSS", "api", "routes", "users"]
    parts = module.split(".")
    nav[parts] = doc_path.as_posix()

    # Write mkdocstrings stub for this module
    with gen.open(doc_path, "w") as f:
        title = ".".join(parts[-2:]) if len(parts) > 2 else module
        f.write(f"# `{title}`\n\n")
        f.write(f"::: {module}\n")
        f.write("    handler: python\n")
        f.write("    options:\n")
        f.write("      show_root_heading: true\n")
        f.write("      show_source: false\n")
        f.write("      docstring_style: google\n")
        f.write("      members_order: source\n")
        f.write("      separate_signature: true\n")
        f.write("      show_signature: true\n")
        f.write("      show_signature_annotations: true\n")
        f.write("      filters:\n")
        f.write("        - '!^_'  # hide private members\n")

# ---------------------------------------------------------------------------
# Navigation file for the whole Python API tree
# ---------------------------------------------------------------------------

with gen.open(DOCS_PREFIX / "SUMMARY.md", "w") as nav_file:
    """
    This creates a human-readable nested navigation that you can reference
    from mkdocs.yml, for example:

        nav:
          - Home: index.md
          - Python API:
              - api/python/index.md
              - !include api/python/SUMMARY.md
    """
    nav_file.writelines(nav.build_literate_nav())
