#!/usr/bin/env python3
from __future__ import annotations
"""
inject_table_args.py

Add or update __table_args__ on SQLAlchemy models to include a human-readable comment
containing a table description and the school positions that most commonly use the data.

- Safe & idempotent: backs up each changed file as "<name>.bak"
- Only touches classes that define __tablename__ (likely ORM models)
- Works with SQLAlchemy 2.x declarative models using mapped_column or legacy Column
- Accepts a mapping JSON (see table_comments.json) keyed by table name

Usage:
  python inject_table_args.py --models-dir /path/to/src/OSSS/db/models \
                              --mapping table_comments.json \
                              --write
"""
import argparse, ast, json, textwrap, zipfile
from pathlib import Path

def load_mapping(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def build_comment(desc: str, positions: list[str]) -> str:
    pos = ", ".join(sorted(set(positions)))
    return f"{desc}\n\nUsed by positions: {pos}"

class Editor(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, dict]):
        super().__init__()
        self.mapping = mapping
        self.changed = False

    def visit_ClassDef(self, node: ast.ClassDef):
        tablename = None
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and t.id == "__tablename__":
                        if isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                            tablename = stmt.value.value
                        elif isinstance(stmt.value, ast.Str):
                            tablename = stmt.value.s
        if not tablename:
            return node

        meta = self.mapping.get(tablename, self.mapping.get("__default__", {}))
        desc = meta.get("description", "OSSS table.")
        positions = meta.get("positions", [])
        comment_text = build_comment(desc, positions)

        found_args = None
        found_kwargs = None
        found_idx = None
        for i, stmt in enumerate(node.body):
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and t.id == "__table_args__":
                        found_idx = i
                        if isinstance(stmt.value, ast.Dict):
                            found_kwargs = stmt.value
                        elif isinstance(stmt.value, (ast.Tuple, ast.List)):
                            for el in stmt.value.elts[::-1]:
                                if isinstance(el, ast.Dict):
                                    found_kwargs = el
                                    break
                            found_args = stmt.value
                        elif isinstance(stmt.value, ast.Constant) and stmt.value.value is None:
                            found_kwargs = None
                        break

        comment_key = ast.Constant(value="comment")
        comment_val = ast.Constant(value=comment_text)

        def ensure_kwargs_dict():
            nonlocal found_kwargs, found_args
            if found_kwargs is None:
                found_kwargs = ast.Dict(keys=[comment_key], values=[comment_val])
                if found_args is None:
                    return ast.Assign(targets=[ast.Name(id="__table_args__", ctx=ast.Store())], value=found_kwargs)
                else:
                    found_args.elts.append(found_kwargs)
                    return None
            else:
                keys = found_kwargs.keys
                vals = found_kwargs.values
                for ix, k in enumerate(keys):
                    if isinstance(k, ast.Constant) and k.value == "comment":
                        vals[ix] = comment_val
                        return None
                keys.append(comment_key)
                vals.append(comment_val)
                return None

        if found_idx is None:
            replace_stmt = ast.Assign(
                targets=[ast.Name(id="__table_args__", ctx=ast.Store())],
                value=ast.Dict(keys=[comment_key], values=[comment_val]),
            )
            insert_pos = 0
            for j, s in enumerate(node.body):
                if isinstance(s, ast.Assign):
                    for t in s.targets:
                        if isinstance(t, ast.Name) and t.id == "__tablename__":
                            insert_pos = j + 1
                            break
            node.body.insert(insert_pos, replace_stmt)
            self.changed = True
        else:
            rep = ensure_kwargs_dict()
            if rep is not None:
                node.body[found_idx] = rep
            self.changed = True
        return node

def process_file(path: Path, mapping: dict) -> bool:
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    ed = Editor(mapping)
    new_tree = ed.visit(tree)
    ast.fix_missing_locations(new_tree)
    if not ed.changed:
        return False
    new_src = ast.unparse(new_tree)
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        backup.write_text(src, encoding="utf-8")
    path.write_text(new_src, encoding="utf-8")
    return True

def main():
    ap = argparse.ArgumentParser(description="Inject __table_args__ comments into SQLAlchemy models")
    ap.add_argument("--models-dir", required=True, help="Path to model .py files (e.g., src/OSSS/db/models)")
    ap.add_argument("--mapping", required=True, help="JSON mapping of table_name → {description, positions}")
    ap.add_argument("--write", action="store_true", help="Actually write files (default: dry-run)")
    args = ap.parse_args()

    models_dir = Path(args.models_dir)
    mapping = load_mapping(Path(args.mapping))
    changed = []

    for path in sorted(models_dir.glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        if not args.write:
            try:
                src = path.read_text(encoding="utf-8")
                tree = ast.parse(src)
                ed = Editor(mapping)
                ed.visit(tree)
                if ed.changed:
                    changed.append(str(path))
            except Exception:
                continue
        else:
            try:
                if process_file(path, mapping):
                    changed.append(str(path))
            except Exception as e:
                print(f"[warn] failed to process {path}: {e}")

    if not changed:
        print("[info] No files needed changes")
        return

    print("[info] Changed files:")
    for p in changed:
        print(" -", p)

    out_zip = Path("changed_models_with_table_args.zip")
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in changed:
            z.write(p, arcname=Path(p).name)
    print(f"[info] Wrote {out_zip}")

if __name__ == "__main__":
    main()
