#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path
from datetime import datetime

MODELS_DIR = Path(__file__).resolve().parent / ".." / "src" / "OSSS" / "db" / "models"

# Regexes to detect table names and to find/replace 'note' fields
RE_TABLENAME = re.compile(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]")
RE_TABLE_CALL = re.compile(r"Table\s*\(\s*['\"]([^'\"]+)['\"]\s*,")
# Note patterns
RE_NOTE_COL_ASSIGN = re.compile(r"^\s*note\s*=\s*Column\([^)]*\)", re.MULTILINE)
RE_NOTE_FIELD_ASSIGN = re.compile(r"^\s*note\s*:\s*[^=]+=\s*Field\([^)]*\)", re.MULTILINE)
RE_NOTE_SIMPLE_ASSIGN = re.compile(r"^\s*note\s*:\s*[^=]+\s*=\s*['\"][^'\"]*['\"]", re.MULTILINE)
RE_NOTE_PLAIN_ASSIGN = re.compile(r"^\s*note\s*=\s*['\"][^'\"]*['\"]", re.MULTILINE)

def load_mapping(json_path: Path):
    data = json.loads(json_path.read_text(encoding='utf-8'))
    mapping = {}
    if isinstance(data, dict):
        # Dict keyed by table name
        for k, v in data.items():
            if not isinstance(v, dict):
                continue
            desc = (v.get("description") or "").strip()
            owner = v.get("departments")
            if owner is None:
                owner = v.get("owner")
            mapping[k] = {"description": desc, "data_ownership": owner}
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            t = item.get("table") or item.get("table_name")
            if not t:
                continue
            desc = (item.get("description") or "").strip()
            owner = item.get("departments") or item.get("owner")
            mapping[t] = {"description": desc, "data_ownership": owner}

    print('mapping: '+str(mapping))
    return mapping

def normalize_owner(owner):
    if isinstance(owner, list):
        return " | ".join(str(x).strip() for x in owner if str(x).strip())
    return str(owner or "").strip()

def compose_note(owner, description):
    o = normalize_owner(owner)
    d = (description or "").strip()
    return f"owner={o}; description={d}" if (o or d) else ""

def detect_table_name(py_src: str):
    m = RE_TABLENAME.search(py_src)
    if m:
        return m.group(1)
    m = RE_TABLE_CALL.search(py_src)
    if m:
        return m.group(1)
    return None

def replace_or_insert_note(py_src: str, note_value: str):
    replaced = False

    if RE_NOTE_COL_ASSIGN.search(py_src):
        py_src = RE_NOTE_COL_ASSIGN.sub(f"    note = '{note_value}'", py_src)
        replaced = True

    if RE_NOTE_FIELD_ASSIGN.search(py_src):
        py_src = RE_NOTE_FIELD_ASSIGN.sub(f"    note: str = '{note_value}'", py_src)
        replaced = True

    if RE_NOTE_SIMPLE_ASSIGN.search(py_src):
        py_src = RE_NOTE_SIMPLE_ASSIGN.sub(f"    note: str = '{note_value}'", py_src)
        replaced = True

    if RE_NOTE_PLAIN_ASSIGN.search(py_src):
        py_src = RE_NOTE_PLAIN_ASSIGN.sub(f"    note = '{note_value}'", py_src)
        replaced = True

    if replaced:
        return py_src, True

    # Insert after first class declaration
    class_match = re.search(r"^class\s+\w+\s*\([^)]*\)\s*:\s*$", py_src, re.MULTILINE)
    if class_match:
        insert_at = class_match.end()
        insertion = f"\n    note: str = '{note_value}'\n"
        return py_src[:insert_at] + insertion + py_src[insert_at:], True

    # Fallback: append at end
    return py_src + f"\n\n# Injected note field\nnote = '{note_value}'\n", True

def main():
    if len(sys.argv) < 2:
        print("Usage: python update_model_notes.py <mapping_json_path> [--dry-run]")
        sys.exit(1)

    mapping_json = Path(sys.argv[1]).resolve()
    dry_run = "--dry-run" in sys.argv

    if not mapping_json.exists():
        print(f"ERROR: mapping JSON not found: {mapping_json}")
        sys.exit(2)

    mapping = load_mapping(mapping_json)
    if not mapping:
        print("ERROR: could not load a table->(description, data_ownership) mapping from the JSON.")
        sys.exit(3)

    models_dir = MODELS_DIR.resolve()
    if not models_dir.exists():
        print(f"ERROR: models directory not found: {models_dir}")
        sys.exit(4)

    backups_dir = models_dir / ("_backups_notes_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    if not dry_run:
        backups_dir.mkdir(parents=True, exist_ok=True)

    changed = 0
    scanned = 0

    for py_file in models_dir.glob("*.py"):
        try:
            src = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        scanned += 1
        table = detect_table_name(src)
        if not table:
            continue

        info = mapping.get(table)
        if not info:
            continue

        note_val = compose_note(info.get('data_ownership'), info.get('description'))
        if not note_val:
            continue

        new_src, did = replace_or_insert_note(src, note_val)
        if did and (new_src != src):
            changed += 1
            if dry_run:
                print(f"[DRY-RUN] Would update {py_file.name} (table={table}) with note='{note_val[:80]}...'")
            else:
                # Backup and write
                try:
                    (backups_dir / py_file.name).write_text(src, encoding="utf-8")
                    py_file.write_text(new_src, encoding="utf-8")
                    print(f"Updated {py_file.name} (table={table})")
                except Exception as e:
                    print(f"ERROR writing {py_file}: {e}")



    print(f"Scanned files: {scanned}, Updated files: {changed}")
    if dry_run:
        print("Dry run only; no files were modified.")

if __name__ == "__main__":
    main()
