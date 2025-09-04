#!/usr/bin/env python3
"""
extract_dept_positions_children_only.py

Builds a JSON mapping of { department(unit): [position names] } from RBAC.json.

- Collect positions from immediate children only (no grandchildren).
- If a department has no child positions, optionally fall back to positions on the department itself.

Usage:
  python extract_dept_positions_children_only.py RBAC.json -o departments_positions.json
Options:
  --no-fallback-self  Disable fallback (default is to fallback to self on empty children)
  --always-include-self  Always include department's own positions in addition to children
  --humanize  Convert snake_case to Title Case
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Dict, List, Set, Any


def _humanize(s: str) -> str:
    return " ".join(w.capitalize() for w in s.replace("-", " ").replace("_", " ").split())


def _positions_on_node(node: Dict[str, Any]) -> Set[str]:
    names: Set[str] = set()
    for pos in (node.get("positions") or []):
        if isinstance(pos, dict) and "name" in pos:
            names.add(pos["name"])
        elif isinstance(pos, str):
            names.add(pos)
    return names


def _children_positions_one_level(node: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    for child in (node.get("children") or []):
        if isinstance(child, dict):
            out |= _positions_on_node(child)
    return out


def _walk(node: Dict[str, Any],
          acc: Dict[str, Set[str]],
          always_include_self: bool,
          fallback_self_on_empty: bool) -> None:
    unit = node.get("unit")
    if unit:
        child_pos = _children_positions_one_level(node)
        pos = set(child_pos)

        if always_include_self:
            pos |= _positions_on_node(node)
        elif fallback_self_on_empty and not child_pos:
            # only fallback to self if children yielded nothing
            pos = _positions_on_node(node)

        if unit not in acc:
            acc[unit] = set()
        acc[unit] |= pos

    for child in (node.get("children") or []):
        if isinstance(child, dict):
            _walk(child, acc, always_include_self, fallback_self_on_empty)


def extract(rbac: Dict[str, Any],
            always_include_self: bool = False,
            fallback_self_on_empty: bool = True,
            humanize: bool = False) -> Dict[str, List[str]]:
    acc: Dict[str, Set[str]] = {}
    for node in (rbac.get("hierarchy") or []):
        if isinstance(node, dict):
            _walk(node, acc, always_include_self, fallback_self_on_empty)

    result: Dict[str, List[str]] = {}
    for unit, names in acc.items():
        u = _humanize(unit) if humanize else unit
        result[u] = sorted({_humanize(n) for n in names} if humanize else names)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rbac_path")
    ap.add_argument("-o", "--out", default="departments_positions.json")
    ap.add_argument("--always-include-self", action="store_true",
                    help="Include department's own positions in addition to children")
    ap.add_argument("--no-fallback-self", action="store_true",
                    help="Disable fallback to self positions when children are empty")
    ap.add_argument("--humanize", action="store_true")
    args = ap.parse_args()

    data = json.loads(Path(args.rbac_path).read_text(encoding="utf-8"))
    mapping = extract(
        data,
        always_include_self=args.always_include_self,
        fallback_self_on_empty=not args.no_fallback_self,  # default True
        humanize=args.humanize,
    )
    Path(args.out).write_text(json.dumps(mapping, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out} with {len(mapping)} departments.")


if __name__ == "__main__":
    main()
