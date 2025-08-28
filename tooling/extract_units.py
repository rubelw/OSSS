#!/usr/bin/env python3
"""
extract_units.py
----------------
Extract a flat list of **units and descriptions** (if present) from an OSSS RBAC JSON file.

By default, this script walks the `hierarchy` recursively and prints CSV with:
    unit, description

It can also extract **positions and descriptions** with `--what positions`.

Usage:
  python extract_units.py /path/to/RBAC.json
  python extract_units.py /path/to/RBAC.json --format json
  python extract_units.py /path/to/RBAC.json --format text
  python extract_units.py /path/to/RBAC.json --what positions --format csv
  python extract_units.py /path/to/RBAC.json --with-path

Notes on schema (robust to missing keys):
- Top-level contains "hierarchy": [ { unit, description?, positions?, children? }, ... ]
- A node's "positions" is a list of { name, description?, ... }
- Unknown shapes are ignored gracefully.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple


def iter_units(node: Dict[str, Any], path: Tuple[str, ...] = ()) -> Iterator[Dict[str, Any]]:
    """Yield units in depth-first order, each as a dict with unit, description, path."""
    unit = node.get("unit")
    desc = node.get("description")
    if isinstance(unit, str) and unit.strip():
        yield {"unit": unit.strip(), "description": desc if isinstance(desc, str) else None, "path": path + (unit.strip(),)}
    # Recurse into children
    for child in node.get("children", []) or []:
        if isinstance(child, dict):
            yield from iter_units(child, path=path + (unit.strip(),) if isinstance(unit, str) and unit.strip() else path)


def iter_positions(node: Dict[str, Any], path: Tuple[str, ...] = ()) -> Iterator[Dict[str, Any]]:
    """Yield positions in depth-first order, each as a dict with name, description, path (including unit chain)."""
    unit = node.get("unit")
    next_path = path + (unit.strip(),) if isinstance(unit, str) and unit.strip() else path

    for pos in node.get("positions", []) or []:
        if isinstance(pos, dict):
            name = pos.get("name")
            desc = pos.get("description")
            if isinstance(name, str) and name.strip():
                yield {"name": name.strip(), "description": desc if isinstance(desc, str) else None, "path": next_path}

    for child in node.get("children", []) or []:
        if isinstance(child, dict):
            yield from iter_positions(child, path=next_path)


def load_rbac(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"Failed to read/parse JSON: {e}")


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract units (or positions) and descriptions from an OSSS RBAC JSON file.")
    ap.add_argument("rbac_file", type=Path, help="Path to RBAC.json")
    ap.add_argument("--what", choices=["units", "positions"], default="units",
                    help="What to extract (default: units)")
    ap.add_argument("--format", "-f", choices=["csv", "json", "text"], default="csv",
                    help="Output format (default: csv)")
    ap.add_argument("--with-path", action="store_true",
                    help="Include the hierarchical path (e.g., top_unit > child_unit)")
    args = ap.parse_args(list(argv) if argv is not None else None)

    if not args.rbac_file.exists():
        ap.error(f"File not found: {args.rbac_file}")

    data = load_rbac(args.rbac_file)
    hierarchy = data.get("hierarchy", [])
    if not isinstance(hierarchy, list):
        hierarchy = []

    if args.what == "units":
        rows = []
        for n in hierarchy:
            if isinstance(n, dict):
                rows.extend(iter_units(n))
        # output
        if args.format == "json":
            out = [
                {"unit": r["unit"], "description": r["description"], **({"path": " > ".join(r["path"])} if args.with_path else {})}
                for r in rows
            ]
            print(json.dumps(out, ensure_ascii=False, indent=2))
        elif args.format == "text":
            for r in rows:
                prefix = (("[" + " > ".join(r["path"]) + "] ") if args.with_path else "")
                print(f"{prefix}{r['unit']}: {r['description'] or ''}".rstrip())
        else:
            # CSV
            writer = csv.writer(sys.stdout)
            header = ["unit", "description"] + (["path"] if args.with_path else [])
            writer.writerow(header)
            for r in rows:
                writer.writerow([r["unit"], r["description"] or ""] + ([" > ".join(r["path"])] if args.with_path else []))

    else:  # positions
        rows = []
        for n in hierarchy:
            if isinstance(n, dict):
                rows.extend(iter_positions(n))
        if args.format == "json":
            out = [
                {"name": r["name"], "description": r["description"], **({"path": " > ".join(r["path"])} if args.with_path else {})}
                for r in rows
            ]
            print(json.dumps(out, ensure_ascii=False, indent=2))
        elif args.format == "text":
            for r in rows:
                prefix = (("[" + " > ".join(r["path"]) + "] ") if args.with_path else "")
                print(f"{prefix}{r['name']}: {r['description'] or ''}".rstrip())
        else:
            writer = csv.writer(sys.stdout)
            header = ["name", "description"] + (["path"] if args.with_path else [])
            writer.writerow(header)
            for r in rows:
                writer.writerow([r["name"], r["description"] or ""] + ([" > ".join(r["path"])] if args.with_path else []))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
