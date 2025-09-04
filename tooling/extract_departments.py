#!/usr/bin/env python3
# Update extract_departments.py: read RBAC.json, find departments via "unit"; write departments.csv.
# Optionally read positions.csv and compare with RBAC positions to write positions_missing.csv.
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set


# -----------------------------
# RBAC traversal helpers
# -----------------------------
def iter_units(node: Dict[str, Any]) -> Iterator[str]:
    """
    Yield department/unit names (snake_case) from this node and all descendants.

    RBAC.json structure (relevant bits):
      - node["unit"]: str   (e.g., "board_of_education_governing_board")
      - node["children"]: list[dict]
    """
    unit = node.get("unit")
    if isinstance(unit, str) and unit.strip():
        yield unit.strip()

    for child in node.get("children", []) or []:
        if isinstance(child, dict):
            yield from iter_units(child)


def collect_departments(data: Dict[str, Any], unique: bool = True) -> List[str]:
    """
    Traverse the RBAC structure and return a list of department/unit names.
    If `unique` is True, de-duplicate while preserving first-seen order.
    """
    departments: List[str] = []
    seen: Set[str] = set()

    hierarchy = data.get("hierarchy", [])
    if not isinstance(hierarchy, list):
        hierarchy = []

    for node in hierarchy:
        if isinstance(node, dict):
            for name in iter_units(node):
                if unique:
                    if name not in seen:
                        departments.append(name)
                        seen.add(name)
                else:
                    departments.append(name)

    return departments


def iter_positions(node: Dict[str, Any]) -> Iterator[str]:
    """Yield position names from this node and descendants (from node['positions'][*]['name'])."""
    for pos in node.get("positions", []) or []:
        name = pos.get("name")
        if isinstance(name, str) and name.strip():
            yield name.strip()
    for child in node.get("children", []) or []:
        if isinstance(child, dict):
            yield from iter_positions(child)


def collect_positions(data: Dict[str, Any], unique: bool = True) -> List[str]:
    """Collect all position names in the RBAC hierarchy."""
    positions: List[str] = []
    seen: Set[str] = set()

    hierarchy = data.get("hierarchy", [])
    if not isinstance(hierarchy, list):
        hierarchy = []

    for node in hierarchy:
        if isinstance(node, dict):
            for name in iter_positions(node):
                if unique:
                    if name not in seen:
                        positions.append(name)
                        seen.add(name)
                else:
                    positions.append(name)

    return positions


# -----------------------------
# CSV helpers
# -----------------------------
def write_csv(values: Iterable[str], path: Path,) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for v in values:
            w.writerow([v])
            count += 1
    return count


def read_positions_csv(path: Path) -> Set[str]:
    """
    Read a positions.csv file and return a set of positions (first column).

    Accepts either a header row containing 'position' or no header.
    """
    seen: Set[str] = set()
    if not path.exists():
        return seen

    with path.open("r", newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        rows = list(r)

    if not rows:
        return seen

    start_idx = 1 if rows and rows[0] and rows[0][0].strip().lower() == "position" else 0
    for row in rows[start_idx:]:
        if not row:
            continue
        val = (row[0] or "").strip()
        if val:
            seen.add(val)
    return seen


# -----------------------------
# CLI
# -----------------------------
def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Extract department/unit names from an OSSS RBAC JSON file.")
    p.add_argument("rbac_file", type=Path, help="Path to RBAC.json")
    p.add_argument("--positions-csv", type=Path, default=Path("positions.csv"),
                   help="Path to positions.csv (optional, used to compute positions_missing.csv)")
    args = p.parse_args(list(argv) if argv is not None else None)

    if not args.rbac_file.exists():
        p.error(f"File not found: {args.rbac_file}")

    try:
        data = json.loads(args.rbac_file.read_text(encoding="utf-8"))
    except Exception as e:
        p.error(f"Failed to parse JSON: {e}")

    # 1) Departments
    departments = collect_departments(data, unique=True)
    wrote = write_csv(departments, Path("departments.csv"))
    print(f"Wrote {wrote} department(s) to departments.csv")

    # 2) (Optional) Missing positions
    rbac_positions = set(collect_positions(data, unique=True))
    csv_positions = read_positions_csv(args.positions_csv)
    if csv_positions:
        missing = sorted(rbac_positions - csv_positions)
        wrote_miss = write_csv(missing, Path("positions_missing.csv"))
        print(f"Wrote {wrote_miss} missing position(s) to positions_missing.csv (RBAC - CSV)")
    else:
        print(f"Note: No positions CSV found at '{args.positions_csv}'. Skipping positions_missing.csv.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())