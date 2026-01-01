# tooling/generate_docs.py

from pathlib import Path
import importlib

import mkdocs_gen_files as gen
from mkdocs_gen_files.nav import Nav

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
PKG_DIR = SRC_DIR / "OSSS"
DOCS_PREFIX = Path("api/python")

# Optional: explicit skip list for things you KNOW you never want mkdocstrings to touch
EXPLICIT_SKIP = {
    "OSSS.schemas",
    "OSSS.agents.metagpt_agent",
    # keep adding here if you want permanent skips
}


def dotted(mod_path: Path) -> str:
    rel = mod_path.relative_to(SRC_DIR)
    return ".".join(rel.with_suffix("").parts)


def can_import(module_name: str) -> bool:
    """
    Try to import a module. If it fails, we treat it as 'not safe' for mkdocstrings.

    This prevents mkdocstrings from blowing up on modules that need extra deps or env.
    """
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


nav = Nav()

# ---------------------------------------------------------------------------
# 1. Root index page
# ---------------------------------------------------------------------------
with gen.open(DOCS_PREFIX / "index.md", "w") as f:
    f.write("# Python API\n\n")
    f.write("Auto-generated API reference for the `OSSS` backend package.\n\n")
    f.write("- [Package Reference](./OSSS.md)\n")
    f.write("- [Module Navigation](./SUMMARY.md)\n")

# ---------------------------------------------------------------------------
# 2. Top-level OSSS package page
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

nav["OSSS"] = "OSSS.md"

# ---------------------------------------------------------------------------
# 3. One page per module under src/OSSS
# ---------------------------------------------------------------------------
for py_file in sorted(PKG_DIR.rglob("*.py")):
    if py_file.name == "__init__.py":
        continue

    module_name = dotted(py_file)
    if not module_name.startswith("OSSS"):
        continue

    rel_md_path = py_file.relative_to(PKG_DIR).with_suffix(".md")
    doc_path = DOCS_PREFIX / rel_md_path

    # nav key and link path are relative to DOCS_PREFIX
    nav_key_parts = tuple(rel_md_path.parts)
    nav[nav_key_parts] = rel_md_path.as_posix()

    with gen.open(doc_path, "w") as f:
        f.write(f"# `{module_name}`\n\n")

        # Decide whether to use mkdocstrings for this module
        if module_name in EXPLICIT_SKIP or not can_import(module_name):
            # Just write a placeholder, no ::: directive
            f.write(
                "*(API docs for this module are disabled in the MkDocs build "
                "because it cannot be safely imported in the docs environment.)*\n"
            )
        else:
            # Normal mkdocstrings directive
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
    f.writelines(nav.build_literate_nav())
