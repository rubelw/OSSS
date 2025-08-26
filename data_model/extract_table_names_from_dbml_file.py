#!/usr/bin/env python3

#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Iterable

# Remove // line comments and /* block */ comments
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.S)
_COMMENT_LINE_RE = re.compile(r"//.*?$", re.M)

# Match: Table <name> [optional settings] { ... }
# <name> can be: unquoted, "double-quoted", `backticked`, or schema.name
_TABLE_RE = re.compile(
    r"""
    \bTable                           # keyword
    \s+
    (                                 # capture name token (with optional quotes)
        "(?P<dquoted>[^"]+)"          # "Name"
        |
        `(?P<bquoted>[^`]+)`          # `Name`
        |
        (?P<raw>[A-Za-z0-9_.]+)       # schema.name or plain
    )
    (?:\s+as\s+[A-Za-z0-9_."`]+)?     # optional 'as Alias'
    (?:\s*\[[^\]]*\])?                # optional [settings: ...]
    \s*\{                             # opening brace of table body
    """,
    re.X | re.I,
)

def _strip_quotes(name: str) -> str:
    # just in case a different bracket sneaks in
    if (name.startswith('"') and name.endswith('"')) or \
       (name.startswith('`') and name.endswith('`')) or \
       (name.startswith('[') and name.endswith(']')):
        return name[1:-1]
    return name

def _preprocess(text: str) -> str:
    text = _COMMENT_BLOCK_RE.sub("", text)
    text = _COMMENT_LINE_RE.sub("", text)
    return text

def iter_table_names(text: str) -> Iterable[str]:
    cleaned = _preprocess(text)
    for m in _TABLE_RE.finditer(cleaned):
        name = m.group("dquoted") or m.group("bquoted") or m.group("raw") or ""
        yield _strip_quotes(name).strip()

def main():
    ap = argparse.ArgumentParser(description="Extract DBML table names")
    ap.add_argument("dbml", type=Path, help="Path to .dbml file")
    ap.add_argument("--json", action="store_true", help="Output as JSON array")
    ap.add_argument("--unique", action="store_true", help="Deduplicate names")
    ap.add_argument("--sort", action="store_true", help="Sort names")
    args = ap.parse_args()

    text = args.dbml.read_text(encoding="utf-8")
    names = list(iter_table_names(text))

    if args.unique:
        names = list(dict.fromkeys(names))  # preserve first-seen order
    if args.sort:
        names = sorted(names, key=str.lower)

    if args.json:
        print(json.dumps(names, indent=2))
    else:
        print("\n".join(names))

if __name__ == "__main__":
    main()
