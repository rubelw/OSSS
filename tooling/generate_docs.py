# tooling/generate_docs.py (key parts)

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
}

# Whole subtrees we skip (module_name.startswith(prefix))
SKIP_PREFIXES = (
    "OSSS.ai.api.",   # <- skip all OSSS.ai.api.* modules for mkdocstrings in CI
    "OSSS.ai.orchestration.nodes."
    # add more prefixes here if needed
)


def dotted(mod_path: Path) -> str:
    rel = mod_path.relative_to(SRC_DIR)
    return ".".join(rel.with_suffix("").parts)


def can_import(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def should_skip_for_mkdocstrings(module_name: str) -> bool:
    if module_name in EXPLICIT_SKIP:
        return True
    if any(module_name == p.rstrip(".") or module_name.startswith(p) for p in SKIP_PREFIXES):
        return True
    if not can_import(module_name):
        return True
    return False


nav = Nav()

# ... index + OSSS.md bits above stay the same ...

for py_file in sorted(PKG_DIR.rglob("*.py")):
    if py_file.name == "__init__.py":
        continue

    module_name = dotted(py_file)
    if not module_name.startswith("OSSS"):
        continue

    rel_md_path = py_file.relative_to(PKG_DIR).with_suffix(".md")
    doc_path = DOCS_PREFIX / rel_md_path

    nav_key_parts = tuple(rel_md_path.parts)
    nav[nav_key_parts] = rel_md_path.as_posix()

    with gen.open(doc_path, "w") as f:
        f.write(f"# `{module_name}`\n\n")

        if should_skip_for_mkdocstrings(module_name):
            f.write(
                "*(API docs for this module are disabled in the MkDocs build "
                "because it cannot be safely imported in the docs environment "
                "or is part of an excluded subtree.)*\n"
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


with gen.open(DOCS_PREFIX / "SUMMARY.md", "w") as f:
    f.write("# Python API navigation\n\n")
    f.writelines(nav.build_literate_nav())
