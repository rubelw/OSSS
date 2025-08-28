#!/usr/bin/env python3
"""
extract_positions.py
--------------------
Read an OSSS RBAC JSON file and print a flat list of all position names found
(recursively) under every unit's `positions` array.

Usage:
  python extract_positions.py /path/to/RBAC.json
  python extract_positions.py /path/to/RBAC.json --format json
  python extract_positions.py /path/to/RBAC.json --format csv --no-unique

Notes:
- The script expects a top-level "hierarchy" list, where each item may contain:
    - "unit": str
    - "positions": [ { "name": str, ... }, ... ]
    - "children": [ ... nested units ... ]
- It is resilient to missing keys; unknown shapes are ignored.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Iterator, List, Dict, Any

def iter_positions(node: Dict[str, Any]) -> Iterator[str]:
    """
    Yield position names in the current node and all nested children.
    """
    # Positions on this node
    for pos in node.get("positions", []) or []:
        name = pos.get("name")
        if isinstance(name, str) and name.strip():
            yield name.strip()

    # Recurse into children
    for child in node.get("children", []) or []:
        if isinstance(child, dict):
            yield from iter_positions(child)

def collect_positions(data: Dict[str, Any], unique: bool = True) -> List[str]:
    """
    Traverse the RBAC structure and return a list of position names.
    If `unique` is True, de-duplicate while preserving first-seen order.
    """
    positions: List[str] = []
    seen = set()

    # Top-level "hierarchy" can be a list of units
    hierarchy = data.get("hierarchy", [])
    if not isinstance(hierarchy, list):
        hierarchy = []

    for unit in hierarchy:
        if isinstance(unit, dict):
            for name in iter_positions(unit):
                if unique:
                    if name not in seen:
                        positions.append(name)
                        seen.add(name)
                else:
                    positions.append(name)

    return positions

def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Extract position names from an OSSS RBAC JSON file.")
    p.add_argument("rbac_file", type=Path, help="Path to RBAC.json")
    p.add_argument("--format", "-f", choices=["text", "json", "csv"], default="text",
                   help="Output format (default: text = one name per line)")
    p.add_argument("--no-unique", action="store_true", help="Do not de-duplicate names")
    args = p.parse_args(list(argv) if argv is not None else None)

    if not args.rbac_file.exists():
        p.error(f"File not found: {args.rbac_file}")

    try:
        data = json.loads(args.rbac_file.read_text(encoding="utf-8"))
    except Exception as e:
        p.error(f"Failed to parse JSON: {e}")

    names = collect_positions(data, unique=not args.no_unique)

    if args.format == "json":
        print(json.dumps(names, indent=2, ensure_ascii=False))
    elif args.format == "csv":
        # Simple CSV (single column header + rows)
        print("position")
        for n in names:
            # naive CSV escaping for commas/quotes
            if any(c in n for c in [",", '"']):
                n = '"' + n.replace('"', '""') + '"'
            print(n)
    else:
        # text (one per line)
        for n in names:
            print(n)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
