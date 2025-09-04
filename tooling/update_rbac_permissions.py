#!/usr/bin/env python3
"""
update_rbac_permissions.py

Defaults:
  pta_json  -> ../RBAC_positions_and_table_access.json (relative to this script)
  rbac_json -> ../RBAC.json (relative to this script)

Usage:
  # use defaults
  python update_rbac_permissions.py

  # override one or both
  python update_rbac_permissions.py path/to/RBAC_positions_and_table_access.json
  python update_rbac_permissions.py path/to/RBAC_positions_and_table_access.json path/to/RBAC.json

  # write elsewhere / dry run
  python update_rbac_permissions.py -o RBAC.updated.json
  python update_rbac_permissions.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(2)


def build_position_table_map(pta_data: Any) -> Dict[str, Set[str]]:
    """
    Returns: { position_name -> {table1, table2, ...} }
    Accepts tables either as simple strings or objects with {"table": "..."}.
    """
    mapping: Dict[str, Set[str]] = {}
    if not isinstance(pta_data, list):
        return mapping

    for entry in pta_data:
        if not isinstance(entry, dict):
            continue
        pos_name = entry.get("position_name")
        if not pos_name:
            continue

        tables = entry.get("tables") or []
        table_names: Set[str] = set()
        for t in tables:
            if isinstance(t, str):
                t = t.strip()
                if t:
                    table_names.add(t)
            elif isinstance(t, dict):
                tbl = (t.get("table") or "").strip()
                if tbl:
                    table_names.add(tbl)
        if table_names:
            mapping.setdefault(pos_name, set()).update(table_names)
    return mapping


def iter_units(unit: Dict[str, Any]):
    """Yield this unit and all descendant units."""
    yield unit
    for child in unit.get("children", []) or []:
        if isinstance(child, dict):
            yield from iter_units(child)


def update_permissions_in_rbac(rbac: Dict[str, Any], pos_to_tables: Dict[str, Set[str]]) -> Dict[str, int]:
    """
    Mutates `rbac` in-place, adding read:/manage: permissions to matching positions.
    Returns counters.
    """
    updated_positions = 0
    added_permissions = 0

    for unit in (rbac.get("hierarchy") or []):
        if not isinstance(unit, dict):
            continue
        for u in iter_units(unit):
            positions = u.get("positions") or []
            if not isinstance(positions, list):
                continue
            for pos in positions:
                if not isinstance(pos, dict):
                    continue
                name = pos.get("name")
                if not isinstance(name, str):
                    continue
                tables = pos_to_tables.get(name)
                if not tables:
                    continue

                perms = pos.get("permissions")
                if not isinstance(perms, list):
                    perms = []
                    pos["permissions"] = perms

                additions = []
                for t in sorted(tables):
                    additions.append(f"read:{t}")
                    additions.append(f"manage:{t}")

                existing = set(perms)
                newly_added = [p for p in additions if p not in existing]
                if newly_added:
                    perms.extend(newly_added)
                    updated_positions += 1
                    added_permissions += len(newly_added)

    return {"updated_positions": updated_positions, "added_permissions": added_permissions}


def main():
    here = Path(__file__).resolve().parent
    default_pta = (here / ".." / "RBAC_positions_and_table_access.json").resolve()
    default_rbac = (here / ".." / "RBAC.json").resolve()

    ap = argparse.ArgumentParser(
        description="Update RBAC.json position permissions from positions/table access mapping."
    )
    ap.add_argument(
        "pta_json",
        nargs="?",
        type=Path,
        default=default_pta,
        help=f"Path to RBAC_positions_and_table_access.json (default: {default_pta})",
    )
    ap.add_argument(
        "rbac_json",
        nargs="?",
        type=Path,
        default=default_rbac,
        help=f"Path to RBAC.json (default: {default_rbac})",
    )
    ap.add_argument("-o", "--output", type=Path, help="Optional output path (if omitted, updates RBAC.json in place)")
    ap.add_argument("--dry-run", action="store_true", help="Show summary and do not write changes")
    ap.add_argument("--backup", action="store_true", help="Write RBAC.json.bak before in-place update")
    args = ap.parse_args()

    pta = load_json(args.pta_json)
    rbac = load_json(args.rbac_json)

    pos_to_tables = build_position_table_map(pta)
    stats = update_permissions_in_rbac(rbac, pos_to_tables)

    dest = args.output or args.rbac_json
    if args.dry_run:
        print(json.dumps({"stats": stats, "would_write": str(dest)}, indent=2))
        return

    if args.output is None and args.backup:
        bak = args.rbac_json.with_suffix(args.rbac_json.suffix + ".bak")
        bak.write_text(args.rbac_json.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup written: {bak}")

    dest.write_text(json.dumps(rbac, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(dest), "stats": stats}, indent=2))


if __name__ == "__main__":
    main()
