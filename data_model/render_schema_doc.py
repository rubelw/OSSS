#!/usr/bin/env python3

# scripts/render_schema_doc.py
import json
from pathlib import Path

SCHEMA_PATH = "schema.json"
OUT_PATH = "schema_doc.md"

# You can hard-code domain synonyms for key tables:
TABLE_SYNONYMS = {
    "consents": ["consent", "parent consent", "permissions", "approval"],
    "students": ["student", "learner", "pupil"],
    # ...
}

def table_block(name: str, tbl: dict) -> str:
    synonyms = TABLE_SYNONYMS.get(name, [])
    syn_line = f"Synonyms: {', '.join(synonyms)}" if synonyms else ""

    lines = [
        f"TABLE: {name}",
        f"DESCRIPTION: {tbl.get('note') or 'No description provided.'}",
    ]
    if syn_line:
        lines.append(syn_line)

    lines.append("KEY COLUMNS:")
    for col in tbl["columns"]:
        col_desc = col.get("note") or ""
        flags = []
        if col["pk"]:
            flags.append("PK")
        if col["not_null"]:
            flags.append("NOT NULL")
        if col["unique"]:
            flags.append("UNIQUE")
        flag_str = f" ({', '.join(flags)})" if flags else ""
        lines.append(f"- {col['name']} : {col['type']}{flag_str} {col_desc}")

    lines.append("")  # blank line
    return "\n".join(lines)

def main():
    schema = json.loads(Path(SCHEMA_PATH).read_text())
    blocks = [table_block(name, tbl) for name, tbl in schema.items()]
    doc = "# OSSS Database Schema Reference\n\n" + "\n".join(blocks)
    Path(OUT_PATH).write_text(doc)
    print(f"Wrote {OUT_PATH}")

if __name__ == "__main__":
    main()
