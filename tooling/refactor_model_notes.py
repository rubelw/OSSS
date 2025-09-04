#!/usr/bin/env python3
"""
Rewrite SQLAlchemy model classes that use:

    note: str = 'owner=...; description=...'
    __tablename__ = "..."
    __table_args__ = {'comment': '...', 'info': {'description': '...'}}

into:

    __tablename__ = "..."
    __allow_unmapped__ = True
    NOTE: ClassVar[str] = ( "owner=...; " "description=... " ... )
    __table_args__ = {"comment": (...), "info": {"note": NOTE, "description": (...)}}

It preserves indentation, keeps the same tablename, and pulls the description
from the existing __table_args__['comment'] (or info['description'] fallback).

Usage:
  python refactor_notes.py --root src/OSSS/db/models --write
  python refactor_notes.py --root src/OSSS/db/models        # dry-run (default)
"""

from __future__ import annotations

import argparse
import ast
import os
from pathlib import Path
from typing import Optional, Tuple, List

# ---------- helpers for source positions ----------

def _linecol_to_index(src: str, line: int, col: int) -> int:
    """Translate (1-based line, 0-based col) to absolute index into src."""
    if line <= 1:
        return col
    lines = src.splitlines(keepends=True)
    return sum(len(l) for l in lines[: line - 1]) + col


def _get_src_segment(src: str, node: ast.AST) -> Tuple[int, int]:
    """Return (start_index, end_index) for a node in source."""
    start = _linecol_to_index(src, node.lineno, node.col_offset)  # type: ignore[attr-defined]
    end = _linecol_to_index(src, node.end_lineno, node.end_col_offset)  # type: ignore[attr-defined]
    return start, end


