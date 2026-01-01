# tooling/generate_docs.py
"""
Generates lightweight Markdown "stubs" that mkdocstrings fills with Python API docs.

- One page for the top-level `OSSS` package.
- One page per Python module under src/OSSS.
- Modules that are unsafe or unwanted for mkdocstrings are skipped via
  EXPLICIT_SKIP and SKIP_PREFIXES, but still get placeholder pages.
"""

from pathlib import Path
import importlib

import mkdocs_gen_files as gen
from mkdocs_gen_files.nav import Nav

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
PKG_DIR = SRC_DIR / "OSSS"
DOCS_PREFIX = Path("api/python")

# Modules we *always* skip in mkdocstrings
EXPLICIT_SKIP = {
    "OSSS.schemas",
    "OSSS.agents.metagpt_agent",
    "OSSS.ai.api.schemas.query_response",
    "OSSS.core.config",  # <-- NEW: skip this module for mkdocstrings
    "OSSS.middleware.session_ttl",
    "OSSS.services.google_client",
}

# Whole subtrees we skip (module_name.startswith(prefix))
SKIP_PREFIXES = (
    "OSSS.ai.api.",                 # skip all OSSS.ai.api.* modules for mkdocstrings in CI
    "OSSS.ai.orchestration.nodes.", # skip orchestration nodes (heavy deps)
    "OSSS.ai.database.migrations.", # skip AI/db migrations (Alembic-style)
    "OSSS.db.migrations.data.",     # skip alembic data seed helpers
    "OSSS.tests.",            # skip test utils
    # add more prefixes here if needed
)


def dotted(mod_path: Path) -> str:
    """Convert src-relative path to a dotted module path."""
    rel = mod_path.relative_to(SRC_DIR)
    return ".".join(rel.with_suffix("").parts)


def can_import(module_name: str) -> bool:
    """Return True if module_name can be imported, False otherwise."""
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def should_skip_for_mkdocstrings(module_name: str) -> bool:
    """
    Decide whether mkdocstrings should introspect this module.

    Order:
    - Explicit skip list
    - Prefix-based subtree skips
    - Fallback: auto-skip if import fails
    """
    if module_name in EXPLICIT_SKIP:
        return True

    if any(
        module_name == prefix.rstrip(".") or module_name.startswith(prefix)
        for prefix in SKIP_PREFIXES
    ):
        return True

    if not can_import(module_name):
        return True

    return False


nav = Nav()

# ---------------------------------------------------------------------------
# Index page
# ---------------------------------------------------------------------------
with gen.open(DOCS_PREFIX / "index.md", "w") as f:
    f.write("# Python API\n\n")
    f.write("Auto-generated API reference for the `OSSS` package.\n\n")
    f.write("- [Package Reference](./OSSS.md)\n")
    f.write("- [Module Navigation](./SUMMARY.md)\n")

# ---------------------------------------------------------------------------
# Top-level OSSS package page
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
    f.write("      show_signature: true\n")

# Ensure OSSS appears in SUMMARY.md
nav["OSSS"] = "OSSS.md"

# ---------------------------------------------------------------------------
# One page per module under src/OSSS
# ---------------------------------------------------------------------------
for py_file in sorted(PKG_DIR.rglob("*.py")):
    # Skip __init__.py files; packages are covered by their modules + OSSS.md
    if py_file.name == "__init__.py":
        continue

    module_name = dotted(py_file)
    if not module_name.startswith("OSSS"):
        continue

    # docs path relative to api/python
    rel_md_path = py_file.relative_to(PKG_DIR).with_suffix(".md")
    doc_path = DOCS_PREFIX / rel_md_path

    # Nav entry uses a path relative to DOCS_PREFIX
    nav_key_parts = tuple(rel_md_path.parts)
    nav[nav_key_parts] = rel_md_path.as_posix()

    with gen.open(doc_path, "w") as f:
        f.write(f"# `{module_name}`\n\n")

        if should_skip_for_mkdocstrings(module_name):
            f.write(
                "*(API docs for this module are disabled in the MkDocs build "
                "because it cannot be safely imported in the docs environment "
                "or is part of an excluded subtree such as migrations, tests, "
                "or heavy runtime modules.)*\n"
            )
        else:
            f.write(f"::: {module_name}\n")
            f.write("    handler: python\n")
            f.write("    options:\n")
            f.write("      show_root_heading: true\n")
            f.write("      show_source: false\n")
            f.write("      docstring_style: google\n")
            f.write("      members_order: source\n")
            f.write("      show_signature: true\n")

# ---------------------------------------------------------------------------
# SUMMARY.md navigation
# ---------------------------------------------------------------------------
with gen.open(DOCS_PREFIX / "SUMMARY.md", "w") as f:
    f.write("# Python API navigation\n\n")
    f.writelines(nav.build_literate_nav())
