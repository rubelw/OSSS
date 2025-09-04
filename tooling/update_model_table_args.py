#!/usr/bin/env python3
"""
Update SQLAlchemy model files so that, for each table in the provided JSON,
the model's __table_args__ includes a SQL 'comment' and an 'info': {'description': ...}.

Fix: regex patterns are raw strings with *single* backslashes (no over-escaping).
"""

import json
import re
import sys
from pathlib import Path
from datetime import datetime

DEFAULT_MODELS_DIR = Path(__file__).resolve().parent / ".." / "src" / "OSSS" / "db" / "models"

# --- Regexes (note the single backslashes; these are raw strings) ---
RE_TABLENAME = re.compile(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]")
RE_TABLE_CALL = re.compile(r"Table\s*\(\s*['\"]([^'\"]+)['\"]\s*,")
RE_CLASS_DEF = re.compile(r"^class\s+\w+\s*\(.*?\):", re.MULTILINE)
RE_TABLE_ARGS_ASSIGN = re.compile(r"^\s*__table_args__\s*=\s*(.+)$", re.MULTILINE)

def load_mapping(json_path: Path) -> dict:
    """
    Accepts either:
      - { "<table_name>": { "description": "..." , ... }, ... }
      - [ { "table": "...", "description": "..." }, ... ]
    Returns {table_name: description}
    """
    data = json.loads(json_path.read_text(encoding="utf-8"))
    mapping = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                desc = (v.get("description") or "").strip()
                if desc:
                    mapping[k] = desc
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            t = item.get("table") or item.get("table_name")
            d = (item.get("description") or "").strip()
            if t and d:
                mapping[t] = d
    return mapping

def find_table_name(src: str) -> str | None:
    m = RE_TABLENAME.search(src)
    if m:
        return m.group(1)
    m2 = RE_TABLE_CALL.search(src)
    if m2:
        return m2.group(1)
    return None

def _escape(s: str) -> str:
    return s.replace("'", "\\'")

def _ensure_info_description_in_dict_literal(dict_lit: str, description: str) -> str:
    """
    Given a Python dict literal as a string, ensure it contains:
      - 'comment': '<description>'
      - 'info': {'description': '<description>'}
    """
    has_comment = re.search(r"[{,]\s*['\"]comment['\"]\s*:", dict_lit) is not None
    has_info = re.search(r"[{,]\s*['\"]info['\"]\s*:", dict_lit) is not None

    inner = dict_lit.strip()
    if inner == "{}":
        return "{'comment': '%s', 'info': {'description': '%s'}}" % (_escape(description), _escape(description))

    # Add or replace 'comment'
    if has_comment:
        dict_lit = re.sub(
            r"(['\"]comment['\"]\s*:\s*)['\"][^'\"]*['\"]",
            lambda m: f"{m.group(1)}'{_escape(description)}'",
            dict_lit,
            count=1,
        )
    else:
        dict_lit = re.sub(
            r"^\s*\{",
            "{'comment': '%s'," % _escape(description),
            dict_lit,
            count=1,
        )

    # Add or replace 'info': {'description': ...}
    if has_info:
        info_desc_re = re.compile(r"(['\"]info['\"]\s*:\s*\{[^}]*?)(['\"]description['\"]\s*:\s*)['\"][^'\"]*['\"]", re.DOTALL)
        if info_desc_re.search(dict_lit):
            dict_lit = info_desc_re.sub(lambda m: f"{m.group(1)}{m.group(2)}'{_escape(description)}'", dict_lit, count=1)
        else:
            dict_lit = re.sub(
                r"(['\"]info['\"]\s*:\s*\{)",
                r"\1'description': '%s', " % _escape(description),
                dict_lit,
                count=1,
            )
    else:
        dict_lit = re.sub(
            r"\}\s*$",
            ", 'info': {'description': '%s'}}" % _escape(description),
            dict_lit,
            count=1,
        )

    return dict_lit