def _escape_double_quotes(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _to_multiline_concat(s: str, indent: str, inner_indent: str = "    ") -> str:
    """
    Turn a long string into a pretty parenthesized multi-line concatenation:

    NOTE: ClassVar[str] = (
        "part1 "
        "part2 "
        "part3"
    )

    We split on '; ' first to make a nice first line for owner=...; then break the
    rest by '. ' to keep sentences readable. This is cosmetic; content is unchanged.
    """
    s = s.strip()
    if "; " in s:
        first, rest = s.split("; ", 1)
        pieces: List[str] = [first + "; "]
    else:
        rest = s
        pieces = []

    # split remaining into sentences by ". "
    while rest:
        dot = rest.find(". ")
        if dot == -1:
            pieces.append(rest)
            break
        pieces.append(rest[: dot + 2])
        rest = rest[dot + 2 :]

    pieces = [ _escape_double_quotes(p) for p in pieces if p ]

    out = f"{indent}(\n"
    for p in pieces:
        out += f'{indent}{inner_indent}"{p}"\n'
    out += f"{indent})"
    return out


# ---------- import editing ----------

def ensure_classvar_import(src: str) -> Tuple[str, bool]:
    """Ensure 'from typing import ClassVar' is present (or appended to an existing typing import)."""
    if "from typing import ClassVar" in src:
        return src, False

    lines = src.splitlines()
    changed = False

    # Try to append to an existing single-line 'from typing import ...'
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("from typing import ") and "(" not in stripped:
            if "ClassVar" not in stripped:
                lines[i] = line + (", ClassVar" if not line.rstrip().endswith(",") else " ClassVar")
                changed = True
                break

    if not changed:
        # Insert a new import after the last import block (after __future__ too)
        insert_at = 0
        for i, line in enumerate(lines):
            s = line.strip()
            if s.startswith("from __future__ import"):
                insert_at = i + 1
            elif s.startswith("import ") or s.startswith("from "):
                insert_at = i + 1
        lines.insert(insert_at, "from typing import ClassVar")
        changed = True

    return "\n".join(lines) + ("\n" if not src.endswith("\n") else ""), True


# ---------- core transformation ----------

def transform_class_block(
    src: str, cls: ast.ClassDef
) -> Optional[Tuple[int, int, str]]:
    """
    If the class contains 'note: str = ...', '__tablename__', and '__table_args__'
    in the expected simple literal forms, return a replacement tuple:
    (start_index_of_note, end_index_of_table_args, new_block_text)
    """
    # quick skip if already converted
    class_text = src[_linecol_to_index(src, cls.lineno, 0) : _linecol_to_index(src, cls.end_lineno, 0)]  # type: ignore[attr-defined]
    if "NOTE: ClassVar[str]" in class_text or "__allow_unmapped__" in class_text:
        return None

    note_node: Optional[ast.AnnAssign] = None
    tablename_node: Optional[ast.Assign] = None
    tableargs_node: Optional[ast.Assign] = None

    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id == "note":
                note_node = stmt
        elif isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    if t.id == "__tablename__":
                        tablename_node = stmt
                    elif t.id == "__table_args__":
                        tableargs_node = stmt

    if not (note_node and tablename_node and tableargs_node):
        return None

    # literal values
    try:
        note_text: str = ast.literal_eval(note_node.value) if note_node.value is not None else ""  # type: ignore[arg-type]
        tablename: str = ast.literal_eval(tablename_node.value)  # type: ignore[arg-type]
        table_args_val = ast.literal_eval(tableargs_node.value)  # type: ignore[arg-type]
    except Exception:
        # non-literal, skip
        return None

    # pull description from __table_args__
    description = None
    if isinstance(table_args_val, dict):
        if isinstance(table_args_val.get("comment"), str):
            description = table_args_val["comment"]
        else:
            info = table_args_val.get("info")
            if isinstance(info, dict) and isinstance(info.get("description"), str):
                description = info["description"]
    if not isinstance(description, str) or not description.strip():
        # fallback: try to extract after 'description=' inside note
        desc_from_note = note_text.split("description=", 1)
        if len(desc_from_note) == 2:
            description = desc_from_note[1].strip()
        else:
            description = note_text.strip()

    # indentation based on existing tablename line
    indent = " " * tablename_node.col_offset  # type: ignore[attr-defined]

    # build new block
    note_ml = _to_multiline_concat(note_text, indent)
    desc_ml_for_comment = _to_multiline_concat(description, indent + "    ")

    new_block = []
    new_block.append(f'{indent}__tablename__ = "{tablename}"')
    new_block.append(f"{indent}__allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper")
    new_block.append("")
    new_block.append(f"{indent}NOTE: ClassVar[str] = {note_ml}")
    new_block.append("")
    new_block.append(f"{indent}__table_args__ = {{")
    new_block.append(f'{indent}    "comment": {desc_ml_for_comment},')
    new_block.append(f'{indent}    "info": {{')
    new_block.append(f'{indent}        "note": NOTE,')
    new_block.append(f'{indent}        "description": {desc_ml_for_comment},')
    new_block.append(f"{indent}    }},")
    new_block.append(f"{indent}}}")
    new_block.append("")

    start, _ = _get_src_segment(src, note_node)
    _, end = _get_src_segment(src, tableargs_node)
    return start, end, "\n".join(new_block)


def transform_file(path: Path, write: bool = False) -> Tuple[bool, str]:
    """
    Returns (changed, message). If write is False, performs dry-run.
    """
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return False, f"[skip] {path}: SyntaxError: {e}"

    edits: List[Tuple[int, int, str]] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            repl = transform_class_block(text, node)
            if repl:
                edits.append(repl)

    if not edits:
        return False, f"[ok]   {path}: no matching classes"

    # apply edits from end to start to keep offsets valid
    edits.sort(key=lambda x: x[0], reverse=True)
    new_text = text
    for start, end, replacement in edits:
        new_text = new_text[:start] + replacement + new_text[end:]

    # ensure ClassVar import
    new_text, import_changed = ensure_classvar_import(new_text)

    if write:
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            return True, f"[write] {path}: {len(edits)} class(es) updated" + (" + import" if import_changed else "")
        else:
            return False, f"[ok]   {path}: no changes after processing"
    else:
        # dry-run message
        return True, f"[dry]  {path}: would update {len(edits)} class(es)" + (" + add import" if import_changed else "")


def main():
    ap = argparse.ArgumentParser(description="Refactor model NOTE/__table_args__ blocks to ClassVar NOTE style.")
    ap.add_argument("--root", type=Path, default=Path("../src/OSSS/db/models"), help="Directory to scan for .py model files")
    ap.add_argument("--write", action="store_true", help="Apply changes (default is dry-run)")
    ap.add_argument("--include", nargs="*", default=["*.py"], help="Glob(s) to include (default: *.py)")
    ap.add_argument("--exclude", nargs="*", default=["__init__.py"], help="Filename(s) to exclude")
    args = ap.parse_args()

    root: Path = args.root
    if not root.exists():
        print(f"Root does not exist: {root}")
        return

    changed_any = False
    for pat in args.include:
        for p in sorted(root.rglob(pat)):
            if p.name in args.exclude or p.is_dir():
                continue
            changed, msg = transform_file(p, write=args.write)
            print(msg)
            changed_any = changed_any or changed

    if not args.write:
        print("\nDRY RUN complete. Re-run with --write to apply changes.")


if __name__ == "__main__":
    main()
