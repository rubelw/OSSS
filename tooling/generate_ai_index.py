#!/usr/bin/env python3

# tooling/generate_ai_index.py
from pathlib import Path
import mkdocs_gen_files as gen

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
AI_AGENTS = SRC_DIR / "OSSS" / "ai" / "agents"

with gen.open("ai/index.md", "w") as f:
    f.write("# OSSS AI Overview\n\n")
    f.write("This page is auto-generated from `src/OSSS/ai/agents`.\n\n")

    for path in sorted(AI_AGENTS.glob("*.py")):
        if path.name == "__init__.py":
            continue
        name = path.stem
        f.write(f"- [`{name}`](../api/python/ai/agents/{name}.md)\n")
