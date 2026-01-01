# tooling/generate_docs.py
"""
Generates lightweight Markdown "stubs" that mkdocstrings fills with Python API docs.

- One page for the top-level `OSSS` package.
- One page per Python module under src/OSSS (e.g. OSSS.tutors.router → api/python/OSSS/tutors/router.md)
- A SUMMARY.md with a nice tree nav for the Python API (used from mkdocs.yml).
"""

from pathlib import Path

import mkdocs_gen_files as gen
from mkdocs_gen_files.nav import Nav

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
PKG_DIR = SRC_DIR / "OSSS"  # FastAPI backend package
DOCS_PREFIX = Path("api/python")  # where we write generated docs

# Modules that should NOT be passed to mkdocstrings (e.g. heavy / optional deps)
# You can add/remove entries as needed.
SKIP_MKDOCSTRINGS = {
    "OSSS.schemas",
    "OSSS.agents.metagpt_agent",
}


def dotted(mod_path: Path) -> str:
    """
    Convert a module file path under src/ into a dotted Python module name.

    Example:
        src/OSSS/tutors/router.py -> OSSS.tutors.router
    """
    rel = mod_path.relative_to(SRC_DIR)
    return ".".join(rel.with_suffix("").parts)


nav = Nav()

# ---------------------------------------------------------------------------
# 1. Root index page for Python API
# ---------------------------------------------------------------------------
with gen.open(DOCS_PREFIX / "index.md", "w") as f:
    f.write("# Python API\n\n")
    f.write("Auto-generated API reference for the `OSSS` backend package.\n\n")
    f.write("- [Package Reference](./OSSS.md)\n")
    f.write("- [Module Navigation](./SUMMARY.md)\n")


# ---------------------------------------------------------------------------
# 2. One page for the top-level OSSS package
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

# Make sure the package page is in the nav
nav["OSSS"] = "OSSS.md"

# ---------------------------------------------------------------------------
# 3. One page per module under src/OSSS
# ---------------------------------------------------------------------------
for py_file in sorted(PKG_DIR.rglob("*.py")):
    # Skip __init__.py — we already have the root OSSS package page,
    # and subpackages will be covered by their internal modules.
    if py_file.name == "__init__.py":
        continue

    module_name = dotted(py_file)
    if not module_name.startswith("OSSS"):
        # Safety check / future-proofing
        continue

    # Compute doc path inside docs (e.g. OSSS/tutors/router.md)
    rel_md_path = py_file.relative_to(PKG_DIR).with_suffix(".md")
    doc_path = DOCS_PREFIX / rel_md_path

    # Build nav *relative* to DOCS_PREFIX, so links in SUMMARY.md
    # don’t accidentally prefix "api/python" twice.
    nav_key_parts = tuple(rel_md_path.parts)
    nav[nav_key_parts] = rel_md_path.as_posix()

    # Write the stub page for this module
    with gen.open(doc_path, "w") as f:
        f.write(f"# `{module_name}`\n\n")

        # If this module is problematic to import in the docs environment,
        # don’t call mkdocstrings on it; just leave a placeholder.
        if module_name in SKIP_MKDOCSTRINGS:
            f.write(
                "*(API docs for this module are temporarily disabled in the "
                "MkDocs build because it has heavy or optional dependencies "
                "at import time.)*\n"
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
# 4. SUMMARY.md with literate nav
# ---------------------------------------------------------------------------
with gen.open(DOCS_PREFIX / "SUMMARY.md", "w") as f:
    f.write("# Python API navigation\n\n")
    # build_literate_nav() returns an iterable of lines; just write them out
    for line in nav.build_literate_nav():
        f.write(line)
