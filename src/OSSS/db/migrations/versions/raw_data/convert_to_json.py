#!/usr/bin/env python3

import ast
import json
import re
from pathlib import Path

SOURCE_FILE = Path("gl_accounts.py")
OUTPUT_FILE = Path("seed_rows.json")

# Read file as raw text
text = SOURCE_FILE.read_text(encoding="utf-8")

# Extract the list literal: SEED_ROWS = [...]
match = re.search(r"SEED_ROWS\s*=\s*(\[\s*.*?\s*\])", text, re.DOTALL)
if not match:
    raise RuntimeError("Could not find SEED_ROWS = [...] in file")

list_source = match.group(1)

# Convert text → Python list safely
seed_rows = ast.literal_eval(list_source)

# Write JSON
OUTPUT_FILE.write_text(
    json.dumps(seed_rows, indent=2),
    encoding="utf-8"
)

print(f"Wrote {OUTPUT_FILE}")