def update_or_insert_table_args(class_src: str, description: str) -> tuple[str, bool]:
    m = RE_TABLE_ARGS_ASSIGN.search(class_src)
    if not m:
        # Insert after __tablename__ line
        tab_m = RE_TABLENAME.search(class_src)
        if not tab_m:
            return class_src, False
        insert_pos = class_src.find("\n", tab_m.end())
        if insert_pos == -1:
            insert_pos = len(class_src)
        insertion = f"\n    __table_args__ = {{'comment': '{_escape(description)}', 'info': {{'description': '{_escape(description)}'}}}}\n"
        new_class_src = class_src[:insert_pos+1] + insertion + class_src[insert_pos+1:]
        return new_class_src, True

    # Right-hand side of the assignment
    rhs = m.group(1).strip()

    if rhs.startswith("{"):
        new_dict = _ensure_info_description_in_dict_literal(rhs, description)
        new_line = class_src[m.start():m.end()].replace(rhs, new_dict)
        class_src = class_src[:m.start()] + new_line + class_src[m.end():]
        return class_src, True

    if rhs.startswith("("):
        tuple_body = rhs[1:-1]
        dict_match = re.search(r"\{.*\}\s*$", tuple_body, re.DOTALL)
        if dict_match:
            dict_lit = dict_match.group(0)
            updated_dict = _ensure_info_description_in_dict_literal(dict_lit, description)
            new_rhs = rhs[:1] + tuple_body[:dict_match.start()] + updated_dict + ")"
        else:
            comma = "" if tuple_body.strip() == "" else ", "
            new_rhs = f"({tuple_body}{comma}{{'comment': '{_escape(description)}', 'info': {{'description': '{_escape(description)}'}}}})"
        new_line = class_src[m.start():m.end()].replace(rhs, new_rhs)
        class_src = class_src[:m.start()] + new_line + class_src[m.end():]
        return class_src, True

    # Fallback: replace entire RHS
    new_rhs = "{'comment': '%s', 'info': {'description': '%s'}}" % (_escape(description), _escape(description))
    new_line = class_src[m.start():m.end()].replace(rhs, new_rhs)
    class_src = class_src[:m.start()] + new_line + class_src[m.end():]
    return class_src, True

def split_classes(src: str):
    spans = []
    for m in RE_CLASS_DEF.finditer(src):
        spans.append((m.start(), m.end()))
    if not spans:
        return
    for i, (s, e) in enumerate(spans):
        end = spans[i+1][0] if i+1 < len(spans) else len(src)
        yield s, end, src[s:end]

def process_file(py_path: Path, table_to_desc: dict) -> tuple[bool, str]:
    src = py_path.read_text(encoding="utf-8")
    # Derive table from __tablename__ or Table("name", ...)
    m = RE_TABLENAME.search(src)
    table = m.group(1) if m else None
    if not table:
        m2 = RE_TABLE_CALL.search(src)
        table = m2.group(1) if m2 else None
    if not table:
        return False, src

    desc = table_to_desc.get(table)
    if not desc:
        return False, src

    changed_any = False
    updated_blocks = []
    for s, e, block in split_classes(src) or []:
        if f"__tablename__ = '{table}'" not in block and f"__tablename__ = \"{table}\"" not in block:
            updated_blocks.append((s, e, block))
            continue
        new_block, changed = update_or_insert_table_args(block, desc)
        changed_any = changed_any or changed
        updated_blocks.append((s, e, new_block))

    new_src = src
    if changed_any:
        pieces = []
        last = 0
        for s, e, block in updated_blocks:
            pieces.append(src[last:s])
            pieces.append(block)
            last = e
        pieces.append(src[last:])
        new_src = "".join(pieces)

    return changed_any, new_src

def main():
    if len(sys.argv) < 2:
        print("Usage: update_model_table_args.py <json_file> [--models-dir DIR] [--dry-run]")
        sys.exit(2)

    json_file = Path(sys.argv[1])
    models_dir = DEFAULT_MODELS_DIR
    dry_run = False

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--dry-run":
            dry_run = True
            i += 1
        elif arg == "--models-dir" and i + 1 < len(sys.argv):
            models_dir = Path(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    # Load mapping
    data = json.loads(json_file.read_text(encoding="utf-8"))
    table_to_desc = {}
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                d = (v.get("description") or "").strip()
                if d:
                    table_to_desc[k] = d
    elif isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            t = item.get("table") or item.get("table_name")
            d = (item.get("description") or "").strip()
            if t and d:
                table_to_desc[t] = d

    if not table_to_desc:
        print("No descriptions found in JSON; nothing to do.")
        return

    backups_dir = Path(__file__).resolve().parent / f"_backups_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not dry_run:
        backups_dir.mkdir(exist_ok=True)

    scanned = 0
    changed = 0
    for py_file in models_dir.rglob("*.py"):
        scanned += 1
        try:
            did_change, new_src = process_file(py_file, table_to_desc)
        except Exception as e:
            print(f"ERROR processing {py_file}: {e}")
            continue
        if did_change:
            if dry_run:
                print(f"[DRY-RUN] Would update {py_file}")
            else:
                try:
                    (backups_dir / py_file.name).write_text(py_file.read_text(encoding='utf-8'), encoding='utf-8')
                    py_file.write_text(new_src, encoding='utf-8')
                    changed += 1
                    print(f"Updated {py_file}")
                except Exception as e:
                    print(f"ERROR writing {py_file}: {e}")

    print(f"Scanned files: {scanned}, Updated files: {changed}")
    if dry_run:
        print("Dry run only; no files were modified.")

if __name__ == "__main__":
    main()
