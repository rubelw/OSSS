#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import json
import csv
import sys

DEFAULT_MODELS_DIR = Path(__file__).resolve().parent / "../../src/OSSS/db/models"

def _class_has_tablename(cls: ast.ClassDef) -> tuple[bool, str | None]:
    tablename = None
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == "__tablename__":
                    if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                        tablename = stmt.value.value
                    elif isinstance(stmt.value, ast.Str):
                        tablename = stmt.value.s
                    return True, tablename
    return False, None

def _class_has_table_args(cls: ast.ClassDef) -> bool:
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id == "__table_args__":
                    return True
    return False

def scan_models_dir(models_dir: Path) -> list[dict]:
    results: list[dict] = []
    for path in sorted(models_dir.glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        try:
            src = path.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except Exception as e:
            results.append({
                "file": str(path),
                "class": None,
                "tablename": None,
                "has_table_args": None,
                "error": str(e),
            })
            continue

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                has_tablename, tablename = _class_has_tablename(node)
                if not has_tablename:
                    continue
                has_table_args = _class_has_table_args(node)
                results.append({
                    "file": str(path),
                    "class": node.name,
                    "tablename": tablename,
                    "has_table_args": has_table_args,
                    "error": None,
                })
    return results

def main():
    ap = argparse.ArgumentParser(description="Find SQLAlchemy models missing __table_args__")
    ap.add_argument("--models-dir", help="Optional path to model .py files (default: ../../src/OSSS/db/models)")
    ap.add_argument("--json", dest="json_out", help="Optional path to write JSON results")
    ap.add_argument("--csv", dest="csv_out", help="Optional path to write CSV results")
    args = ap.parse_args()

    models_dir = Path(args.models_dir) if args.models_dir else DEFAULT_MODELS_DIR
    models_dir = models_dir.resolve()

    if not models_dir.exists():
        print(f"[error] models-dir not found: {models_dir}", file=sys.stderr)
        sys.exit(2)

    results = scan_models_dir(models_dir)
    missing = [r for r in results if r.get("has_table_args") is False]
    total_models = sum(1 for r in results if r.get("has_table_args") is not None)

    print(f"[info] Scanned directory: {models_dir}")
    print(f"[info] Total model classes (with __tablename__): {total_models}")
    print(f"[info] Missing __table_args__: {len(missing)}\n")

    if missing:
        print("Models missing __table_args__:")
        for r in missing:
            print(f" - {r['class']} (table='{r['tablename']}') in {r['file']}")
    else:
        print("No missing __table_args__ found ✅")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"[info] Wrote JSON: {args.json_out}")
    if args.csv_out:
        with open(args.csv_out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["file","class","tablename","has_table_args","error"])
            w.writeheader()
            w.writerows(results)
        print(f"[info] Wrote CSV: {args.csv_out}")

if __name__ == "__main__":
    main()
