#!/usr/bin/env python3
"""
extract_positions.py

Extract position records from an OSSS RBAC JSON file.

Examples:
  # List of {"name", "permissions"} objects (default)
  python extract_positions.py RBAC.json --pretty

  # Mapping {name: [permissions...]}
  python extract_positions.py RBAC.json --group-by-name --pretty

  # List of resources mentioned by 'read:<resource>' permissions
  python extract_positions.py RBAC.json --read-list --pretty
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List


def _normalize_permissions(perms: Any) -> List[str]:
    out: List[str] = []
    if isinstance(perms, list):
        for p in perms:
            if isinstance(p, str):
                p = p.strip()
                if p:
                    out.append(p)
    return out


def iter_position_records(node: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    for pos in (node.get("positions") or []):
        if isinstance(pos, dict):
            name = pos.get("name")
            if isinstance(name, str) and name.strip():
                yield {
                    "name": name.strip(),
                    "permissions": _normalize_permissions(pos.get("permissions")),
                }

    for child in (node.get("children") or []):
        if isinstance(child, dict):
            yield from iter_position_records(child)


def collect_position_records(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    hierarchy = data.get("hierarchy")
    if not isinstance(hierarchy, list):
        return records
    for unit in hierarchy:
        if isinstance(unit, dict):
            records.extend(iter_position_records(unit))
    return records


def merge_by_name(records: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    by_name: Dict[str, List[str]] = {}
    for rec in records:
        name = rec["name"]
        perms = rec.get("permissions") or []
        bucket = by_name.setdefault(name, [])
        for p in perms:
            if p not in bucket:
                bucket.append(p)
    for k in by_name:
        by_name[k].sort()
    return by_name


def extract_read_resources(records: List[Dict[str, Any]]) -> List[str]:
    """
    Collect unique resource names from permissions starting with 'read:'.
    'read:foo' -> 'foo'
    """
    seen = set()
    out: List[str] = []
    for rec in records:
        for perm in rec.get("permissions") or []:
            perm = perm.strip()
            if perm.startswith("read:"):
                parts = perm.split(":", 1)
                if len(parts) == 2:
                    resource = parts[1].strip()
                    if resource and resource not in seen:
                        seen.add(resource)
                        out.append(resource)
    out.sort()
    return out


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Extract positions and permissions from an OSSS RBAC JSON file."
    )
    p.add_argument("rbac_file", type=Path, help="Path to RBAC.json")
    p.add_argument(
        "--group-by-name",
        action="store_true",
        help="Emit a mapping {name: [permissions...]} instead of a list of records.",
    )
    p.add_argument(
        "--read-list",
        action="store_true",
        help="Emit a JSON array of unique resources from 'read:<resource>' permissions.",
    )
    p.add_argument("--pretty", action="store_true", help="Pretty-print the output JSON.")
    args = p.parse_args(list(argv) if argv is not None else None)

    if not args.rbac_file.exists():
        p.error(f"File not found: {args.rbac_file}")

    try:
        data = json.loads(args.rbac_file.read_text(encoding="utf-8"))
    except Exception as e:
        p.error(f"Failed to parse JSON: {e}")

    records = collect_position_records(data)

    if args.read_list:
        payload: Any = extract_read_resources(records)
    elif args.group_by_name:
        payload = merge_by_name(records)
    else:
        payload = records

    print(json.dumps(payload, indent=2 if args.pretty else None, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
