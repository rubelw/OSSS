# tooling/generate_all_docs.py
"""
Central entrypoint for all docs generation.

This is the script executed by the mkdocs-gen-files plugin.
It runs all other generator scripts (Python API, AI index, OpenAPI page, etc.)
inside the MkDocs/mkdocs-gen-files environment.
"""

from __future__ import annotations

from pathlib import Path
import runpy


def run_if_exists(path: Path) -> None:
    """Run a Python script at `path` if it exists."""
    if path.is_file():
        runpy.run_path(path)


def main() -> None:
    root = Path(__file__).resolve().parent  # /tooling

    # Core Python API docs (your generate_docs.py)
    run_if_exists(root / "generate_docs.py")

    # Optional: AI index generator (if you add it)
    run_if_exists(root / "generate_ai_index.py")

    # Optional: OpenAPI or REST docs generator
    run_if_exists(root / "generate_openapi_page.py")


if __name__ == "__main__":
    main()
